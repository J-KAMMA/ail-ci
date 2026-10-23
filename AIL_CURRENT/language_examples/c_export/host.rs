// A Rust host for libgeometry (built from geometry.py by `ail build --lib geometry`).
//
//   rustc host.rs -L outdir -l geometry -C link-arg=-Wl,-rpath,outdir -o host_rs
//
// It prints the same lines as host.c for the calls it makes, so test_ail_c_export.py compares them
// with the CPython results.
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_void};

#[repr(C)]
struct Point {
    x: i64,
    y: f64,
    visible: bool,
}

#[link(name = "geometry")]
extern "C" {
    fn geometry_last_error() -> *const c_char;
    fn geometry_free(data: *mut c_void);
    fn geometry_add(a: i64, b: i64, out: *mut i64) -> i32;
    fn geometry_divide(a: i64, b: i64, out: *mut i64) -> i32;
    fn geometry_shout(text: *const c_char, out: *mut *mut c_char) -> i32;
    fn geometry_squares(values: *const i64, n: usize, out: *mut *mut i64, out_len: *mut usize) -> i32;
    fn geometry_weight(p: *const Point, out: *mut f64) -> i32;
}

fn last_error() -> String {
    unsafe { CStr::from_ptr(geometry_last_error()).to_string_lossy().into_owned() }
}

fn kind_only(call: &str, status: i32) {
    let text = last_error();
    println!("{} = !{}", call, text.split(':').next().unwrap_or(""));
    assert_ne!(status, 0);
}

fn main() {
    unsafe {
        let mut i = 0i64;
        let status = geometry_add(2, 3, &mut i);
        println!("add(2, 3) = {}", if status == 0 { i.to_string() } else { "error".into() });

        let status = geometry_divide(7, 0, &mut i);
        if status != 0 { kind_only("divide(7, 0)", status) }

        let text = CString::new("h\u{e9}llo").unwrap();
        let mut shouted: *mut c_char = std::ptr::null_mut();
        let status = geometry_shout(text.as_ptr(), &mut shouted);
        assert_eq!(status, 0);
        println!("shout('h\u{e9}llo') = {}", CStr::from_ptr(shouted).to_str().unwrap());
        geometry_free(shouted as *mut c_void);

        let values = [1i64, 2, 3, 4];
        let mut squares: *mut i64 = std::ptr::null_mut();
        let mut n = 0usize;
        let status = geometry_squares(values.as_ptr(), values.len(), &mut squares, &mut n);
        assert_eq!(status, 0);
        let slice = std::slice::from_raw_parts(squares, n);
        let joined: Vec<String> = slice.iter().map(|v| format!(" {}", v)).collect();
        println!("squares([1, 2, 3, 4]) ={}", joined.concat());
        geometry_free(squares as *mut c_void);

        let shown = Point { x: 2, y: 1.5, visible: true };
        let mut weight = 0f64;
        let status = geometry_weight(&shown, &mut weight);
        assert_eq!(status, 0);
        println!("weight(Point(2, 1.5, True)) = {}", weight);
    }
}
