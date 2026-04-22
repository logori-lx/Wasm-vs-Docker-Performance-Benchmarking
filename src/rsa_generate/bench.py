import subprocess
import re
import csv
import sys
import os  # 新增：用于检查 Wasm 文件是否存在，并读取文件大小

# ==========================================
# Configuration Parameters
# ==========================================
NUM_RUNS = 1                           # the number of experiment runs here
DOCKER_IMAGE_NAME = "rsa_bench_docker" # Your Docker image name
WASM_FILE_PATH = "rsa_bench.wasm"      # Your Wasm file path

# 负责读取 .wasm 文件大小，并统一转换成 MB
def get_wasm_file_size_mb(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Wasm file '{file_path}' not found.")
        sys.exit(1)
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)

# 负责读取 Docker image 的大小，并统一转换成 MB
def get_docker_image_size_mb(image_name):
    try:
        result = subprocess.run(
            ['sudo', 'docker', 'image', 'inspect', image_name, '--format', '{{.Size}}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print(f"Error: Failed to inspect Docker image '{image_name}'.")
            print(result.stderr)
            sys.exit(1)

        size_bytes = int(result.stdout.strip())
        return size_bytes / (1024 * 1024)

    except ValueError:
        print(f"Error: Unable to parse Docker image size for '{image_name}'.")
        print("Raw output:", result.stdout)
        sys.exit(1)


# --- 1. Execute system native commands and merge captured output ---
def run_benchmark_command(env_name, command_list, run_index, total_runs):
    print(f"[{run_index}/{total_runs}] Running benchmark: {env_name}...")
    try:
        result = subprocess.run(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Warning: '{env_name}' failed with exit code {result.returncode}.")
            print("--- Error Output ---")
            print(result.stdout)
            print("--------------------")
            sys.exit(1)
            
        return result.stdout

    except FileNotFoundError:
        print(f"Error: Command '{command_list[0]}' not found. Is it installed?")
        sys.exit(1)

# --- 2. Data parsing logic ---
def parse_time_to_seconds(time_str):
    parts = time_str.strip().split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return 0.0

def extract_metrics(log_text, is_docker=False):
    metrics = {}
    try:
        metrics['Exec_Micros'] = float(re.search(r"Execution_Time_Micros:\s*(\d+)", log_text).group(1))
        metrics['User_Time_s'] = float(re.search(r"User time \(seconds\):\s*([\d.]+)", log_text).group(1))
        metrics['Sys_Time_s'] = float(re.search(r"System time \(seconds\):\s*([\d.]+)", log_text).group(1))
        
        # 新增：从 /usr/bin/time -v 输出中提取 CPU 使用百分比
        metrics['CPU_Util_Percent'] = float(re.search(r"Percent of CPU this job got:\s*(\d+)%", log_text).group(1))

        elapsed_raw = re.search(r"Elapsed \(wall clock\) time .*?:\s*(.+)", log_text).group(1)
        metrics['Elapsed_s'] = parse_time_to_seconds(elapsed_raw)
        
        metrics['Max_RSS_KB'] = float(re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", log_text).group(1))
        metrics['Minor_Page_Faults'] = int(re.search(r"Minor \(reclaiming a frame\) page faults:\s*(\d+)", log_text).group(1))
        metrics['Vol_Ctx_Switches'] = int(re.search(r"Voluntary context switches:\s*(\d+)", log_text).group(1))
        
        if is_docker:
            cgroup_match = re.search(r"Cgroup_Peak_Memory_Bytes:\s*(\d+)", log_text)
            metrics['Cgroup_Peak_Bytes'] = float(cgroup_match.group(1)) if cgroup_match else 0
        else:
            metrics['Cgroup_Peak_Bytes'] = metrics['Max_RSS_KB'] * 1024 
            
    except AttributeError as e:
        print(f"Error parsing log data. The output format might have changed. Details: {e}")
        print("Raw Log:")
        print(log_text)
        sys.exit(1)
        
    # Calculate derived metrics
    metrics['Internal_Exec_Time_s'] = metrics['Exec_Micros'] / 1_000_000
    metrics['Inner_Cold_Start_s'] = max(0, metrics['Elapsed_s'] - metrics['Internal_Exec_Time_s'])
    metrics['Peak_Memory_MB'] = metrics['Cgroup_Peak_Bytes'] / (1024 * 1024)
    
    return metrics

# --- 3. Average calculation logic ---
def average_metrics(metrics_list):
    if not metrics_list:
        return {}
    
    avg_metrics = {}
    num_runs = len(metrics_list)
    
    for key in metrics_list[0].keys():
        total = sum(run[key] for run in metrics_list)
        avg_metrics[key] = total / num_runs
        
    return avg_metrics

if __name__ == "__main__":
    print(f"Starting End-to-End Performance Benchmark ({NUM_RUNS} Runs)...\n")

    docker_runs_data = []
    wasm_runs_data = []

    # The command to be executed
    docker_cmd = ['sudo','docker', 'run', '--rm', DOCKER_IMAGE_NAME]
    wasm_cmd = ['/usr/bin/time', '-v', 'wasmedge', WASM_FILE_PATH]

    # Loop NUM_RUNS times to execute the benchmark
    for i in range(1, NUM_RUNS + 1):
        print(f"--- Iteration {i} of {NUM_RUNS} ---")
        
        docker_log = run_benchmark_command('Docker', docker_cmd, i, NUM_RUNS)
        docker_metrics = extract_metrics(docker_log, is_docker=True)
        docker_runs_data.append(docker_metrics)
        
        wasm_log = run_benchmark_command('WasmEdge', wasm_cmd, i, NUM_RUNS)
        wasm_metrics = extract_metrics(wasm_log, is_docker=False)
        wasm_runs_data.append(wasm_metrics)
        
        print(f"Iteration {i} completed.\n")

    # Calculate the average of all runs
    print("Calculating averages across all runs...")
    docker_avg = average_metrics(docker_runs_data)
    wasm_avg = average_metrics(wasm_runs_data)

    docker_image_size_mb = get_docker_image_size_mb(DOCKER_IMAGE_NAME)   # 新增：在所有 benchmark 完成后，单独获取静态大小指标
    wasm_binary_size_mb = get_wasm_file_size_mb(WASM_FILE_PATH)

    # Print report
    print("="*65)
    print(f"PROJECT 5296: PERFORMANCE BENCHMARK REPORT (AVG OF {NUM_RUNS} RUNS)")
    print("="*65)
    
    # 新增：在终端打印的 markdown 报告中加入 Binary/Image Size和CPU Utilization 指标
    report_md = f"""
| Metric | Docker (Native) | WasmEdge (Interpreted) | Unit |
| :--- | :--- | :--- | :--- |
| **Execution Time** | {docker_avg['Internal_Exec_Time_s']:.4f} | {wasm_avg['Internal_Exec_Time_s']:.4f} | Seconds |
| **Inner Env Overhead** | {docker_avg['Inner_Cold_Start_s']:.4f} | {wasm_avg['Inner_Cold_Start_s']:.4f} | Seconds |
| **System Overhead** | {docker_avg['Sys_Time_s']:.4f} | {wasm_avg['Sys_Time_s']:.4f} | Seconds |
| **Peak Memory Footprint**| {docker_avg['Peak_Memory_MB']:.2f} | {wasm_avg['Peak_Memory_MB']:.2f} | MB |
| **Binary/Image Size** | {docker_image_size_mb:.2f} | {wasm_binary_size_mb:.2f} | MB |   
| **CPU Utilization** | {docker_avg['CPU_Util_Percent']:.1f} | {wasm_avg['CPU_Util_Percent']:.1f} | % |   
| **Minor Page Faults** | {docker_avg['Minor_Page_Faults']:.1f} | {wasm_avg['Minor_Page_Faults']:.1f} | Count |
| **Context Switches** | {docker_avg['Vol_Ctx_Switches']:.1f} | {wasm_avg['Vol_Ctx_Switches']:.1f} | Count |

*Note: Data generated dynamically. Values are averages across {NUM_RUNS} independent runs.*
    """
    print(report_md.strip())
    print("\n" + "="*65)

    # Export to CSV for plotting   # 新增：将 Binary/Image Size 和 CPU Utilization写入 CSV，便于后续画图和汇总分析 
    csv_filename = f"performance_comparison_{NUM_RUNS}_runs_avg.csv"
    fields = ['Metric', 'Docker_Avg', 'WasmEdge_Avg', 'Unit']
    rows = [
        ['Execution Time', round(docker_avg['Internal_Exec_Time_s'], 4), round(wasm_avg['Internal_Exec_Time_s'], 4), 'Seconds'],
        ['Inner Overhead', round(docker_avg['Inner_Cold_Start_s'], 4), round(wasm_avg['Inner_Cold_Start_s'], 4), 'Seconds'],
        ['System Time', round(docker_avg['Sys_Time_s'], 4), round(wasm_avg['Sys_Time_s'], 4), 'Seconds'],
        ['Peak Memory', round(docker_avg['Peak_Memory_MB'], 2), round(wasm_avg['Peak_Memory_MB'], 2), 'MB'],
        ['Binary/Image Size', round(docker_image_size_mb, 2), round(wasm_binary_size_mb, 2), 'MB'],
        ['CPU Utilization', round(docker_avg['CPU_Util_Percent'], 1), round(wasm_avg['CPU_Util_Percent'], 1), '%'],
        ['Minor Page Faults', round(docker_avg['Minor_Page_Faults'], 1), round(wasm_avg['Minor_Page_Faults'], 1), 'Count'],
        ['Context Switches', round(docker_avg['Vol_Ctx_Switches'], 1), round(wasm_avg['Vol_Ctx_Switches'], 1), 'Count']
    ]

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\nAveraged data successfully exported to '{csv_filename}'. Ready for plotting!")