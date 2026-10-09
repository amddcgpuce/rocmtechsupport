# ROCm TechSupport Log Collection Utilities

Tools for collecting system, GPU, ROCm, and network diagnostic logs for AMD ROCm environments.

---

## rocmx_techsupport.py — ROCm X (TheRock 10.x) [NEW]

Python-based log collector for **TheRock 10.x** releases (ROCm 10.x). Supports tarball, pip-installed, and Docker container ROCm deployments. Single file, no external dependencies — just Python 3.8+.

### Features

- **TheRock 10.x ROCm discovery** — auto-detects tarball, pip, and Docker installs
- **Dynamic GPU detection** — discovers GPUs via sysfs instead of hardcoded ranges
- **GPU architecture awareness** — identifies CDNA generation (CDNA3/CDNA4/CDNA5)
- **MI455/Helios stub** — placeholder for Helios rack-specific diagnostics
- **JSON output** — machine-readable output for automation pipelines
- **Section filtering** — run only the sections you need
- **Graceful degradation** — missing tools produce clear messages, never crash

### Quick Start

```bash
# Download
wget -O rocmx_techsupport.py https://raw.githubusercontent.com/amddcgpuce/rocmtechsupport/rewrite-for-therock/rocmx_techsupport.py

# Run (sudo recommended for full data capture)
sudo python3 rocmx_techsupport.py > $(hostname).$(date +%F-%H%M%S).rocmx.log 2>&1
```

### Usage

```bash
# Basic run — all sections, text output
sudo python3 rocmx_techsupport.py

# Specify ROCm path explicitly
python3 rocmx_techsupport.py --rocm-path /path/to/rocm

# JSON output
python3 rocmx_techsupport.py --json --output report.json

# Run only specific sections
python3 rocmx_techsupport.py --sections system,gpu,rocm

# Verbose mode (includes stderr from commands)
sudo python3 rocmx_techsupport.py --verbose
```

### Available Sections

| Section | Description |
|---------|-------------|
| `system` | OS, kernel, CPU, memory |
| `kernel_logs` | dmesg, journalctl with GPU/error filters |
| `hardware` | lshw, dmidecode, lspci, lstopo, modules |
| `rocm` | TheRock ROCm install, packages, env vars, ldconfig |
| `gpu` | amd-smi, rocm-smi, rocminfo, PCIe, KFD |
| `network` | IB, RDMA, ethtool, ip, OFED, niccli, lldp |
| `tuning` | tuned-adm, tuned.conf, nicctl |

### Notes

- **Without `sudo`**: certain data (dmidecode, lspci -vvv, ethtool) may not be captured
- **Enable persistent boot logs**: `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald.service`
- **ROCm auto-discovery**: checks `ROCM_PATH`/`ROCM_VERSION` env vars, then PATH, then common install locations

---

## rocm_techsupport.sh — Legacy (ROCm 3.x–6.x) V1.41

Shell utility for Ubuntu/CentOS/SLES bare metal or Docker container environments running traditional `/opt/rocm-*` package-based ROCm installations.

### Quick Start (Legacy)

```bash
# Download
wget -O rocm_techsupport.sh --no-cache --no-cookies --no-check-certificate \
  https://raw.githubusercontent.com/amddcgpuce/rocmtechsupport/master/rocm_techsupport.sh

# Run
sudo sh ./rocm_techsupport.sh > $(hostname).$(date +"%y-%m-%d-%H-%M-%S").rocm_techsupport.log 2>&1

# With specific ROCm version
sudo ROCM_VERSION=/opt/rocm-6.2.0 sh ./rocm_techsupport.sh > output.log 2>&1
```

### Notes (Legacy)

- **Enable persistent boot logs**: `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald.service`
- Use `ROCM_VERSION` environment variable to specify the ROCm install path
- Without `sudo`, certain data may not be captured but the script will still run

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for log interpretation and common issue diagnosis.

---

## Sharing Logs with AMD Support

1. Compress the output: `gzip *.rocmx.log` or `gzip *.rocm_techsupport.log`
2. Attach to your support ticket with:
   - Description of the problem
   - ROCm version
   - Any recent system changes
