#!/bin/sh
# Copyright (c) 2022 Advanced Micro Devices, Inc. All Rights Reserved.
#
# rocm_techsupport.sh
# This script collects ROCm and system logs on a Debian OS installation.
# It requires 'sudo' supervisor privileges for some log collection
# such as dmidecode, dmesg, lspci -vvv to read capabilities.
# Author: srinivasan.subramanian@amd.com
# Revision: V1.35
# V1.35: grep amdfwflash
# V1.34: grep watchdog
# V1.33: Remove dockerchk
# V1.32: Revert section broken in SLES15
# V1.31: Removed mlxconfig query commands
# V1.30: added log capture for Mellanox NIC
#        updated PCIe link status to include GPU v-bridge 
# V1.29: check 5.0 version
# V1.28: add timestamp
# V1.27: grab repo setup info
# V1.26: grep amdgpu-dkms packages (new in 4.5)
# V1.25: grab amdgpu udev rules, lsinitrd/ramfs
# V1.24: add dkms status
# V1.23: add 4.0 check
# V1.22: workaround ROCm 3.9 rocm-smi bug
# V1.21: fix 3.10 detect
# V1.20: check openmp-extras package install
# V1.19: support for 3.10 release
# V1.18: add pnp filter
# V1.17: dump pids /sys/class/kfd/kfd/proc/
# V1.16: Add nmi to grep, lspci -t
# V1.15: Add rdc ROCm package filter, env, ldcache
# V1.14: List PCIe current link width/speed
# V1.12: List available ROCm versions under /opt
# V1.11: Run dmesg in addition to journalctl
# V1.10: get ROCm related ldconf entries
# V1.9: Add kfd to message filter
# V1.8: Add vfio to message filter
# V1.7: Check persistent logging status
#       add panic, oop, fail, xgmi to grep filter
# V1.6: In docker, use dmesg
# V1.5: Add error and fault to system log filter
# V1.4: Collect logs from the last 3 boots
#       Add power to grep
# V1.3: Add rocm-bandwidth-test -t to get topology
# V1.2: Add ECC and rask_mask
#       Show ras info, xgmierr
# V1.1: Detect OS type
#       Check paths for lspci, lshw
# V1.0: Initial version
#
echo "=== ROCm TechSupport Log Collection Utility: V1.35 ==="
/bin/date

ret=`/bin/grep -i -E 'debian|ubuntu' /etc/os-release`
if [ $? -ne 0 ]
then
    pkgtype="rpm"
else
    pkgtype="deb"
fi
echo "===== Section: OS Distribution         ==============="
# Print OS type
/bin/uname -a
# OS release
/bin/cat /etc/os-release

# Kernel boot parameters
echo "===== Section: Kernel Boot Parameters  ==============="
/bin/cat /proc/cmdline

# System log related to GPU
echo "===== Section: dmesg GPU/DRM/ATOM/BIOS ==============="
if [ -f /var/log/journal ]
then
    echo "Persistent logging enabled."
else
    echo "WARNING: Persistent logging possibly disabled."
    echo "WARNING: Please run: "
    echo "       sudo mkdir -p /var/log/journal "
    echo "       sudo systemctl restart systemd-journald.service "
    echo "WARNING: to enable persistent boot logs for collection and analysis."
fi

if [ -f /bin/journalctl ]
then
    echo "Section: dmesg boot logs"
    /bin/dmesg -T | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Current boot logs"
    /bin/journalctl -b | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Previous boot logs"
    /bin/journalctl -b -1 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Second Previous boot logs"
    /bin/journalctl -b -2 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Third Previous boot logs"
    /bin/journalctl -b -3 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
elif [ -f /usr/bin/journalctl ]
then
    echo "Section: dmesg boot logs"
    /bin/dmesg -T | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Current boot logs"
    /usr/bin/journalctl -b | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Previous boot logs"
    /usr/bin/journalctl -b -1 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Second Previous boot logs"
    /usr/bin/journalctl -b -2 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "Section: Third Previous boot logs"
    /usr/bin/journalctl -b -3 | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
else
    echo "Section: dmesg boot logs"
    /bin/dmesg -T | /bin/grep -i -E ' Linux v| Command line|power|pnp|pci|gpu|drm|error|xgmi|panic|watchdog|bug|nmi|dazed|too|oop|fail|fault|atom|bios|kfd|vfio|iommu|ras_mask|ECC|smpboot.*CPU|pcieport.*AER|amdfwflash'
    echo "ROCmTechSupportNotFound: journalctl utility not found!"
fi

# CPU information
echo "===== Section: CPU Information         ==============="
/usr/bin/lscpu

# Memory information
echo "===== Section: Memory Information      ==============="
/usr/bin/lsmem

# Hardware Information
echo "===== Section: Hardware Information    ==============="
if [ -f /usr/bin/lshw ]
then
    /usr/bin/lshw
elif [ -f /usr/sbin/lshw ]
then
    /usr/sbin/lshw
elif [ -f /sbin/lshw ]
then
    /sbin/lshw
