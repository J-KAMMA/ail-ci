use std::collections::{HashMap, HashSet};
use std::io::{self, Read, Write};

const LIMIT: i128 = 1_000_000_000_000;

fn parse_amount(s: &str) -> Option<i128> {
    if s.is_empty() {
        return None;
    }
    let mut v: i128 = 0;
    for b in s.bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        v = v.saturating_mul(10).saturating_add((b - b'0') as i128);
        if v > LIMIT {
            return None;
        }
    }
    Some(v)
}

fn main() {
    let mut input = Vec::new();
    let _ = io::stdin().read_to_end(&mut input);
    let text = String::from_utf8_lossy(&input);

    let mut bad: u64 = 0;
    let mut balances: HashMap<String, i128> = HashMap::new();

    for line in text.lines() {
        let tokens: Vec<&str> = line.split_whitespace().collect();
        if tokens.is_empty() {
            continue;
        }
        if tokens.len() < 3 {
            bad += 1;
            continue;
        }

        let amount = match parse_amount(tokens[1]) {
            Some(a) => a,
            None => {
                bad += 1;
                continue;
            }
        };

        let participants = &tokens[2..];
        let mut seen: HashSet<&str> = HashSet::new();
        let mut repeated = false;
        for p in participants {
            if !seen.insert(*p) {
                repeated = true;
                break;
            }
        }
        if repeated {
            bad += 1;
            continue;
        }

        let k = participants.len() as i128;
        let q = amount / k;
        let r = amount % k;

        *balances.entry(tokens[0].to_string()).or_insert(0) += amount;
        for (i, p) in participants.iter().enumerate() {
            let owes = if (i as i128) < r { q + 1 } else { q };
            *balances.entry((*p).to_string()).or_insert(0) -= owes;
        }
    }

    let mut names: Vec<String> = balances.keys().cloned().collect();
    names.sort();

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    let _ = writeln!(out, "bad {}", bad);

    let mut total: i128 = 0;
    for name in &names {
        let net = balances[name];
        total += net;
        let _ = writeln!(out, "balance {} {}", name, net);
    }

    let _ = writeln!(out, "total {}", total);
}
