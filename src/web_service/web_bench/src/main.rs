use std::io::{Read, Write};

#[cfg(target_arch = "wasm32")]
use wasmedge_wasi_socket::TcpListener;

#[cfg(not(target_arch = "wasm32"))]
use std::net::TcpListener;
// --------------------------------

fn main() {
    #[cfg(target_arch = "wasm32")]
    let listener = TcpListener::bind("0.0.0.0:8080", false).expect("WASM bind failed");
    
    #[cfg(not(target_arch = "wasm32"))]
    let listener = TcpListener::bind("0.0.0.0:8080").expect("Native bind failed");

    println!("Server is running on http://0.0.0.0:8080");

    for stream in listener.incoming() {
        let mut stream = match stream {
            Ok(s) => s,
            Err(e) => {
                println!("Connection failed: {}", e);
                continue;
            }
        };

        let mut buffer = [0; 1024];
        if let Ok(bytes_read) = stream.read(&mut buffer) {
            if bytes_read == 0 { continue; }

            let request = String::from_utf8_lossy(&buffer[..bytes_read]);

            if request.starts_with("GET /quit") {
                let response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nBye!\n";
                let _ = stream.write_all(response.as_bytes());
                break;
            } else {
                let mut sum: u64 = 0;
                for i in 1..=5_000_000 { sum = sum.wrapping_add(i); }

                let body = format!("Task finished! Result: {}\n", sum);
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(response.as_bytes());
            }
        }
    }
}