FROM rust:latest AS builder
WORKDIR  /app
COPY rsa_bench .
RUN cargo build --release
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y time && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/rsa_bench /app/rsa_bench
CMD ["sh", "-c", "/usr/bin/time -v /app/rsa_bench 2>&1 && echo 'Cgroup_Peak_Memory_Bytes:' $(cat /sys/fs/cgroup/memory.peak)"]