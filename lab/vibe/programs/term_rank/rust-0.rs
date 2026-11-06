use std::collections::HashMap;
use std::io::{Read, Write};

fn is_word(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b >= 0x80
}

fn is_joiner(b: u8) -> bool {
    b == b'\'' || b == b'-'
}

const STOP: &[&[u8]] = &[
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by", b"for", b"from", b"had",
    b"has", b"have", b"he", b"her", b"his", b"in", b"into", b"is", b"it", b"its", b"not",
    b"of", b"on", b"or", b"our", b"she", b"so", b"than", b"that", b"the", b"their", b"them",
    b"then", b"there", b"these", b"they", b"this", b"to", b"was", b"we", b"were", b"which",
    b"will", b"with", b"you", b"your",
];

fn transform(raw: &[u8]) -> Option<Vec<u8>> {
    let mut t: Vec<u8> = Vec::with_capacity(raw.len());
    for &b in raw {
        if b != b'\'' {
            t.push(b);
        }
    }
    for b in t.iter_mut() {
        if *b >= b'A' && *b <= b'Z' {
            *b += 32;
        }
    }
    if t.iter().all(|b| b.is_ascii_digit()) {
        let digits = t.len();
        let mut s = vec![b'#'];
        s.extend_from_slice(digits.to_string().as_bytes());
        t = s;
    }
    if t.len() < 2 {
        return None;
    }
    for sw in STOP {
        if t.as_slice() == *sw {
            return None;
        }
    }
    let len = t.len();
    if len >= 5 && &t[len - 3..] == b"ing" {
        t.truncate(len - 3);
    } else if len >= 4 && t[len - 1] == b's' && t[len - 2] != b's' {
        t.truncate(len - 1);
    }
    Some(t)
}

fn extract(line: &[u8], out: &mut Vec<Vec<u8>>) {
    let n = line.len();
    let mut i = 0;
    while i < n {
        if is_word(line[i]) {
            let start = i;
            let mut end = i + 1;
            while end < n {
                if is_word(line[end]) {
                    end += 1;
                } else if is_joiner(line[end]) && end + 1 < n && is_word(line[end + 1]) {
                    end += 1;
                } else {
                    break;
                }
            }
            if let Some(t) = transform(&line[start..end]) {
                out.push(t);
            }
            i = end;
        } else {
            i += 1;
        }
    }
}

fn split_lines(data: &[u8]) -> Vec<&[u8]> {
    let mut lines = Vec::new();
    if data.is_empty() {
        return lines;
    }
    let mut start = 0;
    for i in 0..data.len() {
        if data[i] == b'\n' {
            lines.push(&data[start..i]);
            start = i + 1;
        }
    }
    if start < data.len() {
        lines.push(&data[start..]);
    }
    lines
}

fn main() {
    let mut args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    args.remove(0);
    let k: i64;
    if args.len() != 1 {
        std::process::exit(1);
    }
    {
        let s = match args[0].to_str() {
            Some(s) => s,
            None => std::process::exit(1),
        };
        if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
            std::process::exit(1);
        }
        let v: u64 = match s.parse() {
            Ok(v) => v,
            Err(_) => std::process::exit(1),
        };
        if v < 1 || v > 1000 {
            std::process::exit(1);
        }
        k = v as i64;
    }

    let mut data = Vec::new();
    if std::io::stdin().read_to_end(&mut data).is_err() {
        std::process::exit(1);
    }

    let lines = split_lines(&data);

    let mut docs: Vec<Vec<&[u8]>> = vec![Vec::new()];
    for line in lines {
        if line == b"%%" || line == b"%%\r" {
            docs.push(Vec::new());
        } else {
            docs.last_mut().unwrap().push(line);
        }
    }

    let n = docs.len() as i64;
    let mut maps: Vec<HashMap<Vec<u8>, i64>> = Vec::with_capacity(docs.len());
    for doc in &docs {
        let mut m: HashMap<Vec<u8>, i64> = HashMap::new();
        let mut toks: Vec<Vec<u8>> = Vec::new();
        for line in doc {
            extract(line, &mut toks);
        }
        for t in toks {
            *m.entry(t).or_insert(0) += 1;
        }
        maps.push(m);
    }

    let mut df: HashMap<Vec<u8>, i64> = HashMap::new();
    let mut total: HashMap<Vec<u8>, i64> = HashMap::new();
    for m in &maps {
        for (t, &c) in m {
            *df.entry(t.clone()).or_insert(0) += 1;
            *total.entry(t.clone()).or_insert(0) += c;
        }
    }

    let mut out: Vec<u8> = Vec::new();
    for (idx, m) in maps.iter().enumerate() {
        let mut items: Vec<(&Vec<u8>, i128)> = Vec::with_capacity(m.len());
        for (t, &tf) in m {
            let d = *df.get(t).unwrap() as i128;
            let numer = (tf as i128) * 1000 * ((n + 1) as i128);
            let denom = d * ((tf as i128) + 2);
            items.push((t, numer / denom));
        }
        items.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
        let take = std::cmp::min(k as usize, items.len());
        out.extend_from_slice(format!("doc {}:", idx + 1).as_bytes());
        for &(t, s) in &items[..take] {
            out.push(b' ');
            out.extend_from_slice(t);
            out.push(b'=');
            out.extend_from_slice(s.to_string().as_bytes());
        }
        out.push(b'\n');
    }

    let mut all_items: Vec<(&Vec<u8>, i64)> = total.iter().map(|(t, &c)| (t, c)).collect();
    all_items.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    let take = std::cmp::min(k as usize, all_items.len());
    out.extend_from_slice(b"all:");
    for &(t, c) in &all_items[..take] {
        out.push(b' ');
        out.extend_from_slice(t);
        out.push(b'=');
        out.extend_from_slice(c.to_string().as_bytes());
    }
    out.push(b'\n');

    let stdout = std::io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
    let _ = lock.flush();
}
