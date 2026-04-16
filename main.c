#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

// 1. 定义一个 "小本本" (哈希表)
// Key 是 PID (u32)，Value 是起始时间戳 (u64)
BPF_HASH(start_time_map, u32, u64);

// 定义传给 Python 的数据结构
struct data_t {
    u32 pid;
    u64 latency_ns; // 冷启动延迟 (纳秒)
    char comm[TASK_COMM_LEN]; // 进程名
};

BPF_PERF_OUTPUT(events);

/* * 探针 1：挂载在系统调用 execve 的 "返回处" (kretprobe)
 * 为什么用 retprobe？因为进程成功创建后，bpf_get_current_comm 才能拿到新程序的名字
 */
int trace_execve_return(struct pt_regs *ctx) {
    // 获取全局进程 ID
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid >> 32;
    
    // 获取当前进程的名字
    char comm[TASK_COMM_LEN];
    bpf_get_current_comm(&comm, sizeof(comm));
    
    // === 核心过滤逻辑 ===
    // 在这里过滤掉系统噪音，只记录你们关心的进程！
    // 假设你们编译的原生二进制叫 "rsa_bench"，或者运行环境叫 "wasmedge"
    if (comm[0] == 'r' && comm[1] == 's' && comm[2] == 'a') {
        // 获取当前纳秒级时间戳
        u64 ts = bpf_ktime_get_ns();
        // 记录到哈希表中：start_time_map[pid] = ts
        start_time_map.update(&pid, &ts);
    }
    
    return 0;
}

/* * 探针 2：挂载在你们 Rust 程序的 main 函数入口 (uprobe)
 */
int trace_rust_main(struct pt_regs *ctx) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid >> 32;
    
    // 拿着当前 PID 去 "小本本" 里查，看之前有没有记录过它的启动时间
    u64 *start_ts = start_time_map.lookup(&pid);
    
    // 如果查到了，说明这是我们正在追踪的测试进程！
    if (start_ts != NULL) {
        struct data_t data = {};
        data.pid = pid;
        // 核心计算：冷启动延迟 = 当前时间 - 进程被内核拉起的时间
        data.latency_ns = bpf_ktime_get_ns() - *start_ts;
        bpf_get_current_comm(&data.comm, sizeof(data.comm));
        
        // 将结果提交给 Python 用户态
        events.perf_submit(ctx, &data, sizeof(data));
        
        // 用完后清理哈希表，防止内存泄漏
        start_time_map.delete(&pid);
    }
    
    return 0;
}