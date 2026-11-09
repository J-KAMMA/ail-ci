use std::io::{self, Read, Write};

const LEVELS: [&str; 6] = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"];

fn parse(line: &str) -> Option<(usize, usize)> {
    if !line.starts_with('[') {
        return None;
    }
    let close = line.find(']')?;
    let level_name = &line[1..close];
    let idx = LEVELS.iter().position(|&l| l == level_name)?;
    let rest = &line[close + 1..];
    let msg: &str = if rest.is_empty() {
        ""
    } else if let Some(stripped) = rest.strip_prefix(' ') {
        stripped
    } else {
        return None;
    };
    Some((idx, msg.chars().count()))
}

fn main() {
    let mut buf = Vec::new();
    let _ = io::stdin().read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);

    let mut count = [0usize; 6];
    let mut chars = [0usize; 6];
    let mut longest = [0usize; 6];
    let mut good: usize = 0;
    let mut bad: usize = 0;

    for raw in text.split('\n') {
        let line = raw.strip_suffix('\r').unwrap_or(raw);
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
            None => {
                bad += 1;
            }
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
    let _ = handle.write_all(out.as_bytes());
    let _ = handle.flush();
}
