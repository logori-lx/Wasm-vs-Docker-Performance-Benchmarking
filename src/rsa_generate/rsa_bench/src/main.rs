use rsa::RsaPrivateKey;
use rand::rngs::OsRng;
use std::time::Instant;

#[inline(never)]
#[no_mangle]
fn generate_rsa_key(rng: &mut OsRng, bits: usize) -> RsaPrivateKey {
    RsaPrivateKey::new(rng, bits).expect("RSA key generation failed")
}

fn main() {
    let mut rng = OsRng;
    let bits = 2048; 
    let start = Instant::now();
    let _priv_key = generate_rsa_key(&mut rng, bits);
    println!("RSA key generation completed.");
    let duration = start.elapsed();

    println!("Execution_Time_Micros: {}", duration.as_micros());
}