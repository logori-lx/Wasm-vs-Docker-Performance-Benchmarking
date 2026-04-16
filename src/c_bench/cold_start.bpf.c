// cold_start.bpf.c
#include "../../external/vmlinux.h" // 必须生成目标内核的数据结构头文件
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

// 定义一个哈希表记录启动时间
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, u32);
    __type(value, u64);
} start_time_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(key_size, sizeof(int));
    __uint(value_size, sizeof(int));
} events SEC(".maps");

struct event_t {
    u32 pid;
    u64 latency_ns;
    char comm[16];
};

SEC("kretprobe/__x64_sys_execve")
int trace_execve_return(struct pt_regs *ctx) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid >> 32;
    u64 ts = bpf_ktime_get_ns();
    
    // 这里需要更底层的辅助函数来读取 comm
    // 省略部分过滤逻辑...
    bpf_map_update_elem(&start_time_map, &pid, &ts, BPF_ANY);
    return 0;
}

// 注意：在 libbpf 中，uprobe 不在这里指定路径，而是在 C 的用户态代码中挂载
SEC("uprobe/trace_rust_main")
int trace_rust_main(struct pt_regs *ctx) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid >> 32;
    
    u64 *start_ts = bpf_map_lookup_elem(&start_time_map, &pid);
    if (start_ts) {
        struct event_t e = {};
        e.pid = pid;
        e.latency_ns = bpf_ktime_get_ns() - *start_ts;
        bpf_get_current_comm(&e.comm, sizeof(e.comm));
        
        bpf_perf_event_output(ctx, &events, BPF_F_CURRENT_CPU, &e, sizeof(e));
        bpf_map_delete_elem(&start_time_map, &pid);
    }
    return 0;
}

char LICENSE[] SEC("license") = "GPL";