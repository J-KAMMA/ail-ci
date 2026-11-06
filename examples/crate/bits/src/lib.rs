use tinydep::{popcount, rotate_left};

#[no_mangle]
pub extern "C" fn bits_popcount(x: u64) -> u32 {
    popcount(x)
}

#[no_mangle]
pub extern "C" fn bits_rotl(x: u32, n: u32) -> u32 {
    rotate_left(x, n)
}
