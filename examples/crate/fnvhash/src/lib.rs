#[no_mangle]
pub extern "C" fn fnv1a64(p: *const u8, n: usize) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325u64;
    unsafe {
        for index in 0..n {
            hash ^= *p.add(index) as u64;
            hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    hash
}
