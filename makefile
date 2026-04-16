
cargo build --release



clang -target bpf -g -O2 -c cold_start.bpf.c -o cold_start.bpf.o
bpftool gen skeleton cold_start.bpf.o > cold_start.skel.h
gcc -g -O2 -Wall loader.c -lbpf -lelf -lz -o cold_start_monitor