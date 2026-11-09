use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut input = Vec::new();
    let _ = io::stdin().read_to_end(&mut input);

    let mut bad: u64 = 0;
    let mut map: HashMap<Vec<u8>, (u64, i64)> = HashMap::new();

    for line in input.split(|&b| b == b'\n') {
        let toks: Vec<&[u8]> = line
            .split(|b| b.is_ascii_whitespace())
            .filter(|t| !t.is_empty())
            .collect();
        if toks.is_empty() {
            continue;
        }
        if toks.len() != 3 {
            bad += 1;
            continue;
        }
        let s = toks[2];
        if s.is_empty() || !s.iter().all(|c| c.is_ascii_digit()) {
            bad += 1;
            continue;
        }
        let mut v: u64 = 0;
        for &c in s {
            v = v
                .saturating_mul(10)
                .saturating_add((c - b'0') as u64);
        }
        if v > 1_000_000_000_000 {
            bad += 1;
            continue;
        }
        let e = map.entry(toks[0].to_vec()).or_insert((0, 0));
        e.0 += 1;
        e.1 += v as i64;
    }

    let mut rows: Vec<(i64, Vec<u8>, u64, i64)> = map
        .into_iter()
        .map(|(name, (c, s))| (s / (c as i64), name, c, s))
        .collect();

    rows.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));

    let mut out: Vec<u8> = Vec::new();
    out.extend_from_slice(format!("bad {}\n", bad).as_bytes());
    for (avg, name, c, s) in rows {
        out.extend_from_slice(&name);
        out.extend_from_slice(format!(" count {} sum {} avg {}\n", c, s, avg).as_bytes());
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
    let _ = lock.flush();
}
