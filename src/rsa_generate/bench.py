import subprocess
import re
import csv
import sys

# ==========================================
# Configuration Parameters
# ==========================================
NUM_RUNS = 1                           # the number of experiment runs here
DOCKER_IMAGE_NAME = "rsa_bench_docker" # Your Docker image name
WASM_FILE_PATH = "rsa_bench.wasm"      # Your Wasm file path

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

    # Print report
    print("="*65)
    print(f"PROJECT 5296: PERFORMANCE BENCHMARK REPORT (AVG OF {NUM_RUNS} RUNS)")
    print("="*65)
    
    report_md = f"""
| Metric | Docker (Native) | WasmEdge (Interpreted) | Unit |
| :--- | :--- | :--- | :--- |
| **Execution Time** | {docker_avg['Internal_Exec_Time_s']:.4f} | {wasm_avg['Internal_Exec_Time_s']:.4f} | Seconds |
| **Inner Env Overhead** | {docker_avg['Inner_Cold_Start_s']:.4f} | {wasm_avg['Inner_Cold_Start_s']:.4f} | Seconds |
| **System Overhead** | {docker_avg['Sys_Time_s']:.4f} | {wasm_avg['Sys_Time_s']:.4f} | Seconds |
| **Peak Memory Footprint**| {docker_avg['Peak_Memory_MB']:.2f} | {wasm_avg['Peak_Memory_MB']:.2f} | MB |
| **Minor Page Faults** | {docker_avg['Minor_Page_Faults']:.1f} | {wasm_avg['Minor_Page_Faults']:.1f} | Count |
| **Context Switches** | {docker_avg['Vol_Ctx_Switches']:.1f} | {wasm_avg['Vol_Ctx_Switches']:.1f} | Count |

*Note: Data generated dynamically. Values are averages across {NUM_RUNS} independent runs.*
    """
    print(report_md.strip())
    print("\n" + "="*65)

    # Export to CSV for plotting
    csv_filename = f"performance_comparison_{NUM_RUNS}_runs_avg.csv"
    fields = ['Metric', 'Docker_Avg', 'WasmEdge_Avg', 'Unit']
    rows = [
        ['Execution Time', round(docker_avg['Internal_Exec_Time_s'], 4), round(wasm_avg['Internal_Exec_Time_s'], 4), 'Seconds'],
        ['Inner Overhead', round(docker_avg['Inner_Cold_Start_s'], 4), round(wasm_avg['Inner_Cold_Start_s'], 4), 'Seconds'],
        ['System Time', round(docker_avg['Sys_Time_s'], 4), round(wasm_avg['Sys_Time_s'], 4), 'Seconds'],
        ['Peak Memory', round(docker_avg['Peak_Memory_MB'], 2), round(wasm_avg['Peak_Memory_MB'], 2), 'MB'],
        ['Minor Page Faults', round(docker_avg['Minor_Page_Faults'], 1), round(wasm_avg['Minor_Page_Faults'], 1), 'Count'],
        ['Context Switches', round(docker_avg['Vol_Ctx_Switches'], 1), round(wasm_avg['Vol_Ctx_Switches'], 1), 'Count']
    ]

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)

    print(f"\nAveraged data successfully exported to '{csv_filename}'. Ready for plotting!")