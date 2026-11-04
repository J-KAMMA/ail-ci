#[no_mangle]
pub unsafe extern "C" fn rle_encode(src: *const u8, n: usize, dst: *mut u8, room: usize) -> isize {
    let mut written = 0usize;
    let mut index = 0usize;
    while index < n {
        let value = *src.add(index);
        let mut run = 1usize;
        while index + run < n && *src.add(index + run) == value && run < 255 {
            run += 1;
        }
        if written + 2 > room {
            return -1;
        }
        *dst.add(written) = value;
        *dst.add(written + 1) = run as u8;
        written += 2;
        index += run;
    }
    written as isize
}
