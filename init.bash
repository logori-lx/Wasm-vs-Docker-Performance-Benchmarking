sudo apt  update
sudo apt install python3
sudo apt-get install -y bpfcc-tools python3-bpfcc linux-headers-$(uname -r) build-essential python-is-python3
sudo bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h