#!/usr/bin/python3
from bcc import BPF
import ctypes as ct
import statistics
import sys

# 测试配置参数
WARMUP_RUNS = 10
ITERATION_RUNS = 100
TOTAL_RUNS = WARMUP_RUNS + ITERATION_RUNS

bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

BPF_HASH(ts_exec, u32, u64);
BPF_HASH(ts_main, u32, u64);
BPF_HASH(ts_calc, u32, u64);

struct data_t {
    u32 pid;
    u64 cold_start_ns;
    u64 init_ns;
    u64 hot_calc_ns;
};

BPF_PERF_OUTPUT(events);

int trace_execve_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    char comm[TASK_COMM_LEN];
    bpf_get_current_comm(&comm, sizeof(comm));
    
    // 匹配 rsa_bench
    if (comm[0] == 'r' && comm[1] == 's' && comm[2] == 'a') {
        u64 ts = bpf_ktime_get_ns();
        ts_exec.update(&pid, &ts);
    }
    return 0;
}

int trace_rust_main(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    ts_main.update(&pid, &ts);
    return 0;
}

int trace_calc_enter(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    ts_calc.update(&pid, &ts);
    return 0;
}

int trace_calc_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *exec_ts = ts_exec.lookup(&pid);
    u64 *main_ts = ts_main.lookup(&pid);
    u64 *calc_ts = ts_calc.lookup(&pid);
    
    if (exec_ts && main_ts && calc_ts) {
        struct data_t data = {};
        data.pid = pid;
        data.cold_start_ns = *main_ts - *exec_ts;
        data.init_ns = *calc_ts - *main_ts;
        data.hot_calc_ns = bpf_ktime_get_ns() - *calc_ts;
        events.perf_submit(ctx, &data, sizeof(data));
    }
    
    ts_exec.delete(&pid);
    ts_main.delete(&pid);
    ts_calc.delete(&pid);
    return 0;
}
"""

print(f"正在加载 eBPF 探针... (预期收集 {TOTAL_RUNS} 条数据，其中 {WARMUP_RUNS} 条为 Warm-up)")
b = BPF(text=bpf_text)
b.attach_kretprobe(event=b.get_syscall_fnname("execve"), fn_name="trace_execve_return")

RUST_BINARY_PATH = "./src/rsa_bench/target/release/rsa_bench" 

try:
    b.attach_uprobe(name=RUST_BINARY_PATH, sym="main", fn_name="trace_rust_main")
    b.attach_uprobe(name=RUST_BINARY_PATH, sym="generate_rsa_key", fn_name="trace_calc_enter")
    b.attach_uretprobe(name=RUST_BINARY_PATH, sym="generate_rsa_key", fn_name="trace_calc_return")
except Exception as e:
    print(f"挂载失败！请检查路径 {RUST_BINARY_PATH}")
    sys.exit(1)

#用于存储收集到的所有数据
collected_data = []

def print_event(cpu, data, size):
    class Data(ct.Structure):
        _fields_ = [
            ("pid", ct.c_uint32),
            ("cold_start_ns", ct.c_uint64),
            ("init_ns", ct.c_uint64),
            ("hot_calc_ns", ct.c_uint64)
        ]
    event = ct.cast(data, ct.POINTER(Data)).contents
    
    collected_data.append({
        "cold_ms": event.cold_start_ns / 1_000_000.0,
        "init_ms": event.init_ns / 1_000_000.0,
        "calc_ms": event.hot_calc_ns / 1_000_000.0
    })
    
    current_count = len(collected_data)
    if current_count <= WARMUP_RUNS:
        print(f"Warm-up 进度: {current_count}/{WARMUP_RUNS} 丢弃记录...", end="\r")
    else:
        print(f"测量进度: {current_count - WARMUP_RUNS}/{ITERATION_RUNS}...", end="\r")

b["events"].open_perf_buffer(print_event)

print("就绪！请在另一个终端运行压测脚本 (run_bench.sh)")

#轮询直到收集满预期数量
while len(collected_data) < TOTAL_RUNS:
    try:
        b.perf_buffer_poll(timeout=100)
    except KeyboardInterrupt:
        print("\n被用户强行中断。")
        break

print("\n\n" + "="*60)
print(f"数据收集完毕！(总计: {len(collected_data)}, 剔除 Warm-up: {WARMUP_RUNS})")
print("="*60)

#数据切片：抛弃前 10 次 Warm-up
valid_data = collected_data[WARMUP_RUNS:]

if len(valid_data) == 0:
    print("有效样本数为 0，无法计算统计信息。")
    sys.exit(0)

cold_starts = [d["cold_ms"] for d in valid_data]
inits = [d["init_ms"] for d in valid_data]
calcs = [d["calc_ms"] for d in valid_data]

#打印最终统计学报表
print(f"{'Metric (ms)':<20} | {'Mean':<10} | {'Median':<10} | {'Std Dev':<10}")
print("-" * 60)
print(f"{'Cold Start (exec)':<20} | {statistics.mean(cold_starts):<10.3f} | {statistics.median(cold_starts):<10.3f} | {statistics.stdev(cold_starts):<10.3f}")
print(f"{'Init (main->calc)':<20} | {statistics.mean(inits):<10.3f} | {statistics.median(inits):<10.3f} | {statistics.stdev(inits):<10.3f}")
print(f"{'Hot Calc (RSA)':<20} | {statistics.mean(calcs):<10.3f} | {statistics.median(calcs):<10.3f} | {statistics.stdev(calcs):<10.3f}")
print("="*60)