import subprocess
import re
import csv
import sys
import time
import urllib.request
import urllib.error

NUM_RUNS = 1                  # Number of experiment runs
NUM_REQUESTS = 100            # Number of concurrent/loop requests sent per experiment
DOCKER_IMAGE_NAME = "web_bench_docker" # Docker image name
WASM_FILE_PATH = "web_bench.wasm"      # Wasm file path
SERVER_URL = "http://127.0.0.1:8080"   # Web service bind address

# --- 1. Execute resident service, perform stress test, and collect output ---
def run_web_benchmark(env_name, command_list, run_index, total_runs):
    print(f"[{run_index}/{total_runs}] Starting server: {env_name}...")
    
    # 1. Start service in the background (use Popen instead of run so Python doesn't block)
    try:
        proc = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    except FileNotFoundError:
        print(f"Error: Command '{command_list[0]}' not found.")
        sys.exit(1)

    # 2. Wait for the service to start and bind to the port
    time.sleep(2) 

    # 3. Apply HTTP load
    print(f"   Sending {NUM_REQUESTS} requests to {SERVER_URL}...")
    success_count = 0
    start_time = time.time()
    
    for _ in range(NUM_REQUESTS):
        try:
            # Send request to root route to trigger calculation task
            urllib.request.urlopen(f"{SERVER_URL}/", timeout=2).read()
            success_count += 1
        except urllib.error.URLError as e:
            print(f"   Request failed: {e}")

    load_time_s = time.time() - start_time
    print(f"   Finished {success_count}/{NUM_REQUESTS} requests in {load_time_s:.2f}s.")

    # 4. Send self-destruct command to trigger time -v settlement
    print(f"   Sending shutdown signal...")
    try:
        urllib.request.urlopen(f"{SERVER_URL}/quit", timeout=2).read()
    except Exception:
        pass # Expected behavior, the server disconnects directly

    # 5. Wait for the process to exit completely and capture all logs
    try:
        stdout, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"   Timeout waiting for {env_name} to exit. Force killing...")
        proc.kill()
        stdout, _ = proc.communicate()

    if proc.returncode not in [0, 137]: # Ignore normal 0 or force-killed codes
        print(f"Warning: '{env_name}' exited with code {proc.returncode}.")

    # Return full logs and stress test throughput
    req_per_sec = success_count / load_time_s if load_time_s > 0 else 0
    return stdout, req_per_sec

# --- 2. Data parsing logic (adjusted for Web services) ---
def parse_time_to_seconds(time_str):
    parts = time_str.strip().split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return 0.0

