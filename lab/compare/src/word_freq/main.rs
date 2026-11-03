use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();
    let mut counts: HashMap<String, u64> = HashMap::new();
    let mut current = String::new();
    for &b in &data {
        if b.is_ascii_uppercase() {
            current.push((b + 32) as char);
        } else if b.is_ascii_lowercase() {
            current.push(b as char);
        } else if !current.is_empty() {
            *counts.entry(std::mem::take(&mut current)).or_insert(0) += 1;
        }
    }
    if !current.is_empty() {
        *counts.entry(current).or_insert(0) += 1;
    }
    let mut ranked: Vec<(String, u64)> = counts.into_iter().collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    let mut out = String::new();
    for (word, count) in ranked.iter().take(20) {
        out.push_str(&format!("{} {}\n", count, word));
    }
    io::stdout().write_all(out.as_bytes()).unwrap();
}
