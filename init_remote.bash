#!/bin/bash

# 1. install necessary dependencies
sudo apt update
sudo apt-get install -y bpfcc-tools python3-bpfcc linux-headers-$(uname -r) linux-tools-common linux-tools-$(uname -r) build-essential python3 docker.io python-is-python3

# 2. generate vmlinux.h
sudo bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h

# 3. install WasmEdge and source its environment variables
curl -sSf https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | bash
source $HOME/.wasmedge/env

# 4. install Rust environment
sudo snap install rustup --classic
rustup default stable
rustup target add wasm32-wasip1

