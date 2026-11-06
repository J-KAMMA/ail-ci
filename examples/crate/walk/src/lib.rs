pub type Step = extern "C" fn(step: i32) -> i32;

#[no_mangle]
pub unsafe extern "C" fn walk(n: i32, cb: Step) -> i32 {
    let mut total = 0i32;
    for step in 0..n {
        total = total.wrapping_add(cb(step));
    }
    total
}
