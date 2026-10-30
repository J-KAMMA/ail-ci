use std::collections::HashMap;
use std::io::{Read, Write};

fn w(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b >= 0x80
}

const STOP: &[&str] = &[
    "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "had", "has", "have", "he",
    "her", "his", "in", "into", "is", "it", "its", "not", "of", "on", "or", "our", "she", "so",
    "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "to", "was",
    "we", "were", "which", "will", "with", "you", "your",
];

fn make_term(raw: &[u8]) -> Option<Vec<u8>> {
    let mut t: Vec<u8> = raw
        .iter()
        .filter(|&&b| b != b'\'')
        .map(|b| b.to_ascii_lowercase())
        .collect();
    if !t.is_empty() && t.iter().all(|b| b.is_ascii_digit()) {
        t = format!("#{}", t.len()).into_bytes();
    }
    if t.len() < 2 {
        return None;
    }
    if STOP.iter().any(|s| s.as_bytes() == &t[..]) {
        return None;
    }
    if t.len() >= 5 && t.ends_with(b"ing") {
        t.truncate(t.len() - 3);
    } else if t.len() >= 4 && t.ends_with(b"s") && !t.ends_with(b"ss") {
        t.truncate(t.len() - 1);
    }
    Some(t)
}

fn main() {
    let args: Vec<String> = std::env::args_os()
        .skip(1)
        .map(|a| a.to_string_lossy().into_owned())
        .collect();
    if args.len() != 1 {
        std::process::exit(1);
    }
    let a = args[0].as_bytes();
    if a.is_empty() || !a.iter().all(|b| b.is_ascii_digit()) {
        std::process::exit(1);
    }
    let s = a.iter().position(|&b| b != b'0').unwrap_or(a.len());
    let a = &a[s..];
    if a.is_empty() || a.len() > 4 {
        std::process::exit(1);
    }
    let k: usize = std::str::from_utf8(a).unwrap().parse().unwrap();
    if k < 1 || k > 1000 {
        std::process::exit(1);
    }

    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if data.is_empty() || data.last() == Some(&b'\n') {
        lines.pop();
    }

    let mut docs: Vec<HashMap<Vec<u8>, u64>> = vec![HashMap::new()];
    for line in lines {
        if line == b"%%" || line == b"%%\r" {
            docs.push(HashMap::new());
            continue;
        }
        let n = line.len();
        let mut i = 0;
        let doc = docs.last_mut().unwrap();
        while i < n {
            if !w(line[i]) {
                i += 1;
                continue;
            }
            let start = i;
            let mut j = i + 1;
            while j < n {
                if w(line[j]) {
                    j += 1;
                } else if (line[j] == b'\'' || line[j] == b'-') && j + 1 < n && w(line[j + 1]) {
                    j += 2;
                } else {
                    break;
                }
            }
            if let Some(t) = make_term(&line[start..j]) {
                *doc.entry(t).or_insert(0) += 1;
            }
            i = j;
        }
    }

    let nd = docs.len() as u128;
    let mut df: HashMap<&[u8], u128> = HashMap::new();
    let mut total: HashMap<&[u8], u64> = HashMap::new();
    for d in &docs {
        for (t, &c) in d {
            *df.entry(&t[..]).or_insert(0) += 1;
            *total.entry(&t[..]).or_insert(0) += c;
        }
    }

    let mut out: Vec<u8> = Vec::new();
    for (di, d) in docs.iter().enumerate() {
        let mut v: Vec<(u128, &[u8])> = d
            .iter()
            .map(|(t, &tf)| {
                let tf = tf as u128;
                let sc = tf * 1000 * (nd + 1) / (df[&t[..]] * (tf + 2));
                (sc, &t[..])
            })
            .collect();
        v.sort_by(|x, y| y.0.cmp(&x.0).then(x.1.cmp(y.1)));
        out.extend_from_slice(format!("doc {}:", di + 1).as_bytes());
        for (sc, t) in v.iter().take(k) {
            out.push(b' ');
            out.extend_from_slice(t);
            out.extend_from_slice(format!("={}", sc).as_bytes());
        }
        out.push(b'\n');
    }
    let mut v: Vec<(u64, &[u8])> = total.iter().map(|(t, &c)| (c, *t)).collect();
    v.sort_by(|x, y| y.0.cmp(&x.0).then(x.1.cmp(y.1)));
    out.extend_from_slice(b"all:");
    for (c, t) in v.iter().take(k) {
        out.push(b' ');
        out.extend_from_slice(t);
        out.extend_from_slice(format!("={}", c).as_bytes());
    }
    out.push(b'\n');
    std::io::stdout().write_all(&out).unwrap();
}
