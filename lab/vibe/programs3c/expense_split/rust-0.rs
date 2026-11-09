use std::collections::{BTreeMap, HashSet};
use std::fmt::Write as FmtWrite;
use std::io::{self, Read, Write};

fn parse_amount(s: &[u8]) -> Option<u64> {
    if s.is_empty() || !s.iter().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut v: u64 = 0;
    for &b in s {
        v = v * 10 + (b - b'0') as u64;
        if v > 1_000_000_000_000 {
            return None;
        }
    }
    Some(v)
}

fn main() {
    let mut buf = Vec::new();
    let _ = io::stdin().read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);

    let mut bad: u64 = 0;
    let mut bal: BTreeMap<String, i64> = BTreeMap::new();

    for raw in text.split('\n') {
        let tokens: Vec<&str> = raw
            .split(|c: char| c.is_ascii_whitespace())
            .filter(|t| !t.is_empty())
            .collect();

        if tokens.is_empty() {
            continue;
        }
        if tokens.len() < 3 {
            bad += 1;
            continue;
        }

        let amount = match parse_amount(tokens[1].as_bytes()) {
            Some(a) => a,
            None => {
                bad += 1;
                continue;
            }
        };

        let payer = tokens[0];
        let parts = &tokens[2..];

        let mut seen: HashSet<&str> = HashSet::new();
        if !parts.iter().all(|p| seen.insert(*p)) {
            bad += 1;
            continue;
        }

        let k = parts.len() as u64;
        let q = amount / k;
        let r = amount % k;

        *bal.entry(payer.to_string()).or_insert(0) += amount as i64;

        for (i, p) in parts.iter().enumerate() {
            let owed = q + if (i as u64) < r { 1 } else { 0 };
            *bal.entry(p.to_string()).or_insert(0) -= owed as i64;
        }
    }

    let mut out = String::new();
    let _ = writeln!(out, "bad {}", bad);
    let mut total: i64 = 0;
    for (name, v) in &bal {
        let _ = writeln!(out, "balance {} {}", name, v);
        total += *v;
    }
    let _ = writeln!(out, "total {}", total);

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let _ = handle.write_all(out.as_bytes());
    let _ = handle.flush();
}
