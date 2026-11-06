#[no_mangle]
pub unsafe extern "C" fn slugify(p: *const u8, n: usize, out: *mut u8, cap: usize) -> isize {
    let bytes = if n == 0 {
        &[][..]
    } else {
        std::slice::from_raw_parts(p, n)
    };
    let mut slug = Vec::with_capacity(n);
    let mut separator = false;
    for &byte in bytes {
        if byte.is_ascii_alphanumeric() {
            if separator && !slug.is_empty() {
                slug.push(b'-');
            }
            separator = false;
            slug.push(byte.to_ascii_lowercase());
        } else {
            separator = true;
        }
    }
    let needed = slug.len() + 1;
    if cap < needed {
        return -(needed as isize);
    }
    if needed > 1 {
        std::ptr::copy_nonoverlapping(slug.as_ptr(), out, slug.len());
    }
    *out.add(slug.len()) = 0;
    slug.len() as isize
}
