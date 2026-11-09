use std::collections::HashMap;
use std::io::{self, Read};

fn parse_int(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    if b.is_empty() {
        return None;
    }
    let mut i = 0;
    if b[0] == b'-' {
        i = 1;
    }
    if i >= b.len() {
        return None;
    }
    for &c in &b[i..] {
        if !c.is_ascii_digit() {
            return None;
        }
    }
    s.parse::<i64>().ok()
}

fn main() {
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    let mut stack: Vec<i64> = Vec::new();
    let mut vars: HashMap<String, i64> = HashMap::new();
    let mut out = String::new();

    for (idx, raw) in input.split('\n').enumerate() {
        let line_no = idx + 1;

        let mut line = raw;
        if line.ends_with('\r') {
            line = &line[..line.len() - 1];
        }
        let line = line.trim_matches(|c| c == ' ' || c == '\t');

        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let mut toks = line.split_whitespace();
        let cmd = match toks.next() {
            Some(c) => c,
            None => continue,
        };
        let args: Vec<&str> = toks.collect();

        let err = |out: &mut String, reason: &str| {
            out.push_str(&format!("error {} {}\n", line_no, reason));
        };

        match cmd {
            "push" => {
                if args.len() != 1 {
                    err(&mut out, "cmd");
                    continue;
                }
                match parse_int(args[0]) {
                    Some(v) => stack.push(v),
                    None => err(&mut out, "int"),
                }
            }
            "add" | "sub" | "mul" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.len() < 2 {
                    err(&mut out, "stack");
                    continue;
                }
                let b = stack[stack.len() - 1];
                let a = stack[stack.len() - 2];
                let result = match cmd {
                    "add" => a.checked_add(b),
                    "sub" => a.checked_sub(b),
                    _ => a.checked_mul(b),
                };
                match result {
                    Some(v) => {
                        stack.pop();
                        stack.pop();
                        stack.push(v);
                    }
                    None => err(&mut out, "overflow"),
                }
            }
            "dup" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.is_empty() {
                    err(&mut out, "stack");
                    continue;
                }
                let v = *stack.last().unwrap();
                stack.push(v);
            }
            "swap" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.len() < 2 {
                    err(&mut out, "stack");
                    continue;
                }
                let n = stack.len();
                stack.swap(n - 1, n - 2);
            }
            "drop" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.is_empty() {
                    err(&mut out, "stack");
                    continue;
                }
                stack.pop();
            }
            "store" => {
                if args.len() != 1 {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.is_empty() {
                    err(&mut out, "stack");
                    continue;
                }
                let v = stack.pop().unwrap();
                vars.insert(args[0].to_string(), v);
            }
            "load" => {
                if args.len() != 1 {
                    err(&mut out, "cmd");
                    continue;
                }
                match vars.get(args[0]) {
                    Some(&v) => stack.push(v),
                    None => err(&mut out, "var"),
                }
            }
            "print" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                if stack.is_empty() {
                    err(&mut out, "stack");
                    continue;
                }
                out.push_str(&format!("value {}\n", stack.last().unwrap()));
            }
            "clear" => {
                if !args.is_empty() {
                    err(&mut out, "cmd");
                    continue;
                }
                stack.clear();
            }
            _ => err(&mut out, "cmd"),
        }
    }

    out.push_str(&format!("stack {}\n", stack.len()));
    if !stack.is_empty() {
        let vals: Vec<String> = stack.iter().map(|v| v.to_string()).collect();
        out.push_str(&vals.join(" "));
        out.push('\n');
    }

    print!("{}", out);
}
