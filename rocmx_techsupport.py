#!/usr/bin/env python3
# Copyright (c) 2025-2026 Advanced Micro Devices, Inc. All Rights Reserved.
#
# rocmx_techsupport.py
# ROCm X TechSupport Log Collection Utility for TheRock 10.x releases.
# Collects system, GPU, ROCm, and network diagnostics for support/troubleshooting.
#
# Single-file, no external dependencies beyond Python 3.8+ stdlib.
# Author: srinivasan.subramanian@amd.com
# Revision: V2.0
#
# Usage:
#   sudo python3 rocmx_techsupport.py > $(hostname).$(date +%F-%H%M%S).rocmx.log 2>&1
#   python3 rocmx_techsupport.py --json --output report.json

import argparse
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = "2.0"
SCRIPT_NAME = "rocmx_techsupport"

DMESG_FILTER = (
    r" Linux v| Command line|gfx|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog"
    r"|bug|nmi|dazed|too|mce|edac|oop|fail|fault|atom|bios|kfd|vfio|iommu"
    r"|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash"
)

GFX_TO_CDNA = {
    "gfx900": "GCN5.0",
    "gfx906": "GCN5.1",
    "gfx908": "CDNA",
    "gfx90a": "CDNA2",
    "gfx942": "CDNA3",
    "gfx950": "CDNA4",
    "gfx1250": "CDNA5",
}

AMD_SMI_SUBCOMMANDS = [
    ("version", "AMD SMI version"),
    ("list", "AMD SMI list"),
    ("static", "AMD SMI static"),
    ("firmware", "AMD SMI firmware"),
    ("bad-pages", "AMD SMI bad-pages"),
    ("process", "AMD SMI process"),
    ("topology", "AMD SMI topology"),
    ("xgmi", "AMD SMI xgmi"),
]

AMD_SMI_METRIC_COMMANDS = [
    ("metric -t", "AMD SMI temperature"),
    ("metric -e", "AMD SMI ecc"),
    ("metric -k", "AMD SMI ecc-blocks"),
]


