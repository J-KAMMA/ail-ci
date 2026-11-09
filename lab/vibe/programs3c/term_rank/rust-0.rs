use std::collections::BTreeMap;
use std::env;
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

fn parse_k(s: &[u8]) -> Option<usize> {
    if s.is_empty() || !s.iter().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut v: usize = 0;
    for &b in s {
        v = std::cmp::min(v * 10 + (b - b'0') as usize, 1001);
    }
    if v == 0 || v > 1000 {
        None
    } else {
        Some(v)
    }
}

fn tokens(line: &[u8]) -> Vec<&[u8]> {
    let n = line.len();
    let mut out = Vec::new();
    let mut i = 0;
    while i < n {
        if !is_word(line[i]) {
            i += 1;
            continue;
        }
        let mut j = i + 1;
        loop {
            if j >= n {
                break;
            }
            let b = line[j];
            if is_word(b) {
                j += 1;
            } else if is_joiner(b) && is_word(line[j - 1]) && j + 1 < n && is_word(line[j + 1]) {
                j += 1;
            } else {
                break;
            }
        }
        out.push(&line[i..j]);
        i = j;
    }
    out
}

fn normalize(raw: &[u8]) -> Option<Vec<u8>> {
    let mut t: Vec<u8> = raw
        .iter()
        .filter(|&&b| b != b'\'')
        .map(|b| b.to_ascii_lowercase())
        .collect();
    if !t.is_empty() && t.iter().all(|b| b.is_ascii_digit()) {
        let s = format!("#{}", t.len());
        t = s.into_bytes();
    }
    if t.len() < 2 {
        return None;
    }
    if STOP.iter().any(|w| w.as_bytes() == t.as_slice()) {
        return None;
    }
    let n = t.len();
    if n >= 5 && t.ends_with(&b"ing"[..]) {
        t.truncate(n - 3);
    } else if n >= 4 && t.ends_with(&b"s"[..]) && !t.ends_with(&b"ss"[..]) {
        t.truncate(n - 1);
    }
    Some(t)
}

fn main() {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    if args.len() != 1 {
        process::exit(1);
    }
    let k = match args[0].to_str().and_then(|s| parse_k(s.as_bytes())) {
        Some(k) => k,
        None => process::exit(1),
    };

    let mut data: Vec<u8> = Vec::new();
    if io::stdin().lock().read_to_end(&mut data).is_err() {
        process::exit(1);
    }

    let mut maps: Vec<BTreeMap<Vec<u8>, u64>> = vec![BTreeMap::new()];

    if !data.is_empty() {
        let mut parts: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
        if data.last() == Some(&b'\n') {
            parts.pop();
        }
        for line in parts {
            if line == &b"%%"[..] || line == &b"%%\r"[..] {
                maps.push(BTreeMap::new());
                continue;
            }
            let cur = maps.last_mut().unwrap();
            for tok in tokens(line) {
                if let Some(term) = normalize(tok) {
                    *cur.entry(term).or_insert(0) += 1;
                }
            }
        }
    }

    let n_docs = maps.len() as u128;

    let mut dfmap: BTreeMap<Vec<u8>, u64> = BTreeMap::new();
    let mut totals: BTreeMap<Vec<u8>, u64> = BTreeMap::new();
    for m in &maps {
        for (term, &c) in m {
            *dfmap.entry(term.clone()).or_insert(0) += 1;
            *totals.entry(term.clone()).or_insert(0) += c;
        }
    }

    let mut out: Vec<u8> = Vec::new();

    for (idx, m) in maps.iter().enumerate() {
        let mut items: Vec<(u128, &Vec<u8>)> = Vec::with_capacity(m.len());
        for (term, &tf) in m {
            let tf = tf as u128;
            let df = dfmap[term] as u128;
            let num = tf * 1000 * (n_docs + 1);
            let den = df * (tf + 2);
            let score = num / den;
            items.push((score, term));
        }
        items.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(b.1)));

        out.extend_from_slice(format!("doc {}:", idx + 1).as_bytes());
        for (score, term) in items.iter().take(k) {
            out.push(b' ');
            out.extend_from_slice(term);
            out.extend_from_slice(format!("={}", score).as_bytes());
        }
        out.push(b'\n');
    }

    let mut all: Vec<(u64, &Vec<u8>)> = totals.iter().map(|(t, &c)| (c, t)).collect();
    all.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(b.1)));

    out.extend_from_slice(b"all:");
    for (c, term) in all.iter().take(k) {
        out.push(b' ');
        out.extend_from_slice(term);
        out.extend_from_slice(format!("={}", c).as_bytes());
    }
    out.push(b'\n');

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
    let _ = lock.flush();
}