else
    echo "Note: Install lshw to get lshw hardware listing information"
    echo "    Ex: sudo apt install lshw "
    echo "ROCmTechSupportNotFound: lshw utility not found!"
fi

# Kernel Modules loaded
echo "===== Section: lsmod loaded module     ==============="
/sbin/lsmod

# amdgpu modinfo
echo "===== Section: amdgpu modinfo          ==============="
/sbin/modinfo amdgpu

# dkms status
echo "===== Section: dkms status             ==============="
/usr/sbin/dkms status

# amdgpu udev rules
echo "===== Section: amdgpu udev rule        ==============="
cat /etc/udev/rules.d/70-amdgpu.rules

# lsinitrd or lsinitramfs dump
echo "===== Section: lsinitrd lsinitramfs    ==============="
if [ "$pkgtype" = "deb" ]
then
    /usr/bin/lsinitramfs /boot/initrd.img-$(/bin/uname -r)
else
    sudo /usr/bin/lsinitrd
fi

# Hardware Topology
echo "===== Section: Hardware Topology       ==============="
if [ -f /usr/bin/lstopo-no-graphics ]
then
    /usr/bin/lstopo-no-graphics
else
    echo "lstopo command not found. Skipping hardware topology information."
    echo "Note: Install hwloc to get lstopo hardware topology information"
    echo "    Ex: sudo apt install hwloc "
fi

# DMIdecode information - BIOS etc
echo "===== Section: dmidecode Information   ==============="
/usr/sbin/dmidecode

# PCI peripheral information
echo "===== Section: lspci verbose output    ==============="
if [ -f /usr/bin/lspci ]
then
    /usr/bin/lspci -vvvt
    /usr/bin/lspci -vvv
elif [ -f /usr/sbin/lspci ]
then
    /usr/sbin/lspci -vvvt
    /usr/sbin/lspci -vvv
elif [ -f /sbin/lspci ]
then
    /sbin/lspci -vvvt
    /sbin/lspci -vvv
else
    echo "ROCmTechSupportNotFound: lspci utility not found!"
fi

