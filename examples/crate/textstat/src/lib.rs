#[no_mangle]
pub unsafe extern "C" fn stats(p: *const u8, n: usize, out: *mut u64) -> i32 {
    let bytes = std::slice::from_raw_parts(p, n);
    let text = match std::str::from_utf8(bytes) {
        Ok(text) => text,
        Err(_) => return -1,
    };
    let lines = bytes.iter().filter(|&&byte| byte == b'\n').count()
        + if n > 0 && bytes[n - 1] != b'\n' { 1 } else { 0 };
    *out = lines as u64;
    *out.add(1) = text.split_whitespace().count() as u64;
    *out.add(2) = text.chars().count() as u64;
    0
}
