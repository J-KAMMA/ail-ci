use std::io::Write;

#[inline(always)]
fn step(l: f64, r: f64, c: f64) -> f64 {
    let d = (l + r) - (c + c);
    let g = d / (1.0 + (d * d + 0.0625).sqrt());
    c + 0.375 * g
}

fn parse(s: &str) -> Option<u64> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let t = s.trim_start_matches('0');
    if t.is_empty() {
        return Some(0);
    }
    t.parse::<u64>().ok()
}

fn fmt(x: f64) -> String {
    let s = format!("{:.9}", x);
    if s.bytes().all(|b| b == b'0' || b == b'.' || b == b'-') {
        return "0.000000000".to_string();
    }
    s
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 4 {
        std::process::exit(1);
    }
    let n = parse(&args[1]);
    let t = parse(&args[2]);
    let seed = parse(&args[3]);
    let (n, t, seed) = match (n, t, seed) {
        (Some(n), Some(t), Some(s)) if n >= 1 && n <= 10_000_000 && t <= 1_000_000 => (n as usize, t, s),
        _ => std::process::exit(1),
    };
    let mut h = vec![0.0f64; n];
    let mut x = seed;
    for i in 0..n {
        x = x.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        h[i] = (((x >> 33) % 2001) as i64 - 1000) as f64 / 64.0;
    }
    for s in 1..=t {
        if n == 1 {
            let c = h[0];
            h[0] = step(c, c, c);
        } else if s % 2 == 1 {
            let c0 = h[0];
            let n0 = step(h[n - 1], h[1], c0);
            h[0] = n0;
            let mut prev = n0;
            for i in 1..n - 1 {
                let c = h[i];
                let v = step(prev, h[i + 1], c);
                h[i] = v;
                prev = v;
            }
            h[n - 1] = step(prev, h[0], h[n - 1]);
        } else {
            let cl = h[n - 1];
            let nl = step(h[n - 2], h[0], cl);
            h[n - 1] = nl;
            let mut prev = nl;
            for i in (1..n - 1).rev() {
                let c = h[i];
                let v = step(h[i - 1], prev, c);
                h[i] = v;
                prev = v;
            }
            h[0] = step(h[n - 1], prev, h[0]);
        }
    }
    let mut sum = 0.0f64;
    let mut energy = 0.0f64;
    let mut mn = h[0];
    let mut mx = h[0];
    for i in 0..n {
        sum = sum + h[i];
        let tt = h[if i + 1 == n { 0 } else { i + 1 }] - h[i];
        energy = energy + tt * tt;
        if h[i] < mn {
            mn = h[i];
        }
        if h[i] > mx {
            mx = h[i];
        }
    }
    let out = format!(
        "sum {}\nenergy {}\nmin {}\nmax {}\nfirst {}\nmiddle {}\nlast {}\n",
        fmt(sum),
        fmt(energy),
        fmt(mn),
        fmt(mx),
        fmt(h[0]),
        fmt(h[n / 2]),
        fmt(h[n - 1])
    );
    std::io::stdout().write_all(out.as_bytes()).unwrap();
}
