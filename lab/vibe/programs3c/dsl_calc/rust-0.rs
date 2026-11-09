use std::collections::HashMap;
use std::io::{self, Read, Write};

fn parse_int(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    let digits = if !b.is_empty() && b[0] == b'-' { &b[1..] } else { b };
    if digits.is_empty() || !digits.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    s.parse::<i64>().ok()
}

fn main() {
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    let mut out = String::new();
    let mut stack: Vec<i64> = Vec::new();
    let mut vars: HashMap<String, i64> = HashMap::new();

    for (idx, raw) in input.split('\n').enumerate() {
        let lineno = idx + 1;
        let line = raw.strip_suffix('\r').unwrap_or(raw);
        let line = line.trim_matches(|c| c == ' ' || c == '\t');
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let toks: Vec<&str> = line
            .split(|c| c == ' ' || c == '\t')
            .filter(|t| !t.is_empty())
            .collect();
        let cmd = toks[0];
        let args: &[&str] = &toks[1..];

        let res = (|| -> Result<(), &'static str> {
            match cmd {
                "push" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    let v = parse_int(args[0]).ok_or("int")?;
                    stack.push(v);
                }
                "add" | "sub" | "mul" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    let n = stack.len();
                    if n < 2 {
                        return Err("stack");
                    }
                    let a = stack[n - 2];
                    let b = stack[n - 1];
                    let r = match cmd {
                        "add" => a.checked_add(b),
                        "sub" => a.checked_sub(b),
                        _ => a.checked_mul(b),
                    };
                    let r = r.ok_or("overflow")?;
                    stack.truncate(n - 2);
                    stack.push(r);
                }
                "dup" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    let n = stack.len();
                    if n < 1 {
                        return Err("stack");
                    }
                    let top = stack[n - 1];
                    stack.push(top);
                }
                "swap" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    let n = stack.len();
                    if n < 2 {
                        return Err("stack");
                    }
                    stack.swap(n - 2, n - 1);
                }
                "drop" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    if stack.is_empty() {
                        return Err("stack");
                    }
                    stack.pop();
                }
                "print" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    match stack.last() {
                        Some(top) => out.push_str(&format!("value {}\n", top)),
                        None => return Err("stack"),
                    }
                }
                "clear" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    stack.clear();
                }
                "store" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    let v = stack.pop().ok_or("stack")?;
                    vars.insert(args[0].to_string(), v);
                }
                "load" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    let v = *vars.get(args[0]).ok_or("var")?;
                    stack.push(v);
                }
                _ => return Err("cmd"),
            }
            Ok(())
        })();

        if let Err(reason) = res {
            out.push_str(&format!("error {} {}\n", lineno, reason));
        }
    }

    out.push_str(&format!("stack {}\n", stack.len()));
    if !stack.is_empty() {
        let parts: Vec<String> = stack.iter().map(|v| v.to_string()).collect();
        out.push_str(&parts.join(" "));
        out.push('\n');
    }

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let _ = handle.write_all(out.as_bytes());
    let _ = handle.flush();
}
