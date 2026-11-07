use std::env;
use std::io::{self, BufWriter, Write};

fn parse_u64(s: &str) -> Option<u64> {
    if s.is_empty() {
        return None;
    }
    let mut val: u64 = 0;
    for b in s.bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        let d = (b - b'0') as u64;
        val = val.checked_mul(10)?.checked_add(d)?;
    }
    Some(val)
}

fn fmt9(v: f64) -> String {
    let s = format!("{:.9}", v);
    if let Some(rest) = s.strip_prefix('-') {
        if rest.bytes().all(|c| c == b'0' || c == b'.') {
            return "0.000000000".to_string();
        }
    }
    s
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() != 3 {
        std::process::exit(1);
    }

    let n = match parse_u64(&args[0]) {
        Some(v) if v >= 1 && v <= 10_000_000 => v as usize,
        _ => std::process::exit(1),
    };
    let t = match parse_u64(&args[1]) {
        Some(v) if v <= 1_000_000 => v as usize,
        _ => std::process::exit(1),
    };
    let seed = match parse_u64(&args[2]) {
        Some(v) => v,
        _ => std::process::exit(1),
    };

    let mut x = seed;
    let mut h: Vec<f64> = Vec::with_capacity(n);
    for _ in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let v = (((x >> 33) % 2001) as i64 - 1000) as f64;
        h.push(v / 64.0);
    }

    for s in 1..=t {
        if s & 1 == 1 {
            for i in 0..n {
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let l = if i == 0 { h[n - 1] } else { h[i - 1] };
                let r = if i + 1 == n { h[0] } else { h[i + 1] };
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        }
    }

    let mut sum = 0.0f64;
    let mut energy = 0.0f64;
    let mut mn = h[0];
    let mut mx = h[0];
    for i in 0..n {
        let c = h[i];
        sum += c;
        let nxt = if i + 1 == n { h[0] } else { h[i + 1] };
        let tt = nxt - c;
        energy += tt * tt;
        if c < mn {
            mn = c;
        }
        if c > mx {
            mx = c;
        }
    }

    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    let _ = writeln!(out, "sum {}", fmt9(sum));
    let _ = writeln!(out, "energy {}", fmt9(energy));
    let _ = writeln!(out, "min {}", fmt9(mn));
    let _ = writeln!(out, "max {}", fmt9(mx));
    let _ = writeln!(out, "first {}", fmt9(h[0]));
    let _ = writeln!(out, "middle {}", fmt9(h[n / 2]));
    let _ = writeln!(out, "last {}", fmt9(h[n - 1]));
    let _ = out.flush();
}
