use std::collections::BTreeMap;
use std::io::{self, Read, Write};

fn main() {
    let mut input = Vec::new();
    let _ = io::stdin().read_to_end(&mut input);
    let text = String::from_utf8_lossy(&input).into_owned();

    let mut sections: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    let mut current = String::new();
    let mut bad: u64 = 0;

    for raw in text.split('\n') {
        let line = raw.strip_suffix('\r').unwrap_or(raw);
        let line = line.trim_matches(|c| c == ' ' || c == '\t');

        if line.is_empty() {
            continue;
        }

        let first = line.chars().next().unwrap();
        if first == '#' || first == ';' {
            continue;
        }

        if first == '[' {
            if line.ends_with(']') && line.len() >= 2 {
                let name = &line[1..line.len() - 1];
                current = name.to_string();
                sections.entry(current.clone()).or_insert_with(BTreeMap::new);
            } else {
                bad += 1;
            }
            continue;
        }

        match line.find('=') {
            Some(pos) => {
                let key = line[..pos].trim_matches(|c| c == ' ' || c == '\t');
                let value = line[pos + 1..].trim_matches(|c| c == ' ' || c == '\t');
                if key.is_empty() || key.contains(' ') || key.contains('\t') {
                    bad += 1;
                } else {
                    sections
                        .entry(current.clone())
                        .or_insert_with(BTreeMap::new)
                        .insert(key.to_string(), value.to_string());
                }
            }
            None => {
                bad += 1;
            }
        }
    }

    let mut out = String::new();
    out.push_str(&format!("bad {}\n", bad));
    for (name, entries) in &sections {
        out.push('[');
        out.push_str(name);
        out.push_str("]\n");
        for (k, v) in entries {
            out.push_str(k);
            out.push('=');
            out.push_str(v);
            out.push('\n');
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
}
