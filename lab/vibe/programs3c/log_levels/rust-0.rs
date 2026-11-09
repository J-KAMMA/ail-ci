use std::io::{self, Read, Write};

const LEVELS: [&str; 6] = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"];

fn parse(line: &[u8]) -> Option<(usize, u64)> {
    if line.first() != Some(&b'[') {
        return None;
    }
    let close = line.iter().position(|&b| b == b']')?;
    let level = &line[1..close];
    let idx = LEVELS.iter().position(|l| l.as_bytes() == level)?;
    let rest = &line[close + 1..];
    if rest.is_empty() {
        return Some((idx, 0));
    }
    if rest[0] != b' ' {
        return None;
    }
    let msg = &rest[1..];
    let s = String::from_utf8_lossy(msg);
    Some((idx, s.chars().count() as u64))
}

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();

    let mut count = [0u64; 6];
    let mut chars = [0u64; 6];
    let mut longest = [0u64; 6];
    let mut good: u64 = 0;
    let mut bad: u64 = 0;

    for raw in input.split(|&b| b == b'\n') {
        let mut line = raw;
        if let Some((&b'\r', rest)) = line.split_last() {
            line = rest;
        }
        if line.is_empty() {
            continue;
        }
        match parse(line) {
            Some((idx, len)) => {
                good += 1;
                count[idx] += 1;
                chars[idx] += len;
                if len > longest[idx] {
                    longest[idx] = len;
                }
            }
            None => bad += 1,
        }
    }

    let mut out = String::new();
    out.push_str(&format!("lines {} bad {}\n", good, bad));
    for i in 0..6 {
        out.push_str(&format!(
            "level {} count {} chars {} longest {}\n",
            LEVELS[i], count[i], chars[i], longest[i]
        ));
    }

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    handle.write_all(out.as_bytes()).unwrap();
    handle.flush().unwrap();
}
