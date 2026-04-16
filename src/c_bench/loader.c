// loader.c
#include <stdio.h>
#include <stdbool.h>
#include <bpf/libbpf.h>
#include "cold_start.skel.h" 

// 1. 修复：在用户态代码中显式定义 event_t，必须与 BPF 代码完全一致
struct event_t {
    __u32 pid;
    __u64 latency_ns;
    char comm[16];
};

// 回调函数：处理内核传来的 Perf 事件
void handle_event(void *ctx, int cpu, void *data, __u32 data_sz) {
    struct event_t *e = data;
    printf("PID: %d | Comm: %s | Latency: %.3f ms\n", 
           e->pid, e->comm, e->latency_ns / 1000000.0);
}

int main(int argc, char **argv) {
    struct cold_start_bpf *skel;
    int err;

    // 1. 打开并加载 eBPF 程序 (Skeleton API)
    skel = cold_start_bpf__open_and_load();
    if (!skel) {
        fprintf(stderr, "加载 BPF 骨架失败\n");
        return 1;
    }

    // 2. 挂载 kprobe (系统调用)
    err = cold_start_bpf__attach(skel);
    // 修复：检查 err，消除警告
    if (err) {
        fprintf(stderr, "附加 kprobe 失败\n");
        cold_start_bpf__destroy(skel);
        return 1;
    }
    LIBBPF_OPTS(bpf_uprobe_opts, uprobe_opts,
        .func_name = "main", // <--- 填入你想追踪的函数名（和 Python 里填的一致）
        .retprobe = true     // <--- true 表示 uretprobe，false 表示 uprobe
    );

    skel->links.trace_rust_main = bpf_program__attach_uprobe_opts(
        skel->progs.trace_rust_main,
        -1,                                                      // 所有 PID
        "/home/lx/wasm/src/rsa_bench/target/release/rsa_bench",  // 真实路径
        0,                                                       // <--- 偏移量填 0！因为我们用了 func_name
        &uprobe_opts
    );

    // 4. 修复：适配新版 libbpf API，使用 perf_buffer_opts 结构体
    struct perf_buffer_opts pb_opts = {
        .sample_cb = handle_event,
    };
    
    struct perf_buffer *pb = perf_buffer__new(bpf_map__fd(skel->maps.events), 8, &pb_opts);
    if (!pb) {
        fprintf(stderr, "创建 perf buffer 失败\n");
        cold_start_bpf__destroy(skel);
        return 1;
    }
    
    printf("🚀 C 版本探针已运行，正在监听...\n");
    while (true) {
        perf_buffer__poll(pb, 100);
    }

    // 清理资源
    perf_buffer__free(pb);
    cold_start_bpf__destroy(skel);
    return 0;
}