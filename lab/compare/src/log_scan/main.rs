use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let mut data = String::new();
    io::stdin().read_to_string(&mut data).unwrap();
    let mut statuses: HashMap<String, u64> = HashMap::new();
    let mut hours: HashMap<u32, u64> = HashMap::new();
    for line in data.split('\n') {
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.splitn(4, ' ').collect();
        if parts.len() < 3 {
            continue;
        }
        let hour: u32 = parts[1][0..2].parse().unwrap_or(0);
        *statuses.entry(parts[2].to_string()).or_insert(0) += 1;
        *hours.entry(hour).or_insert(0) += 1;
    }
    let mut status_keys: Vec<String> = statuses.keys().cloned().collect();
    status_keys.sort();
    let mut hour_keys: Vec<u32> = hours.keys().cloned().collect();
    hour_keys.sort();
    let mut out = String::new();
    for status in status_keys {
        out.push_str(&format!("status {} {}\n", status, statuses[&status]));
    }
    for hour in hour_keys {
        out.push_str(&format!("hour {:02} {}\n", hour, hours[&hour]));
    }
    io::stdout().write_all(out.as_bytes()).unwrap();
}
