use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut data = String::new();
    io::stdin().read_to_string(&mut data).unwrap();
    let mut totals: HashMap<String, i64> = HashMap::new();
    for line in data.split('\n') {
        if line.is_empty() {
            continue;
        }
        let mut parts = line.splitn(2, ',');
        let key = parts.next().unwrap_or("");
        let value: i64 = parts.next().unwrap_or("0").parse().unwrap_or(0);
        *totals.entry(key.to_string()).or_insert(0) += value;
    }
    let mut keys: Vec<String> = totals.keys().cloned().collect();
    keys.sort();
    let mut out = String::new();
    for key in keys {
        out.push_str(&format!("{},{}\n", key, totals[&key]));
    }
    io::stdout().write_all(out.as_bytes()).unwrap();
}
