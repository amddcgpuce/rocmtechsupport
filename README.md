# rocm_techsupport.sh V1.34 Shell Utility for Ubuntu/CentOS/SLES/docker log collection from last 3 boots (please enable persistent boot logs.)
### NOTE: To enable persistent boot logs across reboots, please run:  
```
  sudo mkdir -p /var/log/journal
  sudo systemctl restart systemd-journald.service
```

### Download rocm_techsupport.sh shell script using:
***wget -O rocm_techsupport.sh --no-check-certificate https://raw.githubusercontent.com/amddcgpuce/rocmtechsupport/master/rocm_techsupport.sh*** 

### Example Usage (run with sudo preferred but not required):
```
mkdir  downloads
cd  downloads
wget -O rocm_techsupport.sh --no-check-certificate https://raw.githubusercontent.com/amddcgpuce/rocmtechsupport/master/rocm_techsupport.sh

# Redirect output to file with hostname and timestamp
sudo sh ./rocm_techsupport.sh > `hostname`.`date +"%y-%m-%d-%H-%M-%S"`.rocm_techsupport.log 2>&1

#Redirect output to file with SYSTEM_NAME_or_ISSUEID
sudo sh ./rocm_techsupport.sh > SYSTEM_NAME_or_ISSUEID.rocm_techsupport.log 2>&1

# Use ROCM_VERSION environment variable to specify which installed ROCm to use when
# collecting logs, for example, ROCM_VERSION=/opt/rocm-5.0.0 to use ROCm 5.0.0 GA version
# Use ROCM_VERSION to specify installed ROCM path and redirect output to a file with hostname and timestamp
sudo ROCM_VERSION=/opt/rocm-5.2.3 sh ./rocm_techsupport.sh > `hostname`.`date +"%y-%m-%d-%H-%M-%S"`.rocm_techsupport.log 2>&1

#Redirect output to file with SYSTEM_NAME_or_ISSUEID
sudo ROCM_VERSION=/opt/rocm-5.0.0 sh ./rocm_techsupport.sh > SYSTEM_NAME_or_ISSUE_ID.rocm_techsupport.log 2>&1

# Without sudo, certain data such as verbose lspci, dmidecode may not
# get captured in the logs

Compress/Zip the output file and include with reported issue.
```