# Print ROCm repo setup
echo "===== Section: ROCm Repo Setup         ==============="
/bin/grep -i -E 'rocm|amdgpu' /etc/apt/sources.list.d/* /etc/zypp/repos.d/* /etc/yum.repos.d/*

# Print ROCm installed packages
echo "===== Section: ROCm Packages Installed ==============="
if [ "$pkgtype" = "deb" ]
then
    /usr/bin/dpkg -l | /bin/grep -i -E 'ocl-icd|kfdtest|llvm-amd|miopen|half|^ii  hip|hcc|hsa|rocm|atmi|^ii  comgr|aomp|amdgpu|rock|mivision|migraph|rocprofiler|roctracer|rocbl|hipify|rocsol|rocthr|rocff|rocalu|rocprim|rocrand|rccl|rocspar|rdc|openmp|amdfwflash|ocl|opencl' | /usr/bin/sort
else
    /usr/bin/rpm -qa | /bin/grep -i -E 'ocl-icd|kfdtest|llvm-amd|miopen|half|hip|hcc|hsa|rocm|atmi|comgr|aomp|amdgpu|rock|mivision|migraph|rocprofiler|roctracer|rocblas|hipify|rocsol|rocthr|rocff|rocalu|rocprim|rocrand|rccl|rocspar|rdc|openmp|amdfwflash|ocl|opencl' | /usr/bin/sort
fi

# Log ROCm related ldconfig entries
echo "===== Section: ROCm ldconfig entries   ==============="
/bin/grep -i -E 'rocm' /etc/ld.so.conf.d/*

# Dump ROCm cached ldconfig entries
echo "===== Section: ROCm ldcache entries      ============="
ldconfig -p | /bin/grep -i -E 'rocm'

# Dump ROCm related environmental variables
echo "===== Section: ROCm environment variables============="
env | /bin/grep -i -E 'rocm|hsa|hip|mpi|openmp|ucx|miopen'

# Select latest ROCM installed version: only supports 3.1 or newer
echo "===== Section: Available ROCm versions ==============="
if [ "$ROCM_VERSION"x = "x" ]; then
    /bin/ls -v -d /opt/rocm*
    ROCM_VERSION=`/bin/ls -v -d /opt/rocm-[3-5]* | /usr/bin/tail -1`
    if [ "$ROCM_VERSION"x = "x" ]
    then
        ROCM_VERSION=`/bin/ls -v -d /opt/rocm* | /usr/bin/tail -1`
    fi
fi 
echo "==== Using $ROCM_VERSION to collect ROCm information.==== "

# RBT Topology
echo "===== Section: rocm-bandwidth-test Topology       ==============="
if [ -f $ROCM_VERSION/bin/rocm-bandwidth-test ]
then
    $ROCM_VERSION/bin/rocm-bandwidth-test -t
else
    echo "$ROCM_VERSION/bin/rocm-bandwidth-test command not found. Skipping topology information."
    echo "Note: Install rocb=m-bandwidth-test ROCm package to get topology information"
    echo "    Ex: sudo apt install rocm-bandwidth-test "
fi

# ROCm SMI 
echo "===== Section: ROCm SMI                ==============="
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi
else
    echo " $ROCM_VERSION/bin/rocm-smi NOT FOUND !!! "
fi

# ROCm SMI - FW version
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    echo "===== Section: ROCm SMI showhw         ==============="
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi --showhw
fi

# ROCm PCIe Clock
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    echo "===== Section: ROCm SMI pcieclk clock  ==============="
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi -c | /bin/grep -i -E 'pcie'
fi

    echo "===== Section: GPU PCIe Link Config    ==============="
for i in $(seq 0 8)
do
    echo "GPU $i PCIe Link Width Speed: "
    cat /sys/class/drm/card$i/device/current_link_width
    cat /sys/class/drm/card$i/device/current_link_speed
done

    echo "===== Section: KFD PIDs sysfs kfd proc ==============="
ls /sys/class/kfd/kfd/proc/

# ROCm SMI - RAS info
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    echo "===== Section: ROCm SMI showrasinfo all==============="
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi --showrasinfo all
fi

# ROCm SMI - xgmierr
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    echo "===== Section: ROCm SMI showxgmierr    ==============="
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi --showxgmierr
fi

# ROCm SMI - FW version clocks etc.
if [ -f $ROCM_VERSION/bin/rocm-smi ]
then
    echo "===== Section: ROCm SMI clocks         ==============="
    LD_LIBRARY_PATH=$ROCM_VERSION/lib:$LD_LIBRARY_PATH $ROCM_VERSION/bin/rocm-smi -cga
fi

# ROCm Agent Information
if [ -f $ROCM_VERSION/bin/rocminfo ]
then
    echo "===== Section: rocminfo                ==============="
    $ROCM_VERSION/bin/rocminfo
fi

# OpenCL Agent Information
if [ -f $ROCM_VERSION/opencl/bin/x86_64/clinfo ]
then
    echo "===== Section: clinfo                  ==============="
    $ROCM_VERSION/opencl/bin/x86_64/clinfo
fi
# path in 3.5
if [ -f $ROCM_VERSION/opencl/bin/clinfo ]
then
    echo "===== Section: clinfo                  ==============="
    $ROCM_VERSION/opencl/bin/clinfo
fi

# This section added to capture NIC configuration


echo "===== Section: NVIDIA Mellanox Info    ==============="
# Show NUMA hardware topology
if [ -f /usr/bin/numactl ]
then
    /usr/bin/numactl -H
else
    echo "Note: Install numactl to get numa hardware listing information"
    echo "    Ex: sudo apt install numactl "
    echo "ROCmTechSupportNotFound: numactl utility not found!"
fi

echo "===== Section: NVIDIA Mellanox IB output    ==============="
# Show IB status information
if [ -f /usr/bin/ibstat ]
then
    /usr/bin/ibstat
elif [ -f /usr/sbin/ibstat ]
then
    /usr/sbin/ibstat
elif [ -f /sbin/ibstat ]
then
    /sbin/ibstat
else
    echo "ROCmTechSupportNotFound: ibstat not found!"
fi

# Show IB Device information
if [ -f /usr/bin/ibv_devinfo ]
then
    /usr/bin/ibv_devinfo
elif [ -f /usr/sbin/ibv_devinfo ]
then
    /usr/sbin/ibv_devinfo
elif [ -f /sbin/ibv_devinfo ]
then
    /sbin/ibv_devinfo
else
    echo "ROCmTechSupportNotFound: ibv_devinfo not found!"
fi

# Show IB device to Ethernet device information
if [ -f /usr/bin/ibdev2netdev ]
then
    /usr/bin/ibdev2netdev
    /usr/bin/ibdev2netdev -v

elif [ -f /usr/sbin/ibdev2netdev ]
then
    /usr/sbin/ibdev2netdev
    /usr/sbin/ibdev2netdev -v
elif [ -f /sbin/ibdev2netdev ]
then
    /sbin/ibdev2netdev
    /sbin/ibdev2netdev -v
else
    echo "ROCmTechSupportNotFound: ibdev2netdev not found!"
fi

# Show Mellanox OFED Information
if [ -f /usr/bin/ofed_info ]
then
    /usr/bin/ofed_info -s
else
    echo "Note: Install Mellanox OFED to get Mellanox OFED information"
    echo "ROCmTechSupportNotFound: ofed_info not found!"
fi

# Show Mellanox MST information
echo "===== Section: NVIDIA Mellanox Software Tools output    ==============="
if [ -f /usr/bin/mst ]
then
    sudo /usr/bin/mst start
    sudo /usr/bin/mst status -v
else
    echo "Note: Install Mellanox OFED to get Mellanox Software Tools information"
    echo "ROCmTechSupportNotFound: mst not found!"
fi

echo "===== Section: Ethernet IP ADDR information    ==============="
# Ethernet IP Information
if [ -f /usr/bin/ip ]
then
    /usr/bin/ip addr

elif [ -f /usr/sbin/ip ]
then
    /usr/sbin/ip addr
elif [ -f /sbin/ip ]
then
    /sbin/ip addr
else
    echo "ROCmTechSupportNotFound: ip command not found!"
fi
