// 批处理任务：固定规模计算，用于测量 Processing Rate
// 处理速率 = 每秒完成的计算量 / 每秒处理的数据量

const DATA_SIZE: u64 = 10_000_000; // 1000万次计算（批处理规模）

fn main() {
    let start = std::time::Instant::now();

    let mut sum = 0u64;
    for i in 0..DATA_SIZE {
        sum = sum.wrapping_add(i);
    }

    let duration = start.elapsed().as_secs_f64();
    let processing_rate = DATA_SIZE as f64 / duration;

    println!("BATCH_RESULT: sum={}, duration={:.6}s, processing_rate={:.2} ops/s",
        sum, duration, processing_rate);
}
