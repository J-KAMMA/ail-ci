// A Rust caller for examples/embed/fib/libfib.a: the same lines test.c prints.
use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

extern "C" {
    fn fib_init() -> c_int;
    fn fib_shutdown();
    fn fib_last_error() -> *const c_char;
    fn fib_fib(n: i64, out: *mut i64) -> c_int;
    fn fib_gcd(a: i64, b: i64, out: *mut i64) -> c_int;
    fn fib_sum_line(text: *const c_char, len: usize, out: *mut i64) -> c_int;
}

fn last_error() -> String {
    unsafe { CStr::from_ptr(fib_last_error()) }
        .to_string_lossy()
        .into_owned()
}

fn main() {
    unsafe { fib_init() };
    let mut ok = true;
    let mut value: i64 = 0;

    let status = unsafe { fib_fib(0, &mut value) };
    println!("fib(0) = {}", value);
    ok &= status == 0 && value == 0;

    let status = unsafe { fib_fib(1, &mut value) };
    println!("fib(1) = {}", value);
    ok &= status == 0 && value == 1;

    let status = unsafe { fib_fib(10, &mut value) };
    println!("fib(10) = {}", value);
    ok &= status == 0 && value == 55;

    let status = unsafe { fib_fib(92, &mut value) };
    println!("fib(92) = {}", value);
    ok &= status == 0 && value == 7_540_113_804_746_346_429;

    let status = unsafe { fib_gcd(48, 18, &mut value) };
    println!("gcd(48, 18) = {}", value);
    ok &= status == 0 && value == 6;

    let status = unsafe { fib_gcd(-48, 18, &mut value) };
    println!("gcd(-48, 18) = {}", value);
    ok &= status == 0 && value == 6;

    let text = "a12 b34 c5";
    let status = unsafe { fib_sum_line(text.as_ptr() as *const c_char, text.len(), &mut value) };
    println!("sum_line(\"a12 b34 c5\") = {}", value);
    ok &= status == 0 && value == 51;

    let text = "no digits";
    let status = unsafe { fib_sum_line(text.as_ptr() as *const c_char, text.len(), &mut value) };
    println!("sum_line(\"no digits\") = {}", value);
    ok &= status == 0 && value == 0;

    let status = unsafe { fib_fib(93, &mut value) };
    if status != 1 || !last_error().starts_with("OverflowError: ") {
        eprintln!("fib example: fib(93) overflow is status {} {:?}", status, last_error());
        ok = false;
    }

    unsafe { fib_shutdown() };
    if !ok {
        std::process::exit(1);
    }
}
