## 📊 Performance Benchmarking Metrics

The following metrics are used to compare **WasmEdge** and **Docker** across various **AWS EC2 instance types**. Our evaluation focuses on cold start latency, memory footprint, and throughput.

| Metric Category | Performance Indicator | Description | Measurement Tool |
| :--- | :--- | :--- | :--- |
| **Latency** | **Cold Start Latency** | Time from trigger to first line of execution. | Python `time.perf_counter()` |
| | **Warm Start Latency** | Response time when environment is already initialized. | Custom Timing Scripts |
| | **Runtime Init Overhead** | Time spent on runtime setup and isolation layer. | Internal Log Timestamps |
| **Efficiency** | **Memory Footprint** | Peak Resident Set Size (RSS) during execution. | `/usr/bin/time -v` |
| | **Binary/Image Size** | Total size of the executable or container image. | `ls -lh` / `docker images` |
| | **CPU Utilization** | Average CPU load during intensive calculation. | `top` / `htop` / `mpstat` |
| **Throughput** | **Requests Per Sec (RPS)** | Maximum concurrent requests handled by web services. | `wrk` or `Apache Benchmark` |
| | **Processing Rate** | Data processed per second for batch tasks. | Custom Benchmarking Scripts |
| **Scalability** | **Resource Scaling** | Performance delta when moving from small to large EC2 instances. | Multi-Instance Comparison |

---

### 📝 Benchmarking Methodology
To ensure statistical significance and minimize noise in the AWS environment:
1. **Warm-up**: We perform 5-10 "warm-up" runs before recording data to ensure the system is in a stable state.
2. **Iterations**: Each test is repeated at least 100 times to calculate a reliable average.
3. **Statistical Analysis**: We report the Mean, Median, and Standard Deviation to identify specific performance factors and outliers.
4. **Environment Isolation**: Tests are conducted across multiple EC2 instance types to understand how performance scales with available CPU and memory resources.