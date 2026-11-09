use std::collections::HashMap;
use std::env;
use std::io::{self, Read, Write};

fn is_word(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b >= 0x80
}

fn is_joiner(b: u8) -> bool {
    b == b'\'' || b == b'-'
}

fn is_separator(line: &[u8]) -> bool {
    (line.len() == 2 && line[0] == b'%' && line[1] == b'%')
        || (line.len() == 3 && line[0] == b'%' && line[1] == b'%' && line[2] == b'\r')
}

const STOP_WORDS: &[&[u8]] = &[
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by", b"for", b"from", b"had",
    b"has", b"have", b"he", b"her", b"his", b"in", b"into", b"is", b"it", b"its", b"not",
    b"of", b"on", b"or", b"our", b"she", b"so", b"than", b"that", b"the", b"their", b"them",
    b"then", b"there", b"these", b"they", b"this", b"to", b"was", b"we", b"were", b"which",
    b"will", b"with", b"you", b"your",
];

fn is_stop_word(t: &[u8]) -> bool {
    STOP_WORDS.iter().any(|w| *w == t)
}

fn process_token(raw: &[u8]) -> Option<Vec<u8>> {
    let mut t = Vec::with_capacity(raw.len());
    for &b in raw {
        if b == b'\'' {
            continue;
        }
        if b.is_ascii_uppercase() {
            t.push(b + 32);
        } else {
            t.push(b);
        }
    }

    if !t.is_empty() && t.iter().all(|b| b.is_ascii_digit()) {
        t = format!("#{}", t.len()).into_bytes();
    }

    if t.len() < 2 {
        return None;
    }

    if is_stop_word(&t) {
        return None;
    }

    if t.len() >= 5 && t.ends_with(b"ing") {
        t.truncate(t.len() - 3);
    } else if t.len() >= 4 && t.ends_with(b"s") && !t.ends_with(b"ss") {
        t.truncate(t.len() - 1);
    }

    Some(t)
}

fn scan_line<F: FnMut(Vec<u8>)>(line: &[u8], mut f: F) {
    let n = line.len();
    let mut i = 0;
    while i < n {
        if is_word(line[i]) {
            let start = i;
            let mut j = i;
            while j < n {
                if is_word(line[j]) {
                    j += 1;
                } else if is_joiner(line[j]) && j + 1 < n && is_word(line[j + 1]) {
                    j += 1;
                } else {
                    break;
                }
            }
            if let Some(tok) = process_token(&line[start..j]) {
                f(tok);
            }
            i = j;
        } else {
            i += 1;
        }
    }
}

fn get_k(args: &[std::ffi::OsString]) -> Option<usize> {
    if args.len() != 2 {
        return None;
    }
    let s = args[1].to_str()?;
    if s.is_empty() {
        return None;
    }
    let mut val: u64 = 0;
    for &b in s.as_bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        val = val * 10 + (b - b'0') as u64;
        if val > 1000 {
            return None;
        }
    }
    if val < 1 {
        None
    } else {
        Some(val as usize)
    }
}

fn main() {
    let args: Vec<std::ffi::OsString> = env::args_os().collect();
    let k = match get_k(&args) {
        Some(k) => k,
        None => std::process::exit(1),
    };

    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        std::process::exit(1);
    }

    let mut lines: Vec<&[u8]> = Vec::new();
    {
        let mut start = 0usize;
        for i in 0..input.len() {
            if input[i] == b'\n' {
                lines.push(&input[start..i]);
                start = i + 1;
            }
        }
        if start < input.len() {
            lines.push(&input[start..]);
        }
    }

    let mut docs: Vec<Vec<&[u8]>> = vec![Vec::new()];
    for line in lines {
        if is_separator(line) {
            docs.push(Vec::new());
        } else {
            docs.last_mut().unwrap().push(line);
        }
    }

    let n_docs = docs.len();
    let mut df: HashMap<Vec<u8>, i64> = HashMap::new();
    let mut totals: HashMap<Vec<u8>, i64> = HashMap::new();
    let mut doc_tfs: Vec<HashMap<Vec<u8>, i64>> = Vec::with_capacity(n_docs);

    for doc in &docs {
        let mut tf: HashMap<Vec<u8>, i64> = HashMap::new();
        for &line in doc {
            scan_line(line, |t| {
                *tf.entry(t).or_insert(0) += 1;
            });
        }
        for (term, &c) in tf.iter() {
            *df.entry(term.clone()).or_insert(0) += 1;
            *totals.entry(term.clone()).or_insert(0) += c;
        }
        doc_tfs.push(tf);
    }

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for (di, tf) in doc_tfs.iter().enumerate() {
        let mut items: Vec<(i128, &[u8])> = tf
            .iter()
            .map(|(term, &c)| {
                let tfc = c as i128;
                let dfv = df[term.as_slice()] as i128;
                let score = tfc * 1000 * ((n_docs as i128) + 1) / (dfv * (tfc + 2));
                (score, term.as_slice())
            })
            .collect();

        items.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(b.1)));

        let _ = write!(out, "doc {}:", di + 1);
        for &(score, term) in items.iter().take(k) {
            let _ = out.write_all(b" ");
            let _ = out.write_all(term);
            let _ = write!(out, "={}", score);
        }
        let _ = out.write_all(b"\n");
    }

    let mut all: Vec<(i64, &[u8])> = totals
        .iter()
        .map(|(term, &c)| (c, term.as_slice()))
        .collect();
    all.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(b.1)));

    let _ = out.write_all(b"all:");
    for &(c, term) in all.iter().take(k) {
        let _ = out.write_all(b" ");
        let _ = out.write_all(term);
        let _ = write!(out, "={}", c);
    }
    let _ = out.write_all(b"\n");
    let _ = out.flush();
}
