use rsa::RsaPrivateKey;
use rand::rngs::OsRng;
use std::time::Instant;

// 必须保留，以便 eBPF 获取符号
#[inline(never)]
#[no_mangle]
fn generate_rsa_key(rng: &mut OsRng, bits: usize) -> RsaPrivateKey {
    RsaPrivateKey::new(rng, bits).expect("生成密钥失败")
}

fn main() {
    let mut rng = OsRng;
    let bits = 2048; 
    let _priv_key = generate_rsa_key(&mut rng, bits);
}