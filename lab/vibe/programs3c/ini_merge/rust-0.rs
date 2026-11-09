use std::collections::BTreeMap;
use std::io::{self, Read, Write};

fn trim_st(s: &str) -> &str {
    s.trim_matches(|c: char| c == ' ' || c == '\t')
}

fn main() {
    let mut buf = Vec::new();
    let _ = io::stdin().read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);

    let mut sections: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    let mut bad: u64 = 0;
    let mut current = String::new();

    for raw in text.split('\n') {
        let line = raw.strip_suffix('\r').unwrap_or(raw);
        let line = trim_st(line);
        if line.is_empty() {
            continue;
        }
        let first = match line.chars().next() {
            Some(c) => c,
            None => continue,
        };
        if first == '#' || first == ';' {
            continue;
        }
        if first == '[' {
            match line.strip_prefix('[').and_then(|s| s.strip_suffix(']')) {
                Some(name) => {
                    current = name.to_string();
                    sections.entry(current.clone()).or_default();
                }
                None => bad += 1,
            }
            continue;
        }
        match line.find('=') {
            None => bad += 1,
            Some(pos) => {
                let key = trim_st(&line[..pos]);
                let value = trim_st(&line[pos + 1..]);
                if key.is_empty() || key.contains(' ') || key.contains('\t') {
                    bad += 1;
                } else {
                    sections
                        .entry(current.clone())
                        .or_default()
                        .insert(key.to_string(), value.to_string());
                }
            }
        }
    }

    let mut out = String::new();
    out.push_str(&format!("bad {}\n", bad));
    for (name, keys) in &sections {
        out.push('[');
        out.push_str(name);
        out.push_str("]\n");
        for (k, v) in keys {
            out.push_str(k);
            out.push('=');
            out.push_str(v);
            out.push('\n');
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
