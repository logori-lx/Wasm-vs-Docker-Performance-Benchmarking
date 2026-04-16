#!/bin/bash

# 确保使用的是 release 编译的最新版本
WARMUP=10
ITERATIONS=100
TOTAL=$((WARMUP + ITERATIONS))
BINARY="./src/rsa_bench/target/release/rsa_bench" 

echo "🔥 开始自动压测，总执行次数: $TOTAL"

for i in $(seq 1 $TOTAL); do
    # > /dev/null 防止终端被 Rust 的 print 刷屏，影响系统 I/O 导致性能偏差
    $BINARY > /dev/null 2>&1
done

echo "✅ 压测执行完毕！请查看 Python 端的统计输出。"