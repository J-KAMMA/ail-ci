// A Rust caller for examples/embed/wordcount/libwordcount.a: the same lines test.c prints.
use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

extern "C" {
    fn wordcount_init() -> c_int;
    fn wordcount_shutdown();
    fn wordcount_last_error() -> *const c_char;
    fn wordcount_word_count(text: *const c_char, len: usize, out: *mut i64) -> c_int;
}

fn last_error() -> String {
    unsafe { CStr::from_ptr(wordcount_last_error()) }
        .to_string_lossy()
        .into_owned()
}

fn show(label: &str, text: &str, ok: &mut bool) {
    let mut count: i64 = 0;
    let status =
        unsafe { wordcount_word_count(text.as_ptr() as *const c_char, text.len(), &mut count) };
    if status != 0 {
        eprintln!("wordcount example: status {}: {}", status, last_error());
        *ok = false;
        return;
    }
    println!("word_count(\"{}\") = {}", label, count);
}

fn main() {
    unsafe { wordcount_init() };
    let mut ok = true;
    show("", "", &mut ok);
    show("one", "one", &mut ok);
    show("  one two\\tthree\\nfour  ", "  one two\tthree\nfour  ", &mut ok);
    show("a,b c-d", "a,b c-d", &mut ok);
    unsafe { wordcount_shutdown() };
    if !ok {
        std::process::exit(1);
    }
}
