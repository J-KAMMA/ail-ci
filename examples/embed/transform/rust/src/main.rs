// A Rust caller for examples/embed/transform/libtransform.a: the same lines test.c prints.
use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

extern "C" {
    fn transform_init() -> c_int;
    fn transform_shutdown();
    fn transform_last_error() -> *const c_char;
    fn transform_transform(
        text: *const c_char,
        len: usize,
        out: *mut c_char,
        cap: usize,
        out_len: *mut usize,
    ) -> c_int;
}

fn last_error() -> String {
    unsafe { CStr::from_ptr(transform_last_error()) }
        .to_string_lossy()
        .into_owned()
}

fn show(value: &str, ok: &mut bool) {
    let mut out = [0u8; 64];
    let mut len: usize = 0;
    let status = unsafe {
        transform_transform(
            value.as_ptr() as *const c_char,
            value.len(),
            out.as_mut_ptr() as *mut c_char,
            out.len(),
            &mut len,
        )
    };
    if status != 0 {
        eprintln!("transform example: status {} for {}: {}", status, value, last_error());
        *ok = false;
        return;
    }
    let text = std::str::from_utf8(&out[..len]).expect("transform returns UTF-8");
    println!("transform(\"{}\") = \"{}\"", value, text);
}

fn main() {
    unsafe { transform_init() };
    let mut ok = true;
    for value in ["Hello World 42", "ail embed", "", "already UPPER", "héllo wörld"] {
        show(value, &mut ok);
    }

    let value = "Hello World 42";
    let mut small = [0u8; 4];
    let mut len: usize = 0;
    let status = unsafe {
        transform_transform(
            value.as_ptr() as *const c_char,
            value.len(),
            small.as_mut_ptr() as *mut c_char,
            small.len(),
            &mut len,
        )
    };
    if status != 2 || len != 14 {
        eprintln!("transform example: buffer-too-small status {} len {}", status, len);
        ok = false;
    }

    unsafe { transform_shutdown() };
    if !ok {
        std::process::exit(1);
    }
}
