use std::collections::HashMap;
use std::io::{self, Read, Write};

fn parse_int(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    let digits: &[u8] = if !b.is_empty() && b[0] == b'-' { &b[1..] } else { b };
    if digits.is_empty() || !digits.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    s.parse::<i64>().ok()
}

fn main() {
    let mut buf = Vec::new();
    io::stdin().read_to_end(&mut buf).unwrap();
    let text = String::from_utf8_lossy(&buf);

    let mut out = String::new();
    let mut stack: Vec<i64> = Vec::new();
    let mut vars: HashMap<String, i64> = HashMap::new();

    for (idx, raw) in text.split('\n').enumerate() {
        let lineno = idx + 1;
        let line = raw
            .strip_suffix('\r')
            .unwrap_or(raw)
            .trim_matches(|c: char| c == ' ' || c == '\t');
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let toks: Vec<&str> = line
            .split(|c: char| c == ' ' || c == '\t')
            .filter(|t| !t.is_empty())
            .collect();
        let cmd = toks[0];
        let args = &toks[1..];

        let err: Option<&'static str> = match (cmd, args.len()) {
            ("push", 1) => match parse_int(args[0]) {
                Some(v) => {
                    stack.push(v);
                    None
                }
                None => Some("int"),
            },
            ("push", _) => Some("cmd"),
            ("add", 0) | ("sub", 0) | ("mul", 0) => {
                let len = stack.len();
                if len < 2 {
                    Some("stack")
                } else {
                    let b = stack[len - 1];
                    let a = stack[len - 2];
                    let r = match cmd {
                        "add" => a.checked_add(b),
                        "sub" => a.checked_sub(b),
                        _ => a.checked_mul(b),
                    };
                    match r {
                        Some(v) => {
                            stack.truncate(len - 2);
                            stack.push(v);
                            None
                        }
                        None => Some("overflow"),
                    }
                }
            }
            ("dup", 0) => {
                if let Some(&t) = stack.last() {
                    stack.push(t);
                    None
                } else {
                    Some("stack")
                }
            }
            ("swap", 0) => {
                let len = stack.len();
                if len < 2 {
                    Some("stack")
                } else {
                    stack.swap(len - 1, len - 2);
                    None
                }
            }
            ("drop", 0) => {
                if stack.pop().is_some() {
                    None
                } else {
                    Some("stack")
                }
            }
            ("store", 1) => match stack.pop() {
                Some(v) => {
                    vars.insert(args[0].to_string(), v);
                    None
                }
                None => Some("stack"),
            },
            ("store", _) => Some("cmd"),
            ("load", 1) => match vars.get(args[0]) {
                Some(&v) => {
                    stack.push(v);
                    None
                }
                None => Some("var"),
            },
            ("load", _) => Some("cmd"),
            ("print", 0) => match stack.last() {
                Some(v) => {
                    out.push_str(&format!("value {}\n", v));
                    None
                }
                None => Some("stack"),
            },
            ("clear", 0) => {
                stack.clear();
                None
            }
            _ => Some("cmd"),
        };

        if let Some(e) = err {
            out.push_str(&format!("error {} {}\n", lineno, e));
        }
    }

    out.push_str(&format!("stack {}\n", stack.len()));
    if !stack.is_empty() {
        let vals: Vec<String> = stack.iter().map(|v| v.to_string()).collect();
        out.push_str(&vals.join(" "));
        out.push('\n');
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    lock.write_all(out.as_bytes()).unwrap();
    lock.flush().unwrap();
}
