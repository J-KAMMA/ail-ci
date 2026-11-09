use std::env;
use std::ffi::OsString;
use std::process;

fn parse_dec(s: &str, max: u64) -> Option<u64> {
    if s.is_empty() {
        return None;
    }
    let mut v: u64 = 0;
    for b in s.bytes() {
        if !(b'0'..=b'9').contains(&b) {
            return None;
        }
        let d = (b - b'0') as u64;
        v = v.checked_mul(10)?.checked_add(d)?;
        if v > max {
            return None;
        }
    }
    Some(v)
}

fn fmt9(x: f64) -> String {
    let s = format!("{:.9}", x);
    if s.starts_with('-') && s[1..].bytes().all(|b| b == b'0' || b == b'.') {
        s[1..].to_string()
    } else {
        s
    }
}

fn to_str_arg(a: &OsString) -> Option<&str> {
    a.to_str()
}

fn main() {
    let args: Vec<OsString> = env::args_os().collect();
    if args.len() != 4 {
        process::exit(1);
    }
    let a1 = match to_str_arg(&args[1]) {
        Some(s) => s,
        None => process::exit(1),
    };
    let a2 = match to_str_arg(&args[2]) {
        Some(s) => s,
        None => process::exit(1),
    };
    let a3 = match to_str_arg(&args[3]) {
        Some(s) => s,
        None => process::exit(1),
    };

    let n = match parse_dec(a1, 10_000_000) {
        Some(v) if v >= 1 => v as usize,
        _ => process::exit(1),
    };
    let t = match parse_dec(a2, 1_000_000) {
        Some(v) => v,
        None => process::exit(1),
    };
    let seed = match parse_dec(a3, u64::MAX) {
        Some(v) => v,
        None => process::exit(1),
    };

    let mut h = vec![0.0f64; n];
    let mut x: u64 = seed;
    for i in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let v = ((x >> 33) % 2001) as i64 - 1000;
        h[i] = v as f64 / 64.0;
    }

    for s in 1..=t {
        if s % 2 == 1 {
            for i in 0..n {
                let l = h[(i + n - 1) % n];
                let r = h[(i + 1) % n];
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let l = h[(i + n - 1) % n];
                let r = h[(i + 1) % n];
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        }
    }

    let mut sum: f64 = 0.0;
    let mut energy: f64 = 0.0;
    let mut mn = h[0];
    let mut mx = h[0];
    for i in 0..n {
        sum = sum + h[i];
        let t_diff = h[(i + 1) % n] - h[i];
        energy = energy + t_diff * t_diff;
        if h[i] < mn {
            mn = h[i];
        }
        if h[i] > mx {
            mx = h[i];
        }
    }

    let mut out = String::new();
    out.push_str(&format!("sum {}\n", fmt9(sum)));
    out.push_str(&format!("energy {}\n", fmt9(energy)));
    out.push_str(&format!("min {}\n", fmt9(mn)));
    out.push_str(&format!("max {}\n", fmt9(mx)));
    out.push_str(&format!("first {}\n", fmt9(h[0])));
    out.push_str(&format!("middle {}\n", fmt9(h[n / 2])));
    out.push_str(&format!("last {}\n", fmt9(h[n - 1])));
    print!("{}", out);
    process::exit(0);
}
