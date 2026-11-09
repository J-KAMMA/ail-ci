use std::collections::BTreeMap;
use std::io::{self, Read, Write};

fn trim_st(s: &str) -> &str {
    s.trim_matches(|c| c == ' ' || c == '\t')
}

fn main() {
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    let mut sections: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    let mut bad: u64 = 0;
    let mut current = String::new();

    for raw in input.split('\n') {
        let mut line = raw;
        if let Some(stripped) = line.strip_suffix('\r') {
            line = stripped;
        }
        let line = trim_st(line);

        if line.is_empty() {
            continue;
        }
        if line.starts_with('#') || line.starts_with(';') {
            continue;
        }
        if line.starts_with('[') {
            if line.ends_with(']') {
                let name = &line[1..line.len() - 1];
                current = name.to_string();
                sections.entry(name.to_string()).or_insert_with(BTreeMap::new);
            } else {
                bad += 1;
            }
            continue;
        }

        match line.find('=') {
            Some(pos) => {
                let key = trim_st(&line[..pos]);
                let value = trim_st(&line[pos + 1..]);
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

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    writeln!(out, "bad {}", bad).unwrap();
    for (name, keys) in &sections {
        writeln!(out, "[{}]", name).unwrap();
        for (k, v) in keys {
            writeln!(out, "{}={}", k, v).unwrap();
        }
    }
    let _ = out.flush();
}
