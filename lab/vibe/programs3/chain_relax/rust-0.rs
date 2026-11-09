use std::env;
use std::ffi::OsStr;
use std::process;

fn parse_u64(s: &OsStr) -> Option<u64> {
    let text = s.to_str()?;
    if text.is_empty() || !text.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    text.parse::<u64>().ok()
}

fn format_value(value: f64) -> String {
    let s = format!("{:.9}", value);
    if s.starts_with('-') && s[1..].bytes().all(|b| b == b'0' || b == b'.') {
        s[1..].to_string()
    } else {
        s
    }
}

fn main() {
    let mut args = env::args_os();
    let _ = args.next();
    let rest: Vec<_> = args.collect();

    if rest.len() != 3 {
        process::exit(1);
    }

    let n_raw = match parse_u64(&rest[0]) {
        Some(v) => v,
        None => process::exit(1),
    };
    let t_raw = match parse_u64(&rest[1]) {
        Some(v) => v,
        None => process::exit(1),
    };
    let seed = match parse_u64(&rest[2]) {
        Some(v) => v,
        None => process::exit(1),
    };

    if n_raw < 1 || n_raw > 10_000_000 || t_raw > 1_000_000 {
        process::exit(1);
    }

    let n = n_raw as usize;
    let t = t_raw as usize;

    let mut x = seed;
    let mut h = vec![0.0f64; n];

    for i in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let v = ((x >> 33) % 2001) as i64 - 1000;
        h[i] = (v as f64) / 64.0;
    }

    for s in 1..=t {
        if s % 2 == 1 {
            for i in 0..n {
                let c = h[i];
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };

                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let c = h[i];
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };

                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        }
    }

    let mut sum = 0.0;
    let mut energy = 0.0;
    let mut min = h[0];
    let mut max = h[0];

    for i in 0..n {
        let c = h[i];
        sum = sum + c;

        let next = if i + 1 == n { h[0] } else { h[i + 1] };
        let diff = next - c;
        energy = energy + diff * diff;

        if c < min {
            min = c;
        }
        if c > max {
            max = c;
        }
    }

    println!("sum {}", format_value(sum));
    println!("energy {}", format_value(energy));
    println!("min {}", format_value(min));
    println!("max {}", format_value(max));
    println!("first {}", format_value(h[0]));
    println!("middle {}", format_value(h[n / 2]));
    println!("last {}", format_value(h[n - 1]));
}
