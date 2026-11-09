use std::collections::{BTreeMap, HashSet};
use std::io::{self, Read, Write};

fn parse_amount(s: &str) -> Option<u64> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let trimmed = s.trim_start_matches('0');
    if trimmed.len() > 13 {
        return None;
    }
    let v: u64 = if trimmed.is_empty() {
        0
    } else {
        trimmed.parse().ok()?
    };
    if v > 1_000_000_000_000 {
        None
    } else {
        Some(v)
    }
}

fn main() {
    let mut buf = Vec::new();
    let _ = io::stdin().read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);

    let mut bad: u64 = 0;
    let mut bal: BTreeMap<String, i128> = BTreeMap::new();

    for line in text.lines() {
        let toks: Vec<&str> = line.split_whitespace().collect();
        if toks.is_empty() {
            continue;
        }
        if toks.len() < 3 {
            bad += 1;
            continue;
        }
        let amt = match parse_amount(toks[1]) {
            Some(a) => a,
            None => {
                bad += 1;
                continue;
            }
        };
        let parts = &toks[2..];
        let mut seen: HashSet<&str> = HashSet::new();
        if !parts.iter().all(|p| seen.insert(*p)) {
            bad += 1;
            continue;
        }
        let k = parts.len() as u64;
        let q = amt / k;
        let r = amt % k;

        *bal.entry(toks[0].to_string()).or_insert(0) += amt as i128;
        for (i, p) in parts.iter().enumerate() {
            let owe = q + if (i as u64) < r { 1 } else { 0 };
            *bal.entry(p.to_string()).or_insert(0) -= owe as i128;
        }
    }

    let mut out = String::new();
    out.push_str(&format!("bad {}\n", bad));
    let mut total: i128 = 0;
    for (name, v) in &bal {
        out.push_str(&format!("balance {} {}\n", name, v));
        total += *v;
    }
    out.push_str(&format!("total {}\n", total));

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let _ = handle.write_all(out.as_bytes());
    let _ = handle.flush();
}
