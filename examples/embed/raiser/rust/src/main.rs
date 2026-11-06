// A Rust caller for examples/embed/raiser/libraiser.a: the same lines test.c prints.
use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

extern "C" {
    fn raiser_init() -> c_int;
    fn raiser_shutdown();
    fn raiser_last_error() -> *const c_char;
    fn raiser_checked_div(a: i64, b: i64, out: *mut i64) -> c_int;
    fn raiser_require_positive(n: i64, out: *mut i64) -> c_int;
}

fn last_error() -> String {
    unsafe { CStr::from_ptr(raiser_last_error()) }
        .to_string_lossy()
        .into_owned()
}

fn main() {
    unsafe { raiser_init() };
    let mut ok = true;
    let mut value: i64 = 0;

    let status = unsafe { raiser_checked_div(7, 2, &mut value) };
    println!("checked_div(7, 2) = {}", value);
    ok &= status == 0 && value == 3;

    let status = unsafe { raiser_checked_div(1, 0, &mut value) };
    if status == 1 && last_error() == "ValueError: division by zero" {
        println!("error: {}", last_error());
    } else {
        ok = false;
    }

    let status = unsafe { raiser_require_positive(-3, &mut value) };
    if status == 1 && last_error() == "ValueError: value must be positive" {
        println!("error: {}", last_error());
    } else {
        ok = false;
    }

    let status = unsafe { raiser_require_positive(5, &mut value) };
    println!("require_positive(5) = {}", value);
    ok &= status == 0 && value == 5;

    unsafe { raiser_shutdown() };
    if !ok {
        std::process::exit(1);
    }
}