def extract_metrics(log_text, req_per_sec, is_docker=False):
    metrics = {}
    try:
        # Extract system-level metrics
        metrics['User_Time_s'] = float(re.search(r"User time \(seconds\):\s*([\d.]+)", log_text).group(1))
        metrics['Sys_Time_s'] = float(re.search(r"System time \(seconds\):\s*([\d.]+)", log_text).group(1))
        
        elapsed_raw = re.search(r"Elapsed \(wall clock\) time .*?:\s*(.+)", log_text).group(1)
        metrics['Elapsed_s'] = parse_time_to_seconds(elapsed_raw)
        
        metrics['Max_RSS_KB'] = float(re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", log_text).group(1))
        metrics['Minor_Page_Faults'] = int(re.search(r"Minor \(reclaiming a frame\) page faults:\s*(\d+)", log_text).group(1))
        metrics['Vol_Ctx_Switches'] = int(re.search(r"Voluntary context switches:\s*(\d+)", log_text).group(1))
        
        # Extract Docker's Cgroup memory metrics
        if is_docker:
            cgroup_match = re.search(r"Cgroup_Peak_Memory_Bytes:\s*(\d+)", log_text)
            metrics['Cgroup_Peak_Bytes'] = float(cgroup_match.group(1)) if cgroup_match else 0
        else:
            metrics['Cgroup_Peak_Bytes'] = metrics['Max_RSS_KB'] * 1024 
            
    except AttributeError as e:
        print(f"Error parsing log data. Format might have changed. Details: {e}")
        print("Raw Log:\n", log_text)
        sys.exit(1)
        
    # Calculate derived metrics
    metrics['Peak_Memory_MB'] = metrics['Cgroup_Peak_Bytes'] / (1024 * 1024)
    metrics['Req_Per_Sec'] = req_per_sec # New: Requests processed per second
    
    return metrics

# --- 3. Average calculation logic ---
def average_metrics(metrics_list):
    if not metrics_list: return {}
    avg_metrics = {}
    num_runs = len(metrics_list)
    for key in metrics_list[0].keys():
        total = sum(run[key] for run in metrics_list)
        avg_metrics[key] = total / num_runs
    return avg_metrics

if __name__ == "__main__":
    print(f"Starting WEB Server Performance Benchmark ({NUM_RUNS} Runs)...\n")

    docker_runs_data = []
    wasm_runs_data = []

    # Docker needs to map port 8080
    docker_cmd = ['sudo', 'docker', 'run', '--rm', '-p', '8080:8080', DOCKER_IMAGE_NAME]
    wasm_cmd = ['/usr/bin/time', '-v', 'wasmedge', WASM_FILE_PATH]

    for i in range(1, NUM_RUNS + 1):
        print(f"--- Iteration {i} of {NUM_RUNS} ---")
        
        # 1. Run Docker 
        docker_log, docker_rps = run_web_benchmark('Docker', docker_cmd, i, NUM_RUNS)
        docker_metrics = extract_metrics(docker_log, docker_rps, is_docker=True)
        docker_runs_data.append(docker_metrics)
        time.sleep(2) # Buffer time to ensure the port is completely released
        
        # 2. Run WasmEdge
        wasm_log, wasm_rps = run_web_benchmark('WasmEdge', wasm_cmd, i, NUM_RUNS)
        wasm_metrics = extract_metrics(wasm_log, wasm_rps, is_docker=False)
        wasm_runs_data.append(wasm_metrics)
        time.sleep(2) 
        
        print(f"Iteration {i} completed.\n")

    print("Calculating averages across all runs...")
    docker_avg = average_metrics(docker_runs_data)
    wasm_avg = average_metrics(wasm_runs_data)

    print("="*75)
    print(f"WEB SERVICE BENCHMARK REPORT (AVG OF {NUM_RUNS} RUNS)")
    print("="*75)
    
    report_md = f"""
| Metric | Docker (Native) | WasmEdge (WASI) | Unit |
| :--- | :--- | :--- | :--- |
| **Throughput** | {docker_avg['Req_Per_Sec']:.1f} | {wasm_avg['Req_Per_Sec']:.1f} | Req/sec |
| **Total Uptime** | {docker_avg['Elapsed_s']:.4f} | {wasm_avg['Elapsed_s']:.4f} | Seconds |
| **CPU User Time**| {docker_avg['User_Time_s']:.4f} | {wasm_avg['User_Time_s']:.4f} | Seconds |
| **CPU Sys Time** | {docker_avg['Sys_Time_s']:.4f} | {wasm_avg['Sys_Time_s']:.4f} | Seconds |
| **Peak Memory** | {docker_avg['Peak_Memory_MB']:.2f} | {wasm_avg['Peak_Memory_MB']:.2f} | MB |
| **Page Faults** | {docker_avg['Minor_Page_Faults']:.1f} | {wasm_avg['Minor_Page_Faults']:.1f} | Count |

*Note: Load triggered with {NUM_REQUESTS} sequential requests per run.*
    """
    print(report_md.strip())
    print("\n" + "="*75)

    csv_filename = f"web_performance_comparison_{NUM_RUNS}_runs_avg.csv"
    fields = ['Metric', 'Docker_Avg', 'WasmEdge_Avg', 'Unit']
    rows = [
        ['Throughput (RPS)', round(docker_avg['Req_Per_Sec'], 1), round(wasm_avg['Req_Per_Sec'], 1), 'Req/sec'],
        ['Total Uptime', round(docker_avg['Elapsed_s'], 4), round(wasm_avg['Elapsed_s'], 4), 'Seconds'],
        ['User CPU Time', round(docker_avg['User_Time_s'], 4), round(wasm_avg['User_Time_s'], 4), 'Seconds'],
        ['System CPU Time', round(docker_avg['Sys_Time_s'], 4), round(wasm_avg['Sys_Time_s'], 4), 'Seconds'],
        ['Peak Memory', round(docker_avg['Peak_Memory_MB'], 2), round(wasm_avg['Peak_Memory_MB'], 2), 'MB'],
        ['Minor Page Faults', round(docker_avg['Minor_Page_Faults'], 1), round(wasm_avg['Minor_Page_Faults'], 1), 'Count']
    ]

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)
    import shutil
    shutil.copyfile(csv_filename, "latest_web_report.csv")

    print(f"\nAveraged data successfully exported to '{csv_filename}'. Ready for plotting!")