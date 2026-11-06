pub fn popcount(x: u64) -> u32 {
    x.count_ones()
}

pub fn rotate_left(x: u32, n: u32) -> u32 {
    x.rotate_left(n % 32)
}
