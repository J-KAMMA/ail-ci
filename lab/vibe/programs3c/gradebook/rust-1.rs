use std::collections::HashMap;
use std::io::{self, Read, Write};

const MAX_SCORE: i64 = 1_000_000_000_000;

fn parse_score(s: &str) -> Option<i64> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut v: i64 = 0;
    for b in s.bytes() {
        v = v * 10 + (b - b'0') as i64;
        if v > MAX_SCORE {
            return None;
        }
    }
    Some(v)
}

fn main() {
    let mut raw = Vec::new();
    let _ = io::stdin().read_to_end(&mut raw);
    let text = String::from_utf8_lossy(&raw);

    let mut bad: u64 = 0;
    // name -> (count, sum)
    let mut stats: HashMap<String, (u64, i64)> = HashMap::new();

    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let tokens: Vec<&str> = line.split_whitespace().collect();
        if tokens.len() != 3 {
            bad += 1;
            continue;
        }
        match parse_score(tokens[2]) {
            None => {
                bad += 1;
            }
            Some(score) => {
                let e = stats.entry(tokens[0].to_string()).or_insert((0, 0));
                e.0 += 1;
                e.1 += score;
            }
        }
    }

    // (name, count, sum, avg)
    let mut rows: Vec<(String, u64, i64, i64)> = stats
        .into_iter()
        .map(|(name, (count, sum))| {
            let avg = sum / count as i64;
            (name, count, sum, avg)
        })
        .collect();

    rows.sort_by(|a, b| b.3.cmp(&a.3).then_with(|| a.0.cmp(&b.0)));

    let mut out = String::new();
    out.push_str(&format!("bad {}\n", bad));
    for (name, count, sum, avg) in &rows {
        out.push_str(&format!(
            "{} count {} sum {} avg {}\n",
            name, count, sum, avg
        ));
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
