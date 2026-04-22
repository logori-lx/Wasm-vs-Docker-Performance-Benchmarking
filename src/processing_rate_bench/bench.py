import subprocess
import re
import csv
import time
import sys

NUM_RUNS = 5
DOCKER_IMAGE = "processing_rate_bench_docker"
WASM_FILE = "processing_rate_bench.wasm"

def run_benchmark(env_name, command):
    print(f"Running {env_name}...")

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    stdout, _ = proc.communicate()
    return stdout

def extract_metrics(log):
    res = {}

    user_time = re.search(r"User time.*?:\s*([\d.]+)", log)
    res["user_time"] = float(user_time.group(1)) if user_time else 0

    sys_time = re.search(r"System time.*?:\s*([\d.]+)", log)
    res["sys_time"] = float(sys_time.group(1)) if sys_time else 0

    elapsed = re.search(r"Elapsed.*?:\s*([\d:.]+)", log)
    if elapsed:
        time_str = elapsed.group(1)
        parts = time_str.split(":")
        if len(parts) == 2:
            res["elapsed_s"] = float(parts[0])*60 + float(parts[1])
        else:
            res["elapsed_s"] = float(time_str)
    else:
        res["elapsed_s"] = 0

    rss = re.search(r"Maximum resident set size.*?:\s*(\d+)", log)
    res["max_rss_kb"] = int(rss.group(1)) if rss else 0

    rate = re.search(r"processing_rate=([\d.]+) ops/s", log)
    res["processing_rate"] = float(rate.group(1)) if rate else 0

    res["mem_mb"] = res["max_rss_kb"] / 1024
    return res

def avg(list):
    return sum(list) / len(list)

def main():
    docker_rates = []
    docker_times = []
    docker_mems = []

    wasm_rates = []
    wasm_times = []
    wasm_mems = []

    for i in range(NUM_RUNS):
        print(f"\n===== Run {i+1}/{NUM_RUNS} =====")

        # Docker
        log_d = run_benchmark("Docker", [
            "/usr/bin/time", "-v",
            "docker", "run", "--rm", DOCKER_IMAGE
        ])
        m_d = extract_metrics(log_d)
        docker_rates.append(m_d["processing_rate"])
        docker_times.append(m_d["elapsed_s"])
        docker_mems.append(m_d["mem_mb"])

        time.sleep(2)

        # WasmEdge
        log_w = run_benchmark("WasmEdge", [
            "/usr/bin/time", "-v",
            "wasmedge", WASM_FILE
        ])
        m_w = extract_metrics(log_w)
        wasm_rates.append(m_w["processing_rate"])
        wasm_times.append(m_w["elapsed_s"])
        wasm_mems.append(m_w["mem_mb"])

        time.sleep(2)

    d_rate = avg(docker_rates)
    d_time = avg(docker_times)
    d_mem = avg(docker_mems)

    w_rate = avg(wasm_rates)
    w_time = avg(wasm_times)
    w_mem = avg(wasm_mems)

    print("\n" + "="*60)
    print(" PROCESSING RATE BENCHMARK REPORT ")
    print("="*60)

    md = f"""
| Metric | Docker | WasmEdge | Unit |
| :--- | :--- | :--- | :--- |
| Processing Rate | {d_rate:.2f} | {w_rate:.2f} | ops/sec |
| Avg Time | {d_time:.3f} | {w_time:.3f} | sec |
| Peak Memory | {d_mem:.2f} | {w_mem:.2f} | MB |
    """
    print(md)

    # 输出 CSV
    with open("processing_rate_report.csv", "w") as f:
        w = csv.writer(f)
        w.writerow(["metric", "docker", "wasmedge", "unit"])
        w.writerow(["processing_rate", round(d_rate,2), round(w_rate,2), "ops/sec"])
        w.writerow(["time_sec", round(d_time,3), round(w_time,3), "sec"])
        w.writerow(["memory_mb", round(d_mem,2), round(w_mem,2), "MB"])

    print("\nCSV saved to: processing_rate_report.csv")

if __name__ == "__main__":
    main()
