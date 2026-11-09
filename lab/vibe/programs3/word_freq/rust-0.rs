use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        return;
    }

    let mut counts: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut total: u64 = 0;
    let mut word: Vec<u8> = Vec::new();

    for &b in &input {
        if b.is_ascii_alphabetic() {
            word.push(b.to_ascii_lowercase());
        } else if !word.is_empty() {
            total += 1;
            *counts.entry(std::mem::take(&mut word)).or_insert(0) += 1;
            word.clear();
        }
    }
    if !word.is_empty() {
        total += 1;
        *counts.entry(word).or_insert(0) += 1;
    }

    let unique = counts.len();
    let mut entries: Vec<(Vec<u8>, u64)> = counts.into_iter().collect();
    entries.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    let _ = writeln!(out, "words {} unique {}", total, unique);
    for (w, c) in entries.iter().take(20) {
        let _ = out.write_all(w);
        let _ = writeln!(out, " {}", c);
    }
    let _ = out.flush();
}
