use std::io::{self, Read, Write};

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
enum Ident {
    Num(i64),
    Alpha(Vec<u8>),
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
struct Key {
    major: i64,
    minor: i64,
    patch: i64,
    release: bool,
    pre: Vec<Ident>,
}

fn all_digits(s: &[u8]) -> bool {
    !s.is_empty() && s.iter().all(|b| b.is_ascii_digit())
}

fn parse_idents(s: &[u8]) -> Option<Vec<Ident>> {
    if s.is_empty() {
        return None;
    }
    let mut v = Vec::new();
    for part in s.split(|&b| b == b'.') {
        if part.is_empty() {
            return None;
        }
        if !part.iter().all(|&b| b.is_ascii_alphanumeric() || b == b'-') {
            return None;
        }
        if all_digits(part) {
            let n: i64 = std::str::from_utf8(part).ok()?.parse().ok()?;
            v.push(Ident::Num(n));
        } else {
            v.push(Ident::Alpha(part.to_vec()));
        }
    }
    Some(v)
}

fn parse_line(line: &[u8]) -> Option<Key> {
    let (main, build) = match line.iter().position(|&b| b == b'+') {
        Some(i) => (&line[..i], Some(&line[i + 1..])),
        None => (line, None),
    };
    if let Some(b) = build {
        parse_idents(b)?;
    }
    let (core, pre) = match main.iter().position(|&b| b == b'-') {
        Some(i) => (&main[..i], Some(&main[i + 1..])),
        None => (main, None),
    };
    let pre_ids = match pre {
        Some(p) => parse_idents(p)?,
        None => Vec::new(),
    };
    let parts: Vec<&[u8]> = core.split(|&b| b == b'.').collect();
    if parts.len() != 3 {
        return None;
    }
    let mut nums = [0i64; 3];
    for (i, p) in parts.iter().enumerate() {
        if !all_digits(p) {
            return None;
        }
        nums[i] = std::str::from_utf8(p).ok()?.parse().ok()?;
    }
    Some(Key {
        major: nums[0],
        minor: nums[1],
        patch: nums[2],
        release: pre.is_none(),
        pre: pre_ids,
    })
}

fn main() {
    let mut data = Vec::new();
    let _ = io::stdin().read_to_end(&mut data);

    let mut bad: usize = 0;
    let mut items: Vec<(Key, Vec<u8>)> = Vec::new();

    for raw in data.split(|&b| b == b'\n') {
        let line: &[u8] = if raw.last() == Some(&b'\r') {
            &raw[..raw.len() - 1]
        } else {
            raw
        };
        if line.iter().all(|b| b.is_ascii_whitespace()) {
            continue;
        }
        match parse_line(line) {
            Some(k) => items.push((k, line.to_vec())),
            None => bad += 1,
        }
    }

    items.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));

    let mut out: Vec<u8> = Vec::new();
    let _ = writeln!(out, "bad {} sorted {}", bad, items.len());
    for (_, l) in &items {
        out.extend_from_slice(l);
        out.push(b'\n');
    }
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let _ = handle.write_all(&out);
    let _ = handle.flush();
}
