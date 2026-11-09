use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).expect("failed to read stdin");

    let mut counts: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut total: u64 = 0;
    let mut current: Vec<u8> = Vec::new();

    for &b in &input {
        if b.is_ascii_alphabetic() {
            current.push(b.to_ascii_lowercase());
        } else if !current.is_empty() {
            total += 1;
            *counts.entry(std::mem::take(&mut current)).or_insert(0) += 1;
        }
    }
    if !current.is_empty() {
        total += 1;
        *counts.entry(std::mem::take(&mut current)).or_insert(0) += 1;
    }

    let unique = counts.len();
    let mut entries: Vec<(Vec<u8>, u64)> = counts.into_iter().collect();
    entries.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "words {} unique {}", total, unique).expect("write failed");
    for (word, count) in entries.iter().take(20) {
        out.write_all(word).expect("write failed");
        writeln!(out, " {}", count).expect("write failed");
    }
    out.flush().expect("flush failed");
}
