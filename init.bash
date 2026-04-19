# 本地机器
# 安装ansible
# 更新源
sudo apt update
# ansible依赖包安装
sudo apt install software-properties-common --yes
# ansible安装
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install ansible --yes





# 远程机器
sudo apt  update
sudo apt install python3
sudo apt install docker.io
sudo apt-get install -y bpfcc-tools python3-bpfcc linux-headers-$(uname -r) build-essential python-is-python3
sudo bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h
