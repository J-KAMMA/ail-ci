use std::collections::HashMap;

pub struct Bag {
    counts: HashMap<Vec<u8>, u64>,
}

fn key(p: *const u8, n: usize) -> Vec<u8> {
    if n == 0 {
        Vec::new()
    } else {
        unsafe { std::slice::from_raw_parts(p, n).to_vec() }
    }
}

#[no_mangle]
pub extern "C" fn wordbag_new() -> *mut Bag {
    Box::into_raw(Box::new(Bag { counts: HashMap::new() }))
}

#[no_mangle]
pub unsafe extern "C" fn wordbag_add(bag: *mut Bag, p: *const u8, n: usize) {
    if bag.is_null() {
        return;
    }
    let count = (*bag).counts.entry(key(p, n)).or_insert(0);
    *count = count.wrapping_add(1);
}

#[no_mangle]
pub unsafe extern "C" fn wordbag_bump(bag: *mut Bag, p: *const u8, n: usize, k: u64) {
    if bag.is_null() {
        return;
    }
    let count = (*bag).counts.entry(key(p, n)).or_insert(0);
    *count = count.wrapping_add(k);
}

#[no_mangle]
pub unsafe extern "C" fn wordbag_seed(bag: *mut Bag, p: *const u8, n: usize) {
    if bag.is_null() {
        return;
    }
    let count = (*bag).counts.entry(key(p, n)).or_insert(0);
    *count = 9223372036854775813u64;
}

#[no_mangle]
pub unsafe extern "C" fn wordbag_count(bag: *const Bag, p: *const u8, n: usize) -> u64 {
    if bag.is_null() {
        return 0;
    }
    (*bag).counts.get(&key(p, n)).copied().unwrap_or(0)
}

#[no_mangle]
pub unsafe extern "C" fn wordbag_free(bag: *mut Bag) {
    if !bag.is_null() {
        drop(Box::from_raw(bag));
    }
}
