use std::collections::HashMap;
use std::io::{self, Read, Write};

fn parse_int(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    if b.is_empty() {
        return None;
    }
    let neg = b[0] == b'-';
    let digits = if neg { &b[1..] } else { b };
    if digits.is_empty() {
        return None;
    }
    let mut val: u128 = 0;
    for &d in digits {
        if !d.is_ascii_digit() {
            return None;
        }
        val = match val
            .checked_mul(10)
            .and_then(|v| v.checked_add((d - b'0') as u128))
        {
            Some(v) => v,
            None => return None,
        };
    }
    if neg {
        const LIM: u128 = 9223372036854775808;
        if val > LIM {
            return None;
        }
        if val == LIM {
            Some(i64::MIN)
        } else {
            Some(-(val as i64))
        }
    } else {
        if val > i64::MAX as u128 {
            return None;
        }
        Some(val as i64)
    }
}

fn main() {
    let mut buf = Vec::new();
    io::stdin().read_to_end(&mut buf).ok();
    let input = String::from_utf8_lossy(&buf);

    let mut stack: Vec<i64> = Vec::new();
    let mut vars: HashMap<String, i64> = HashMap::new();
    let mut out = String::new();

    for (i, raw) in input.split('\n').enumerate() {
        let line_no = i + 1;
        let mut line = raw;
        if let Some(x) = line.strip_suffix('\r') {
            line = x;
        }
        let line = line.trim_matches(|c| c == ' ' || c == '\t');
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let mut it = line.split_whitespace();
        let cmd = it.next().unwrap();
        let args: Vec<&str> = it.collect();

        let res: Result<Option<String>, &'static str> = (|| {
            match cmd {
                "push" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    let v = match parse_int(args[0]) {
                        Some(v) => v,
                        None => return Err("int"),
                    };
                    stack.push(v);
                }
                "add" | "sub" | "mul" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    if stack.len() < 2 {
                        return Err("stack");
                    }
                    let n = stack.len();
                    let b = stack[n - 1];
                    let a = stack[n - 2];
                    let r = match cmd {
                        "add" => a.checked_add(b),
                        "sub" => a.checked_sub(b),
                        _ => a.checked_mul(b),
                    };
                    match r {
                        Some(v) => {
                            stack.pop();
                            stack.pop();
                            stack.push(v);
                        }
                        None => return Err("overflow"),
                    }
                }
                "dup" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    if stack.is_empty() {
                        return Err("stack");
                    }
                    let v = *stack.last().unwrap();
                    stack.push(v);
                }
                "swap" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    if stack.len() < 2 {
                        return Err("stack");
                    }
                    let n = stack.len();
                    stack.swap(n - 1, n - 2);
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
                "store" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    if stack.is_empty() {
                        return Err("stack");
                    }
                    let v = stack.pop().unwrap();
                    vars.insert(args[0].to_string(), v);
                }
                "load" => {
                    if args.len() != 1 {
                        return Err("cmd");
                    }
                    match vars.get(args[0]) {
                        Some(&v) => stack.push(v),
                        None => return Err("var"),
                    }
                }
                "print" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    if stack.is_empty() {
                        return Err("stack");
                    }
                    return Ok(Some(format!("value {}", stack.last().unwrap())));
                }
                "clear" => {
                    if !args.is_empty() {
                        return Err("cmd");
                    }
                    stack.clear();
                }
                _ => return Err("cmd"),
            }
            Ok(None)
        })();

        match res {
            Ok(Some(s)) => {
                out.push_str(&s);
                out.push('\n');
            }
            Ok(None) => {}
            Err(e) => {
                out.push_str(&format!("error {} {}\n", line_no, e));
            }
        }
    }

    out.push_str(&format!("stack {}\n", stack.len()));
    if !stack.is_empty() {
        let parts: Vec<String> = stack.iter().map(|v| v.to_string()).collect();
        out.push_str(&parts.join(" "));
        out.push('\n');
    }

    io::stdout().write_all(out.as_bytes()).ok();
}
