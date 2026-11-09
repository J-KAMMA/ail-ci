use std::io::Write;
use std::process::exit;

fn parse_dec(s: &str) -> Option<u64> {
    let b = s.as_bytes();
    if b.is_empty() {
        return None;
    }
    let mut acc: u64 = 0;
    for &c in b {
        if !c.is_ascii_digit() {
            return None;
        }
        acc = acc.checked_mul(10)?.checked_add((c - b'0') as u64)?;
    }
    Some(acc)
}

fn fail() -> ! {
    exit(1)
}

fn fmt9(v: f64) -> String {
    let s = format!("{:.9}", v);
    if let Some(rest) = s.strip_prefix('-') {
        if rest.bytes().all(|b| b == b'0' || b == b'.') {
            return rest.to_string();
        }
    }
    s
}

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().skip(1).collect();
    if args.len() != 3 {
        fail();
    }
    let mut parsed = Vec::with_capacity(3);
    for a in &args {
        match a.to_str().and_then(parse_dec) {
            Some(v) => parsed.push(v),
            None => fail(),
        }
    }
    let n_u = parsed[0];
    let t_u = parsed[1];
    let seed = parsed[2];
    if n_u < 1 || n_u > 10_000_000 {
        fail();
    }
    if t_u > 1_000_000 {
        fail();
    }
    let n = n_u as usize;
    let t = t_u;

    // Initial heights
    let mut h: Vec<f64> = Vec::with_capacity(n);
    let mut x: u64 = seed;
    for _ in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let v = (((x >> 33) % 2001) as i64) - 1000;
        h.push(v as f64 / 64.0);
    }

    // Sweeps
    for s in 1..=t {
        if s % 2 == 1 {
            for i in 0..n {
                let li = (i + n - 1) % n;
                let ri = (i + 1) % n;
                let l = h[li];
                let r = h[ri];
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let li = (i + n - 1) % n;
                let ri = (i + 1) % n;
                let l = h[li];
                let r = h[ri];
                let c = h[i];
                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());
                h[i] = c + 0.375 * g;
            }
        }
    }

    // Summary
    let mut sum: f64 = 0.0;
    let mut energy: f64 = 0.0;
    let mut mn = h[0];
    let mut mx = h[0];
    for i in 0..n {
        sum = sum + h[i];
        let tt = h[(i + 1) % n] - h[i];
        energy = energy + tt * tt;
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

    let stdout = std::io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
    exit(0);
}