ROCM_ENV_FILTER = re.compile(
    r"rocm|hsa|hip|mpi|openmp|ucx|miopen|rccl|nccl|therock",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: List[str],
    timeout: int = 60,
    check: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    merged_env = {**os.environ, **(env or {})}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:
        return 1, "", f"Error running {' '.join(cmd)}: {exc}"


def find_binary(name: str, extra_paths: Optional[List[str]] = None) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    search = ["/usr/bin", "/usr/sbin", "/sbin", "/bin"]
    if extra_paths:
        search = extra_paths + search
    for d in search:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def read_file(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(errors="replace").rstrip()
    except (OSError, PermissionError):
        return None


def grep_lines(text: str, pattern: str, flags: int = re.IGNORECASE) -> str:
    regex = re.compile(pattern, flags)
    return "\n".join(line for line in text.splitlines() if regex.search(line))


# ---------------------------------------------------------------------------
# Output / section management
# ---------------------------------------------------------------------------

class SectionCollector:
    def __init__(self, json_mode: bool = False, verbose: bool = False):
        self.json_mode = json_mode
        self.verbose = verbose
        self.sections: List[Dict[str, Any]] = []
        self._current_lines: List[str] = []

    def begin_section(self, title: str) -> None:
        header = f"===== Section: {title:<30s} ==============="
        self._current_lines = [header]
        if not self.json_mode:
            print(header)

    def add_output(self, text: str) -> None:
        if text:
            self._current_lines.append(text)
            if not self.json_mode:
                print(text)

    def add_not_found(self, tool: str) -> None:
        msg = f"RocmxTechSupportNotFound: {tool} not found!"
        self._current_lines.append(msg)
        if not self.json_mode:
            print(msg)

    def add_warning(self, msg: str) -> None:
        warning = f"WARNING: {msg}"
        self._current_lines.append(warning)
        if not self.json_mode:
            print(warning)

    def end_section(self, title: str) -> None:
        self.sections.append({
            "title": title,
            "content": "\n".join(self._current_lines[1:]),
        })
        self._current_lines = []

    def run_tool(self, title: str, cmd: List[str], env: Optional[Dict[str, str]] = None, timeout: int = 60) -> str:
        self.begin_section(title)
        rc, out, err = run_cmd(cmd, timeout=timeout, env=env)
        if rc == 127:
            self.add_not_found(cmd[0])
        else:
            if out.strip():
                self.add_output(out.rstrip())
            if err.strip() and self.verbose:
                self.add_output(f"[stderr] {err.rstrip()}")
        self.end_section(title)
        return out

    def to_json(self) -> str:
        return json.dumps({
            "script": SCRIPT_NAME,
            "version": VERSION,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "hostname": platform.node(),
            "sections": self.sections,
        }, indent=2)


# ---------------------------------------------------------------------------
# TheRock 10.x ROCm discovery
# ---------------------------------------------------------------------------

def discover_rocm(explicit_path: Optional[str] = None) -> Optional[str]:
    if explicit_path:
        if os.path.isdir(explicit_path):
            return explicit_path
        return None

    for var in ("ROCM_PATH", "ROCM_VERSION", "HIP_PATH"):
        val = os.environ.get(var, "")
        if val and os.path.isdir(val):
            return val

    for tool in ("amd-smi", "rocminfo", "hipcc"):
        path = shutil.which(tool)
        if path:
            bin_dir = os.path.dirname(os.path.abspath(path))
            rocm_dir = os.path.dirname(bin_dir)
            if os.path.isdir(rocm_dir) and os.path.basename(bin_dir) == "bin":
                version_json = os.path.join(rocm_dir, "version.json")
                rocminfo_check = os.path.join(bin_dir, "rocminfo")
                amdsmi_check = os.path.join(bin_dir, "amd-smi")
                if (os.path.isfile(version_json)
                        or os.path.isfile(rocminfo_check)
                        or os.path.isfile(amdsmi_check)):
                    return rocm_dir

    for prefix in ("/opt/rocm", "/usr/local/rocm", "/usr"):
        if os.path.isdir(prefix) and os.path.isdir(os.path.join(prefix, "bin")):
            amd_smi = os.path.join(prefix, "bin", "amd-smi")
            rocminfo = os.path.join(prefix, "bin", "rocminfo")
            if os.path.isfile(amd_smi) or os.path.isfile(rocminfo):
                return prefix

    return None


def get_rocm_version_info(rocm_path: Optional[str]) -> Dict[str, str]:
    info: Dict[str, str] = {}
    if not rocm_path:
        return info

    version_json = os.path.join(rocm_path, "version.json")
    if os.path.isfile(version_json):
        try:
            data = json.loads(Path(version_json).read_text())
            info["rocm-version"] = data.get("rocm-version", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    version_file = os.path.join(rocm_path, ".info", "version")
    if os.path.isfile(version_file):
        content = read_file(version_file)
        if content:
            info["version-file"] = content.strip()

    return info


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def detect_gpus_sysfs() -> List[Dict[str, str]]:
    gpus: List[Dict[str, str]] = []
    drm_base = Path("/sys/class/drm")
    if not drm_base.is_dir():
        return gpus

    for card in sorted(drm_base.iterdir()):
        if not re.match(r"card\d+$", card.name):
            continue
        device = card / "device"
        if not device.is_dir():
            continue
        vendor = read_file(str(device / "vendor"))
        if vendor and vendor.strip() != "0x1002":
            continue

        gpu: Dict[str, str] = {"card": card.name}
        for attr in ("current_link_width", "current_link_speed", "device", "subsystem_device"):
            val = read_file(str(device / attr))
            if val:
                gpu[attr] = val.strip()
        gpus.append(gpu)
    return gpus


def detect_gpu_targets(rocm_path: Optional[str]) -> List[str]:
    targets: List[str] = []
    rocminfo_bin = None
    if rocm_path:
        candidate = os.path.join(rocm_path, "bin", "rocminfo")
        if os.path.isfile(candidate):
            rocminfo_bin = candidate
    if not rocminfo_bin:
        rocminfo_bin = find_binary("rocminfo")
    if not rocminfo_bin:
        return targets

    rc, out, _ = run_cmd([rocminfo_bin])
    if rc == 0:
        for match in re.finditer(r"gfx\w+", out):
            t = match.group()
            if t not in targets:
                targets.append(t)
    return targets


# ---------------------------------------------------------------------------
# Collector functions
# ---------------------------------------------------------------------------

def collect_system_info(col: SectionCollector) -> None:
    col.begin_section("OS Distribution")
    rc, out, _ = run_cmd(["uname", "-a"])
    col.add_output(out.rstrip())
    content = read_file("/etc/os-release")
    if content:
        col.add_output(content)
    col.end_section("OS Distribution")

    col.begin_section("System Uptime")
    uptime = find_binary("uptime")
    if uptime:
        rc, out, _ = run_cmd([uptime])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("uptime")
    col.end_section("System Uptime")

    col.begin_section("Kernel Boot Parameters")
    content = read_file("/proc/cmdline")
    if content:
        col.add_output(content)
    else:
        col.add_output("Could not read /proc/cmdline")
    col.end_section("Kernel Boot Parameters")

    col.begin_section("Kernel Parameters sysctl")
    sysctl = find_binary("sysctl")
    if sysctl:
        rc, out, _ = run_cmd([sysctl, "-a"], timeout=30)
        col.add_output(out.rstrip())
    else:
        col.add_not_found("sysctl")
    col.end_section("Kernel Parameters sysctl")

    col.begin_section("CPU Information")
    lscpu = find_binary("lscpu")
    if lscpu:
        rc, out, _ = run_cmd([lscpu])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("lscpu")
    col.end_section("CPU Information")

    col.begin_section("Memory Information")
    lsmem = find_binary("lsmem")
    if lsmem:
        rc, out, _ = run_cmd([lsmem])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("lsmem")
    col.end_section("Memory Information")

    col.begin_section("Memory Summary")
    meminfo = read_file("/proc/meminfo")
    if meminfo:
        lines = meminfo.splitlines()[:5]
        col.add_output("\n".join(lines))
    else:
        col.add_output("Could not read /proc/meminfo")
    col.end_section("Memory Summary")


def collect_kernel_logs(col: SectionCollector) -> None:
    journal_dir = Path("/var/log/journal")
    col.begin_section("dmesg GPU/DRM/ATOM/BIOS")
    if not journal_dir.exists():
        col.add_warning("Persistent logging possibly disabled.")
        col.add_warning("Run: sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald.service")

    dmesg = find_binary("dmesg")
    if dmesg:
        col.add_output("--- dmesg boot logs ---")
        rc, out, _ = run_cmd([dmesg, "-T"], timeout=30)
        if rc == 0:
            col.add_output(grep_lines(out, DMESG_FILTER))
        else:
            col.add_warning("dmesg returned non-zero (may need sudo)")
    else:
        col.add_not_found("dmesg")

    journalctl = find_binary("journalctl")
    if journalctl:
        for boot_offset, label in [(0, "Current"), (-1, "Previous"), (-2, "Second Previous"), (-3, "Third Previous")]:
            col.add_output(f"--- {label} boot logs ---")
            rc, out, _ = run_cmd([journalctl, "-b", str(boot_offset)], timeout=30)
            if rc == 0:
                col.add_output(grep_lines(out, DMESG_FILTER))
    else:
        col.add_not_found("journalctl")
    col.end_section("dmesg GPU/DRM/ATOM/BIOS")


def collect_hardware_info(col: SectionCollector) -> None:
    lshw = find_binary("lshw")
    col.begin_section("Hardware Information")
    if lshw:
        rc, out, _ = run_cmd([lshw], timeout=120)
        col.add_output(out.rstrip())
    else:
        col.add_not_found("lshw")
        col.add_output("Note: Install lshw (sudo apt install lshw)")
    col.end_section("Hardware Information")

    col.run_tool("lsmod loaded modules", ["lsmod"])
    col.run_tool("amdgpu modinfo", ["modinfo", "amdgpu"])

    dkms = find_binary("dkms")
    if dkms:
        col.run_tool("dkms status", [dkms, "status"])
    else:
        col.begin_section("dkms status")
        col.add_not_found("dkms")
        col.end_section("dkms status")

    col.begin_section("amdgpu udev rule")
    content = read_file("/etc/udev/rules.d/70-amdgpu.rules")
    if content:
        col.add_output(content)
    else:
        col.add_output("No 70-amdgpu.rules found")
    col.end_section("amdgpu udev rule")

    col.begin_section("lsinitrd lsinitramfs")
    os_release = read_file("/etc/os-release") or ""
    if re.search(r"debian|ubuntu", os_release, re.IGNORECASE):
        lsinitramfs = find_binary("lsinitramfs")
        if lsinitramfs:
            rc, uname_out, _ = run_cmd(["uname", "-r"])
            kernel = uname_out.strip()
            initrd = f"/boot/initrd.img-{kernel}"
            if os.path.isfile(initrd):
                rc, out, _ = run_cmd([lsinitramfs, initrd], timeout=60)
                col.add_output(out.rstrip())
            else:
                col.add_output(f"initrd not found at {initrd}")
        else:
            col.add_not_found("lsinitramfs")
    else:
        lsinitrd = find_binary("lsinitrd")
        if lsinitrd:
            rc, out, _ = run_cmd(["sudo", lsinitrd], timeout=60)
            col.add_output(out.rstrip())
        else:
            col.add_not_found("lsinitrd")
    col.end_section("lsinitrd lsinitramfs")

    lstopo = find_binary("lstopo-no-graphics")
    col.begin_section("Hardware Topology")
    if lstopo:
        rc, out, _ = run_cmd([lstopo])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("lstopo-no-graphics")
        col.add_output("Note: Install hwloc (sudo apt install hwloc)")
    col.end_section("Hardware Topology")

    col.run_tool("dmidecode Information", ["dmidecode"])

    lspci = find_binary("lspci")
    col.begin_section("lspci verbose output")
    if lspci:
        rc, out, _ = run_cmd([lspci, "-vvvt"])
        col.add_output(out.rstrip())
        rc, out, _ = run_cmd([lspci, "-vvv"])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("lspci")
    col.end_section("lspci verbose output")


def collect_rocm_install(col: SectionCollector, rocm_path: Optional[str]) -> None:
    col.begin_section("TheRock ROCm Installation")
    if rocm_path:
        col.add_output(f"ROCm path: {rocm_path}")
        version_info = get_rocm_version_info(rocm_path)
        for k, v in version_info.items():
            col.add_output(f"  {k}: {v}")

        bin_dir = os.path.join(rocm_path, "bin")
        if os.path.isdir(bin_dir):
            binaries = sorted(os.listdir(bin_dir))
            col.add_output(f"ROCm binaries ({len(binaries)}): {', '.join(binaries[:30])}")
            if len(binaries) > 30:
                col.add_output(f"  ... and {len(binaries) - 30} more")
    else:
        col.add_warning("No TheRock ROCm installation found.")
        col.add_output("Set ROCM_PATH or --rocm-path to specify the ROCm installation directory.")
    col.end_section("TheRock ROCm Installation")

    col.begin_section("ROCm Repo Setup")
    repo_dirs = [
        "/etc/apt/sources.list.d",
        "/etc/zypp/repos.d",
        "/etc/yum.repos.d",
    ]
    found_repos = False
    for repo_dir in repo_dirs:
        if os.path.isdir(repo_dir):
            for f in sorted(os.listdir(repo_dir)):
                fpath = os.path.join(repo_dir, f)
                if not os.path.isfile(fpath):
                    continue
                content = read_file(fpath)
                if content and re.search(r"rocm|amdgpu", content, re.IGNORECASE):
                    col.add_output(f"{fpath}:")
                    col.add_output(grep_lines(content, r"rocm|amdgpu"))
                    found_repos = True
    if not found_repos:
        col.add_output("No ROCm/AMDGPU repo entries found in apt/yum/zypp sources")
    col.end_section("ROCm Repo Setup")

    col.begin_section("ROCm Packages Installed")
    os_release = read_file("/etc/os-release") or ""
    if re.search(r"debian|ubuntu", os_release, re.IGNORECASE):
        dpkg = find_binary("dpkg")
        if dpkg:
            rc, out, _ = run_cmd([dpkg, "-l"])
            pkg_filter = (
                r"ocl-icd|kfdtest|llvm-amd|miopen|half|hip|hcc|hsa|rocm|atmi|comgr"
                r"|composa|amd-smi|aomp|amdgpu|rock|mivision|migraph|rocprofiler"
                r"|roctracer|rocbl|hipify|rocsol|rocthr|rocff|rocalu|rocprim|rocrand"
                r"|rccl|rocspar|rdc|rocwmma|rpp|openmp|amdfwflash|ocl|opencl|therock"
            )
            col.add_output(grep_lines(out, pkg_filter))
    else:
        rpm = find_binary("rpm")
        if rpm:
            rc, out, _ = run_cmd([rpm, "-qa"])
            pkg_filter = (
                r"ocl-icd|kfdtest|llvm-amd|miopen|half|hip|hcc|hsa|rocm|atmi|comgr"
                r"|composa|amd-smi|aomp|amdgpu|rock|mivision|migraph|rocprofiler"
                r"|roctracer|rocblas|hipify|rocsol|rocthr|rocff|rocalu|rocprim|rocrand"
                r"|rccl|rocspar|rdc|rocwmma|rpp|openmp|amdfwflash|ocl|opencl|therock"
            )
            col.add_output(grep_lines(out, pkg_filter))
    col.end_section("ROCm Packages Installed")

    col.begin_section("ROCm pip packages")
    pip = find_binary("pip3") or find_binary("pip")
    if pip:
        rc, out, _ = run_cmd([pip, "list"])
        if rc == 0:
            filtered = grep_lines(out, r"rocm|hip|amd|therock|rccl|miopen")
            if filtered.strip():
                col.add_output(filtered)
            else:
                col.add_output("No ROCm pip packages found in current environment")
    else:
        col.add_output("pip not found in PATH")
    col.end_section("ROCm pip packages")

    col.begin_section("ROCm ldconfig entries")
    for conf_dir in ("/etc/ld.so.conf.d",):
        if os.path.isdir(conf_dir):
            for f in sorted(os.listdir(conf_dir)):
                content = read_file(os.path.join(conf_dir, f))
                if content and re.search(r"rocm", content, re.IGNORECASE):
                    col.add_output(f"{f}: {content}")
    col.end_section("ROCm ldconfig entries")

    col.begin_section("ROCm ldcache entries")
    ldconfig = find_binary("ldconfig")
    if ldconfig:
        rc, out, _ = run_cmd([ldconfig, "-p"])
        if rc == 0:
            col.add_output(grep_lines(out, r"rocm"))
    col.end_section("ROCm ldcache entries")

    col.begin_section("ROCm environment variables")
    for key, val in sorted(os.environ.items()):
        if ROCM_ENV_FILTER.search(key) or ROCM_ENV_FILTER.search(val):
            col.add_output(f"{key}={val}")
    col.end_section("ROCm environment variables")


def collect_gpu_diagnostics(col: SectionCollector, rocm_path: Optional[str]) -> None:
    extra_paths = []
    if rocm_path:
        extra_paths.append(os.path.join(rocm_path, "bin"))

    lib_env: Dict[str, str] = {}
    if rocm_path:
        existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
        lib_env["LD_LIBRARY_PATH"] = f"{rocm_path}/lib:{existing_ld}"

    # GPU architecture detection
    col.begin_section("GPU Architecture Detection")
    targets = detect_gpu_targets(rocm_path)
    if targets:
        for t in targets:
            gen = GFX_TO_CDNA.get(t, "Unknown")
            col.add_output(f"  {t} ({gen})")
    else:
        col.add_output("No GPU targets detected via rocminfo")

    gpus_sysfs = detect_gpus_sysfs()
    if gpus_sysfs:
        col.add_output(f"sysfs GPU cards found: {len(gpus_sysfs)}")
        for g in gpus_sysfs:
            col.add_output(f"  {g['card']}: device={g.get('device', '?')}")
    col.end_section("GPU Architecture Detection")

    # AMD SMI
    amd_smi = find_binary("amd-smi", extra_paths)
    if amd_smi:
        col.run_tool("AMD SMI", [amd_smi], env=lib_env)
        for subcmd, title in AMD_SMI_SUBCOMMANDS:
            col.run_tool(title, [amd_smi] + subcmd.split(), env=lib_env)
        for subcmd, title in AMD_SMI_METRIC_COMMANDS:
            col.run_tool(title, [amd_smi] + subcmd.split(), env=lib_env)
    else:
        col.begin_section("AMD SMI")
        col.add_not_found("amd-smi")
        col.end_section("AMD SMI")

    # PCIe link status (dynamic based on detected GPUs)
    col.begin_section("GPU PCIe Link Config")
    gpus = detect_gpus_sysfs()
    if gpus:
        for gpu in gpus:
            card = gpu["card"]
            width = gpu.get("current_link_width", "?")
            speed = gpu.get("current_link_speed", "?")
            col.add_output(f"{card}: Width={width}, Speed={speed}")
    else:
        col.add_output("No AMD GPUs detected in sysfs")
    col.end_section("GPU PCIe Link Config")

    # KFD PIDs
    col.begin_section("KFD PIDs sysfs kfd proc")
    kfd_proc = "/sys/class/kfd/kfd/proc"
    if os.path.isdir(kfd_proc):
        pids = os.listdir(kfd_proc)
        col.add_output(f"Active KFD processes: {' '.join(pids) if pids else 'none'}")
    else:
        col.add_output("KFD proc sysfs not found")
    col.end_section("KFD PIDs sysfs kfd proc")

    # rocminfo
    rocminfo_bin = find_binary("rocminfo", extra_paths)
    if rocminfo_bin:
        col.run_tool("rocminfo", [rocminfo_bin], timeout=30)

    # rocm-bandwidth-test
    rbt = find_binary("rocm-bandwidth-test", extra_paths)
    if rbt:
        col.run_tool("rocm-bandwidth-test Topology", [rbt, "-t"], timeout=120)

    # clinfo — check standard PATH, then OpenCL subdirectory layouts
    clinfo_candidates = [find_binary("clinfo", extra_paths)]
    if rocm_path:
        clinfo_candidates.extend([
            os.path.join(rocm_path, "opencl", "bin", "clinfo"),
            os.path.join(rocm_path, "opencl", "bin", "x86_64", "clinfo"),
        ])
    clinfo_found = False
    for clinfo_path in clinfo_candidates:
        if clinfo_path and os.path.isfile(clinfo_path):
            col.run_tool("clinfo", [clinfo_path], timeout=30)
            clinfo_found = True
            break
    if not clinfo_found:
        col.begin_section("clinfo")
        col.add_not_found("clinfo")
        col.end_section("clinfo")



def collect_network_info(col: SectionCollector) -> None:
    # NUMA
    numactl = find_binary("numactl")
    col.begin_section("NUMA Topology")
    if numactl:
        rc, out, _ = run_cmd([numactl, "-H"])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("numactl")
    col.end_section("NUMA Topology")

    # InfiniBand
    ibstat = find_binary("ibstat")
    col.begin_section("InfiniBand Status")
    if ibstat:
        rc, out, _ = run_cmd([ibstat])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("ibstat")
    col.end_section("InfiniBand Status")

    ibv_devinfo = find_binary("ibv_devinfo")
    col.begin_section("IB Device Info")
    if ibv_devinfo:
        rc, out, _ = run_cmd([ibv_devinfo])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("ibv_devinfo")
    col.end_section("IB Device Info")

    ibdev2netdev = find_binary("ibdev2netdev")
    col.begin_section("IB to Ethernet Mapping")
    if ibdev2netdev:
        rc, out, _ = run_cmd([ibdev2netdev])
        col.add_output(out.rstrip())
        rc, out, _ = run_cmd([ibdev2netdev, "-v"])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("ibdev2netdev")
    col.end_section("IB to Ethernet Mapping")

    # OFED
    ofed_info = find_binary("ofed_info")
    if ofed_info:
        col.run_tool("OFED Information", [ofed_info, "-s"])

    # MST
    mst = find_binary("mst")
    col.begin_section("Mellanox Software Tools")
    if mst:
        run_cmd(["sudo", mst, "start"])
        rc, out, _ = run_cmd(["sudo", mst, "status", "-v"])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("mst")
    col.end_section("Mellanox Software Tools")

    # Broadcom niccli
    niccli = find_binary("niccli")
    col.begin_section("Broadcom niccli")
    if niccli:
        rc, out, _ = run_cmd(["sudo", niccli, "--listdev"])
        col.add_output(out.rstrip())
        for line in out.splitlines():
            match = re.match(r"^(\d+)\s*\)", line)
            if match:
                dev_num = match.group(1)
                rc2, out2, _ = run_cmd(["sudo", niccli, "-i", dev_num, "getqos"])
                col.add_output(out2.rstrip())
    else:
        col.add_not_found("niccli")
    col.end_section("Broadcom niccli")

    # IP / Ethernet
    ip_bin = find_binary("ip")
    col.begin_section("Ethernet IP ADDR")
    if ip_bin:
        for subcmd in [
            [ip_bin, "addr"],
            [ip_bin, "-br", "addr"],
            [ip_bin, "link", "show"],
            [ip_bin, "route", "show"],
            [ip_bin, "rule", "show"],
            [ip_bin, "neighbor", "show"],
        ]:
            rc, out, _ = run_cmd(subcmd)
            col.add_output(out.rstrip())
    else:
        col.add_not_found("ip")
    col.end_section("Ethernet IP ADDR")

    # Netplan
    col.begin_section("Netplan")
    netplan_dir = Path("/etc/netplan")
    if netplan_dir.is_dir():
        for f in sorted(netplan_dir.glob("*.yaml")):
            content = read_file(str(f))
            if content:
                col.add_output(f"--- {f.name} ---")
                col.add_output(content)
    else:
        col.add_output("No /etc/netplan directory")
    col.end_section("Netplan")

    # ethtool
    ethtool = find_binary("ethtool")
    col.begin_section("Ethernet ethtool")
    if ethtool:
        net_dir = Path("/sys/class/net")
        if net_dir.is_dir():
            for iface in sorted(net_dir.iterdir()):
                rc, out, _ = run_cmd(["sudo", ethtool, iface.name])
                col.add_output(f"--- {iface.name} ---")
                col.add_output(out.rstrip())
    else:
        col.add_not_found("ethtool")
    col.end_section("Ethernet ethtool")

    # RDMA
    rdma = find_binary("rdma")
    col.begin_section("RDMA")
    if rdma:
        rc, out, _ = run_cmd(["sudo", rdma, "link"])
        col.add_output(out.rstrip())
        rc, out, _ = run_cmd(["sudo", rdma, "stat"])
        col.add_output(out.rstrip())
    else:
        col.add_not_found("rdma")
    col.end_section("RDMA")

    # LLDP
    lldpcli = find_binary("lldpcli")
    if lldpcli:
        col.run_tool("lldpcli neighbors", ["sudo", lldpcli, "show", "neighbor"])

    lldpctl = find_binary("lldpctl")
    if lldpctl:
        col.run_tool("lldpctl", ["sudo", lldpctl])


def collect_tuning_info(col: SectionCollector) -> None:
    col.begin_section("Tuning Configuration")
    tuned_adm = find_binary("tuned-adm")
    if tuned_adm:
        rc, out, _ = run_cmd(["sudo", tuned_adm, "profile"])
        col.add_output(f"Active profile: {out.rstrip()}")

    tuned_conf = "/etc/tuned/amd_custom/tuned.conf"
    content = read_file(tuned_conf)
    if content:
        col.add_output(f"--- {tuned_conf} ---")
        col.add_output(content)
    else:
        col.add_output(f"{tuned_conf} not found")
    col.end_section("Tuning Configuration")

    # nicctl
    nicctl = find_binary("nicctl")
    col.begin_section("nicctl")
    if nicctl and os.access(nicctl, os.X_OK):
        nicctl_cmds = [
            ["sudo", nicctl, "show", "card"],
            ["sudo", nicctl, "show", "dcqcn"],
            ["sudo", nicctl, "show", "environment"],
            ["sudo", nicctl, "show", "pcie", "ats"],
            ["sudo", nicctl, "show", "port"],
            ["sudo", nicctl, "show", "qos"],
            ["sudo", nicctl, "show", "rdma", "statistics"],
            ["sudo", nicctl, "show", "version", "host-software"],
            ["sudo", nicctl, "show", "version", "firmware"],
        ]
        for cmd in nicctl_cmds:
            label = " ".join(cmd[2:])
            col.add_output(f"--- nicctl {label} ---")
            rc, out, _ = run_cmd(cmd)
            col.add_output(out.rstrip())
    else:
        col.add_not_found("nicctl")
    col.end_section("nicctl")


# ---------------------------------------------------------------------------
# Section registry — controls what runs and in what order
# ---------------------------------------------------------------------------

SECTION_REGISTRY: List[Tuple[str, Callable]] = [
    ("system", collect_system_info),
    ("kernel_logs", collect_kernel_logs),
    ("hardware", collect_hardware_info),
    ("network", collect_network_info),
    ("tuning", collect_tuning_info),
]

# rocm_install and gpu_diagnostics need rocm_path, handled specially in main


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description=textwrap.dedent(f"""\
            ROCm X TechSupport Log Collection Utility V{VERSION}
            Collects system, GPU, ROCm, and network diagnostics for TheRock 10.x releases.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rocm-path", help="Explicit path to ROCm installation")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--sections",
        help="Comma-separated list of sections to run (default: all). "
             "Available: system,kernel_logs,hardware,rocm,gpu,network,tuning",
    )
    parser.add_argument("--output", help="Write output to file (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Include extra debug info")
    parser.add_argument("--version", action="version", version=f"{SCRIPT_NAME} V{VERSION}")

    args = parser.parse_args()

    if args.output:
        sys.stdout = open(args.output, "w")

    col = SectionCollector(json_mode=args.json, verbose=args.verbose)

    if not args.json:
        print(f"=== ROCm X TechSupport Log Collection Utility: V{VERSION} ===")
        print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
        print(f"Hostname: {platform.node()}")

    rocm_path = discover_rocm(args.rocm_path)
    if not args.json:
        print(f"ROCm path: {rocm_path or 'NOT FOUND'}")
        print()

    requested = None
    if args.sections:
        requested = set(s.strip() for s in args.sections.split(","))

    for name, func in SECTION_REGISTRY:
        if requested and name not in requested:
            continue
        try:
            func(col)
        except Exception as exc:
            col.begin_section(f"ERROR in {name}")
            col.add_output(f"Collector '{name}' failed: {exc}")
            col.end_section(f"ERROR in {name}")

    if not requested or "rocm" in requested:
        try:
            collect_rocm_install(col, rocm_path)
        except Exception as exc:
            col.begin_section("ERROR in rocm")
            col.add_output(f"ROCm collector failed: {exc}")
            col.end_section("ERROR in rocm")

    if not requested or "gpu" in requested:
        try:
            collect_gpu_diagnostics(col, rocm_path)
        except Exception as exc:
            col.begin_section("ERROR in gpu")
            col.add_output(f"GPU collector failed: {exc}")
            col.end_section("ERROR in gpu")

    if args.json:
        print(col.to_json())

    if not args.json:
        print()
        print(f"=== ROCm X TechSupport Log Collection Complete: V{VERSION} ===")
        print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
