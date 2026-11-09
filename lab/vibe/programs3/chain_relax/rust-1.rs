use std::env;
use std::ffi::OsString;
use std::io::{self, Write};
use std::process;

fn parse_u64(s: &str) -> Option<u64> {
    if s.is_empty() {
        return None;
    }

    let mut value: u64 = 0;
    for &b in s.as_bytes() {
        if b < b'0' || b > b'9' {
            return None;
        }
        let digit = (b - b'0') as u64;
        value = value.checked_mul(10)?;
        value = value.checked_add(digit)?;
    }

    Some(value)
}

fn format_number(value: f64) -> String {
    let s = format!("{:.9}", value);
    if s.starts_with('-') && s[1..].bytes().all(|b| b == b'0' || b == b'.') {
        "0.000000000".to_string()
    } else {
        s
    }
}

fn main() {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    if args.len() != 3 {
        process::exit(1);
    }

    let n_str = match args[0].to_str() {
        Some(s) => s,
        None => process::exit(1),
    };
    let t_str = match args[1].to_str() {
        Some(s) => s,
        None => process::exit(1),
    };
    let seed_str = match args[2].to_str() {
        Some(s) => s,
        None => process::exit(1),
    };

    let n_value = match parse_u64(n_str) {
        Some(v) => v,
        None => process::exit(1),
    };
    if n_value < 1 || n_value > 10_000_000 {
        process::exit(1);
    }

    let t_value = match parse_u64(t_str) {
        Some(v) => v,
        None => process::exit(1),
    };
    if t_value > 1_000_000 {
        process::exit(1);
    }

    let seed = match parse_u64(seed_str) {
        Some(v) => v,
        None => process::exit(1),
    };

    let n = n_value as usize;
    let t = t_value as usize;

    let mut x = seed;
    let mut h: Vec<f64> = Vec::with_capacity(n);

    for _ in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let value = ((x >> 33) % 2001) as i64 - 1000;
        h.push((value as f64) / 64.0);
    }

    for sweep in 0..t {
        if sweep % 2 == 0 {
            for i in 0..n {
                let c = h[i];
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };

                let d = (l + r) - (c + c);
                let root = (d * d + 0.0625).sqrt();
                let g = d / (1.0 + root);
                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let c = h[i];
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };

                let d = (l + r) - (c + c);
                let root = (d * d + 0.0625).sqrt();
                let g = d / (1.0 + root);
                h[i] = c + 0.375 * g;
            }
        }
    }

    let mut sum = 0.0f64;
    let mut energy = 0.0f64;
    let mut minimum = h[0];
    let mut maximum = h[0];

    for i in 0..n {
        let current = h[i];
        sum = sum + current;

        let next = if i + 1 == n { h[0] } else { h[i + 1] };
        let diff = next - current;
        let square = diff * diff;
        energy = energy + square;

        if current < minimum {
            minimum = current;
        }
        if current > maximum {
            maximum = current;
        }
    }

    let output = format!(
        "sum {}\nenergy {}\nmin {}\nmax {}\nfirst {}\nmiddle {}\nlast {}\n",
        format_number(sum),
        format_number(energy),
        format_number(minimum),
        format_number(maximum),
        format_number(h[0]),
        format_number(h[n / 2]),
        format_number(h[n - 1])
    );

    let stdout = io::stdout();
    let mut out = stdout.lock();
    out.write_all(output.as_bytes()).unwrap();
}
