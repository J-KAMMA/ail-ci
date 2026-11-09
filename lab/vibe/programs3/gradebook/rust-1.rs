use std::collections::HashMap;
use std::io::{self, Read, Write};

fn parse_score(token: &str) -> Option<i64> {
    if token.is_empty() {
        return None;
    }

    let mut value: u64 = 0;
    for b in token.bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        value = value.checked_mul(10)?.checked_add((b - b'0') as u64)?;
    }

    if value <= 1_000_000_000_000 {
        Some(value as i64)
    } else {
        None
    }
}

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();
    let input = String::from_utf8_lossy(&data);

    let mut stats: HashMap<String, (i64, i64)> = HashMap::new();
    let mut bad: i64 = 0;

    for line in input.lines() {
        let tokens: Vec<&str> = line.split_whitespace().collect();

        if tokens.is_empty() {
            continue;
        }

        if tokens.len() != 3 {
            bad += 1;
            continue;
        }

        let score = match parse_score(tokens[2]) {
            Some(score) => score,
            None => {
                bad += 1;
                continue;
            }
        };

        let entry = stats.entry(tokens[0].to_string()).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += score;
    }

    let mut rows: Vec<(String, i64, i64, i64)> = stats
        .into_iter()
        .map(|(name, (count, sum))| (name, count, sum, sum / count))
        .collect();

    rows.sort_by(|a, b| {
        b.3.cmp(&a.3)
            .then_with(|| a.0.as_bytes().cmp(b.0.as_bytes()))
    });

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "bad {}", bad).unwrap();
    for (name, count, sum, avg) in rows {
        writeln!(out, "{} count {} sum {} avg {}", name, count, sum, avg).unwrap();
    }
}
