use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        return;
    }

    const LEVEL_NAMES: [&str; 6] = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"];
    let mut counts = [0u64; 6];
    let mut chars = [0u64; 6];
    let mut longest = [0u64; 6];
    let mut good = 0u64;
    let mut bad = 0u64;

    for raw_line in input.split('\n') {
        let line = raw_line.strip_suffix('\r').unwrap_or(raw_line);
        if line.is_empty() {
            continue;
        }

        if !line.starts_with('[') {
            bad += 1;
            continue;
        }

        let close = match line[1..].find(']') {
            Some(offset) => offset + 1,
            None => {
                bad += 1;
                continue;
            }
        };

        let level = &line[1..close];
        let level_index = match LEVEL_NAMES.iter().position(|name| *name == level) {
            Some(index) => index,
            None => {
                bad += 1;
                continue;
            }
        };

        let rest = &line[close + 1..];
        let message = if rest.is_empty() {
            rest
        } else if rest.starts_with(' ') {
            &rest[1..]
        } else {
            bad += 1;
            continue;
        };

        let length = message.chars().count() as u64;
        counts[level_index] += 1;
        chars[level_index] += length;
        if length > longest[level_index] {
            longest[level_index] = length;
        }
        good += 1;
    }

    println!("lines {} bad {}", good, bad);
    for (index, name) in LEVEL_NAMES.iter().enumerate() {
        println!(
            "level {} count {} chars {} longest {}",
            name, counts[index], chars[index], longest[index]
        );
    }
}
