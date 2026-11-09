use std::io::{self, Read, Write};

const LEVELS: [&str; 6] = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"];

fn main() {
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    let mut counts = [0usize; 6];
    let mut totals = [0usize; 6];
    let mut longest = [0usize; 6];
    let mut good = 0usize;
    let mut bad = 0usize;

    for raw in input.split('\n') {
        let line = raw.strip_suffix('\r').unwrap_or(raw);

        if line.is_empty() {
            continue;
        }

        if !line.starts_with('[') {
            bad += 1;
            continue;
        }

        let Some(close) = line[1..].find(']').map(|p| p + 1) else {
            bad += 1;
            continue;
        };

        let level = &line[1..close];
        let Some(idx) = LEVELS.iter().position(|&l| l == level) else {
            bad += 1;
            continue;
        };

        let rest = &line[close + 1..];
        let message = if rest.is_empty() {
            ""
        } else if let Some(m) = rest.strip_prefix(' ') {
            m
        } else {
            bad += 1;
            continue;
        };

        let len = message.chars().count();

        good += 1;
        counts[idx] += 1;
        totals[idx] += len;
        if len > longest[idx] {
            longest[idx] = len;
        }
    }

    let stdout = io::stdout();
    let mut out = stdout.lock();

    let _ = writeln!(out, "lines {} bad {}", good, bad);

    for (i, level) in LEVELS.iter().enumerate() {
        let _ = writeln!(
            out,
            "level {} count {} chars {} longest {}",
            level, counts[i], totals[i], longest[i]
        );
    }
}
