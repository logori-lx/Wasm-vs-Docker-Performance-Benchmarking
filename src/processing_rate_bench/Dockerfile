FROM rust:latest AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y time && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/processing_rate_bench /app/processing_rate_bench

CMD ["sh", "-c", "/usr/bin/time -v /app/processing_rate_bench 2>&1 && echo Cgroup_Peak_Memory_Bytes: $(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)"]
