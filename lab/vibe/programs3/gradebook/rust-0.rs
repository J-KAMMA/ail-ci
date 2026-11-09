use std::collections::HashMap;
use std::io::{self, Read, Write};

fn parse_score(token: &str) -> Option<u64> {
    const LIMIT: u64 = 1_000_000_000_000;

    if token.is_empty() {
        return None;
    }

    let mut value: u64 = 0;
    for byte in token.bytes() {
        if !byte.is_ascii_digit() {
            return None;
        }
        value = value * 10 + (byte - b'0') as u64;
        if value > LIMIT {
            return None;
        }
    }

    Some(value)
}

fn main() {
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    let mut bad: u64 = 0;
    let mut stats: HashMap<String, (u64, i64)> = HashMap::new();

    for line in input.lines() {
        let mut tokens = line.split_whitespace();

        let name = match tokens.next() {
            Some(name) => name,
            None => continue,
        };

        let _assignment = match tokens.next() {
            Some(assignment) => assignment,
            None => {
                bad += 1;
                continue;
            }
        };

        let score_token = match tokens.next() {
            Some(score) => score,
            None => {
                bad += 1;
                continue;
            }
        };

        if tokens.next().is_some() {
            bad += 1;
            continue;
        }

        let score = match parse_score(score_token) {
            Some(score) => score,
            None => {
                bad += 1;
                continue;
            }
        };

        let entry = stats.entry(name.to_string()).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += score as i64;
    }

    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());

    let _ = writeln!(output, "bad {}", bad);

    let mut rows: Vec<(String, u64, i64, i64)> = stats
        .into_iter()
        .map(|(name, (count, sum))| {
            let avg = sum / count as i64;
            (name, count, sum, avg)
        })
        .collect();

    rows.sort_by(|a, b| b.3.cmp(&a.3).then_with(|| a.0.cmp(&b.0)));

    for (name, count, sum, avg) in rows {
        let _ = writeln!(
            output,
            "{} count {} sum {} avg {}",
            name, count, sum, avg
        );
    }
}
