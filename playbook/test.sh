#!/bin/bash
echo "=== 开始收集系统信息 ==="
echo "主机名: $(hostname)"
echo "当前时间: $(date)"
echo "系统运行时间: $(uptime -p)"
echo "=== 收集结束 ==="