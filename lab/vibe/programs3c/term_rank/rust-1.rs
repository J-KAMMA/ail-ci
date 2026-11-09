use std::collections::BTreeMap;
use std::ffi::OsString;
use std::io::{self, Read, Write};
use std::process;

const STOP: &[&str] = &[
    "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "had", "has", "have",
    "he", "her", "his", "in", "into", "is", "it", "its", "not", "of", "on", "or", "our", "she",
    "so", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "to",
    "was", "we", "were", "which", "will", "with", "you", "your",
];

fn is_word(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b >= 0x80
}

fn is_joiner(b: u8) -> bool {
    b == b'\'' || b == b'-'
}

fn normalize(tok: &[u8]) -> Option<Vec<u8>> {
    let mut t: Vec<u8> = tok
        .iter()
        .filter(|&&b| b != b'\'')
        .map(|&b| b.to_ascii_lowercase())
        .collect();
    if !t.is_empty() && t.iter().all(|b| b.is_ascii_digit()) {
        let s = format!("#{}", t.len());
        t = s.into_bytes();
    }
    if t.len() < 2 {
        return None;
    }
    if STOP.iter().any(|s| s.as_bytes() == t.as_slice()) {
        return None;
    }
    let n = t.len();
    if n >= 5 && t.ends_with(b"ing") {
        t.truncate(n - 3);
    } else if n >= 4 && t.ends_with(b"s") && !t.ends_with(b"ss") {
        t.truncate(n - 1);
    }
    Some(t)
}

fn tokens_of_line(line: &[u8], out: &mut Vec<Vec<u8>>) {
    let n = line.len();
    let mut i = 0;
    while i < n {
        if !is_word(line[i]) {
            i += 1;
            continue;
        }
        let start = i;
        let mut j = i;
        loop {
            if j < n && is_word(line[j]) {
                j += 1;
            } else if j < n && is_joiner(line[j]) && j + 1 < n && is_word(line[j + 1]) {
                j += 1;
            } else {
                break;
            }
        }
        i = j;
        if let Some(t) = normalize(&line[start..j]) {
            out.push(t);
        }
    }
}

fn parse_k(arg: &OsString) -> Option<u64> {
    let s = arg.to_str()?;
    let b = s.as_bytes();
    if b.is_empty() || !b.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let mut v: u64 = 0;
    for &c in b {
        v = std::cmp::min(v * 10 + (c - b'0') as u64, 1_000_000);
    }
    if (1..=1000).contains(&v) {
        Some(v)
    } else {
        None
    }
}

fn main() {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    if args.len() != 1 {
        process::exit(1);
    }
    let k = match parse_k(&args[0]) {
        Some(k) => k as usize,
        None => process::exit(1),
    };

    let mut data = Vec::new();
    let _ = io::stdin().read_to_end(&mut data);

    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if data.is_empty() {
        lines.clear();
    } else if data.last() == Some(&b'\n') {
        lines.pop();
    }

    let mut docs: Vec<Vec<&[u8]>> = vec![Vec::new()];
    for line in lines {
        if line == &b"%%"[..] || line == &b"%%\r"[..] {
            docs.push(Vec::new());
        } else {
            docs.last_mut().unwrap().push(line);
        }
    }

    let mut doc_tf: Vec<BTreeMap<Vec<u8>, u64>> = Vec::with_capacity(docs.len());
    let mut df: BTreeMap<Vec<u8>, u64> = BTreeMap::new();
    let mut total: BTreeMap<Vec<u8>, u64> = BTreeMap::new();

    for doc in &docs {
        let mut toks: Vec<Vec<u8>> = Vec::new();
        for line in doc {
            tokens_of_line(line, &mut toks);
        }
        let mut tf: BTreeMap<Vec<u8>, u64> = BTreeMap::new();
        for t in toks {
            *tf.entry(t).or_insert(0) += 1;
        }
        for (t, &c) in &tf {
            *df.entry(t.clone()).or_insert(0) += 1;
            *total.entry(t.clone()).or_insert(0) += c;
        }
        doc_tf.push(tf);
    }

    let n_docs = docs.len() as u128;
    let mut out: Vec<u8> = Vec::new();

    for (idx, tf) in doc_tf.iter().enumerate() {
        let mut items: Vec<(u128, &Vec<u8>)> = Vec::with_capacity(tf.len());
        for (t, &c) in tf {
            let d = df[t] as u128;
            let c128 = c as u128;
            let score = c128 * 1000 * (n_docs + 1) / (d * (c128 + 2));
            items.push((score, t));
        }
        items.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(b.1)));

        out.extend_from_slice(format!("doc {}:", idx + 1).as_bytes());
        for (score, t) in items.iter().take(k) {
            out.push(b' ');
            out.extend_from_slice(t);
            out.extend_from_slice(format!("={}", score).as_bytes());
        }
        out.push(b'\n');
    }

    let mut all: Vec<(u64, &Vec<u8>)> = total.iter().map(|(t, &c)| (c, t)).collect();
    all.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(b.1)));
    out.extend_from_slice(b"all:");
    for (c, t) in all.iter().take(k) {
        out.push(b' ');
        out.extend_from_slice(t);
        out.extend_from_slice(format!("={}", c).as_bytes());
    }
    out.push(b'\n');

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
    let _ = lock.flush();
}
