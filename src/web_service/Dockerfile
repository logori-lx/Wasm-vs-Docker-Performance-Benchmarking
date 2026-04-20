# ==========================================
# 阶段 1: 编译构建 (Builder)
# ==========================================
FROM rust:latest AS builder
WORKDIR /app

# 假设你的项目文件夹叫 web_bench，请根据实际情况调整
COPY web_bench . 
RUN cargo build --release

# ==========================================
# 阶段 2: 运行环境 (Runner)
# ==========================================
FROM debian:bookworm-slim

# 安装 time 工具用于性能抓取
RUN apt-get update && apt-get install -y time && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/web_bench /app/web_bench

# ⚠️ 关键新增：声明暴露 8080 端口
EXPOSE 8080

# 启动命令与 rsa_bench 保持同样的监控逻辑
# 当发送 curl http://localhost:8080/quit 时，进程结束，触发 time 结算和 cgroup 读取
CMD ["sh", "-c", "/usr/bin/time -v /app/web_bench 2>&1 && echo 'Cgroup_Peak_Memory_Bytes:' $(cat /sys/fs/cgroup/memory.peak)"]