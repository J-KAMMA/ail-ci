use std::collections::BTreeMap;
use std::io::{self, Read, Write};

fn is_ws(c: char) -> bool {
    c == ' ' || c == '\t'
}

fn main() {
    let mut buf = Vec::new();
    if io::stdin().read_to_end(&mut buf).is_err() {
        buf.clear();
    }
    let text = String::from_utf8_lossy(&buf);

    let mut sections: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    let mut current = String::new();
    let mut bad: u64 = 0;

    for raw in text.split('\n') {
        let line0 = raw.strip_suffix('\r').unwrap_or(raw);
        let line = line0.trim_matches(is_ws);

        if line.is_empty() {
            continue;
        }

        let first = line.chars().next().unwrap();
        if first == '#' || first == ';' {
            continue;
        }

        if first == '[' {
            if line.len() >= 2 && line.ends_with(']') {
                let name = line[1..line.len() - 1].to_string();
                sections.entry(name.clone()).or_default();
                current = name;
            } else {
                bad += 1;
            }
            continue;
        }

        match line.find('=') {
            None => {
                bad += 1;
            }
            Some(pos) => {
                let key = line[..pos].trim_matches(is_ws);
                let value = line[pos + 1..].trim_matches(is_ws);
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
    let mut handle = stdout.lock();
    let _ = handle.write_all(out.as_bytes());
    let _ = handle.flush();
}
