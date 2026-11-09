use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut data = Vec::new();
    if io::stdin().read_to_end(&mut data).is_err() {
        return;
    }

    let mut counts: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut total: u64 = 0;
    let n = data.len();
    let mut i = 0;

    while i < n {
        if data[i].is_ascii_alphabetic() {
            let start = i;
            while i < n && data[i].is_ascii_alphabetic() {
                i += 1;
            }
            let word: Vec<u8> = data[start..i]
                .iter()
                .map(|b| b.to_ascii_lowercase())
                .collect();
            *counts.entry(word).or_insert(0) += 1;
            total += 1;
        } else {
            i += 1;
        }
    }

    let unique = counts.len();

    let mut entries: Vec<(Vec<u8>, u64)> = counts.into_iter().collect();
    entries.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    let _ = writeln!(out, "words {} unique {}", total, unique);
    for (word, count) in entries.iter().take(20) {
        let _ = out.write_all(word);
        let _ = writeln!(out, " {}", count);
    }
    let _ = out.flush();
}
