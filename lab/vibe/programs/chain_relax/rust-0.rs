use std::env;
use std::process;

fn parse_u64(s: &str) -> Option<u64> {
    if s.is_empty() {
        return None;
    }
    if !s.as_bytes().iter().all(|b| b.is_ascii_digit()) {
        return None;
    }
    s.parse::<u64>().ok()
}

fn fmt9(v: f64) -> String {
    let s = format!("{:.9}", v);
    let unsigned = s.strip_prefix('-').unwrap_or(&s);
    if unsigned.as_bytes().iter().all(|&b| b == b'0' || b == b'.') {
        "0.000000000".to_owned()
    } else {
        s
    }
}

fn main() {
    let mut args = Vec::new();
    for arg in env::args_os().skip(1) {
        match arg.into_string() {
            Ok(s) => args.push(s),
            Err(_) => process::exit(1),
        }
    }

    if args.len() != 3 {
        process::exit(1);
    }

    let n_u = match parse_u64(&args[0]) {
        Some(v) => v,
        None => process::exit(1),
    };
    let t_u = match parse_u64(&args[1]) {
        Some(v) => v,
        None => process::exit(1),
    };
    let seed = match parse_u64(&args[2]) {
        Some(v) => v,
        None => process::exit(1),
    };

    if n_u < 1 || n_u > 10_000_000 || t_u > 1_000_000 {
        process::exit(1);
    }

    let n = n_u as usize;
    let sweeps = t_u as usize;

    let mut h = vec![0.0f64; n];
    let mut x = seed;

    for i in 0..n {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let v = (((x >> 33) % 2001) as i64) - 1000;
        h[i] = (v as f64) / 64.0;
    }

    for s in 1..=sweeps {
        if s % 2 == 1 {
            for i in 0..n {
                let left = if i == 0 { n - 1 } else { i - 1 };
                let right = if i + 1 == n { 0 } else { i + 1 };

                let c = h[i];
                let l = h[left];
                let r = h[right];

                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());

                h[i] = c + 0.375 * g;
            }
        } else {
            for i in (0..n).rev() {
                let left = if i == 0 { n - 1 } else { i - 1 };
                let right = if i + 1 == n { 0 } else { i + 1 };

                let c = h[i];
                let l = h[left];
                let r = h[right];

                let d = (l + r) - (c + c);
                let g = d / (1.0 + (d * d + 0.0625).sqrt());

                h[i] = c + 0.375 * g;
            }
        }
    }

    let mut sum = 0.0f64;
    let mut energy = 0.0f64;
    let mut min = h[0];
    let mut max = h[0];

    for i in 0..n {
        let c = h[i];
        sum = sum + c;

        let right = if i + 1 == n { 0 } else { i + 1 };
        let t = h[right] - c;
        let t2 = t * t;
        energy = energy + t2;

        if c < min {
            min = c;
        }
        if c > max {
            max = c;
        }
    }

    let first = h[0];
    let middle = h[n / 2];
    let last = h[n - 1];

    let out = format!(
        "sum {}\nenergy {}\nmin {}\nmax {}\nfirst {}\nmiddle {}\nlast {}\n",
        fmt9(sum),
        fmt9(energy),
        fmt9(min),
        fmt9(max),
        fmt9(first),
        fmt9(middle),
        fmt9(last)
    );

    print!("{}", out);
}
