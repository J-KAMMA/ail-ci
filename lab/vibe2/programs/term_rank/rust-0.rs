use std::collections::HashMap;
use std::env;
use std::io::{self, Read, Write};

const STOP_WORDS: &[&[u8]] = &[
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by", b"for", b"from",
    b"had", b"has", b"have", b"he", b"her", b"his", b"in", b"into", b"is", b"it",
    b"its", b"not", b"of", b"on", b"or", b"our", b"she", b"so", b"than", b"that",
    b"the", b"their", b"them", b"then", b"there", b"these", b"they", b"this", b"to",
    b"was", b"we", b"were", b"which", b"will", b"with", b"you", b"your",
];

fn usage() -> ! {
    std::process::exit(1);
}

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

fn push_usize(out: &mut Vec<u8>, mut n: usize) {
    if n == 0 {
        out.push(b'0');
        return;
    }
    let mut buf = [0u8; 20];
    let mut i = buf.len();
    while n > 0 {
        i -= 1;
        buf[i] = b'0' + (n % 10) as u8;
        n /= 10;
    }
    out.extend_from_slice(&buf[i..]);
}

fn is_stop(t: &[u8]) -> bool {
    STOP_WORDS.iter().any(|w| *w == t)
}

fn make_term(raw: &[u8]) -> Option<Vec<u8>> {
    let mut t = Vec::with_capacity(raw.len());

    for &b in raw {
        if b == b'\'' {
            continue;
        }
        if b >= b'A' && b <= b'Z' {
            t.push(b + 32);
        } else {
            t.push(b);
        }
    }

    if !t.is_empty() && t.iter().all(|&b| b.is_ascii_digit()) {
        let digits = t.len();
        t.clear();
        t.push(b'#');
        push_usize(&mut t, digits);
    }

    if t.len() < 2 {
        return None;
    }

    if is_stop(&t) {
        return None;
    }

    let len = t.len();
    if len >= 5 && t.ends_with(b"ing") {
        t.truncate(len - 3);
    } else if len >= 4 && t[len - 1] == b's' && !t.ends_with(b"ss") {
        t.truncate(len - 1);
    }

    Some(t)
}

fn process_line(line: &[u8], counts: &mut HashMap<Vec<u8>, u64>) {
    let n = line.len();
    let mut i = 0;

    while i < n {
        if !is_word(line[i]) {
            i += 1;
            continue;
        }

        let start = i;
        let mut j = i;

        while j < n {
            if is_word(line[j]) {
                j += 1;
            } else if is_joiner(line[j])
                && j > start
                && j + 1 < n
                && is_word(line[j - 1])
                && is_word(line[j + 1])
            {
                j += 1;
            } else {
                break;
            }
        }

        if let Some(term) = make_term(&line[start..j]) {
            *counts.entry(term).or_insert(0) += 1;
        }

        i = j;
    }
}

fn main() {
    let mut args = env::args_os().skip(1);

    let karg = match args.next() {
        Some(a) => a,
        None => usage(),
    };

    if args.next().is_some() {
        usage();
    }

    let s = match karg.to_str() {
        Some(s) => s,
        None => usage(),
    };

    if s.is_empty() {
        usage();
    }

    let mut kval: u64 = 0;
    for &b in s.as_bytes() {
        if !b.is_ascii_digit() {
            usage();
        }
        kval = kval.saturating_mul(10).saturating_add((b - b'0') as u64);
    }

    if !(1..=1000).contains(&kval) {
        usage();
    }

    let k = kval as usize;

    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        usage();
    }

    let mut docs: Vec<HashMap<Vec<u8>, u64>> = Vec::new();
    let mut current: HashMap<Vec<u8>, u64> = HashMap::new();

    if !input.is_empty() {
        let mut pos = 0;

        loop {
            let start = pos;
            while pos < input.len() && input[pos] != b'\n' {
                pos += 1;
            }

            let line = &input[start..pos];

            if is_separator(line) {
                docs.push(std::mem::take(&mut current));
            } else {
                process_line(line, &mut current);
            }

            if pos < input.len() {
                pos += 1;
                if pos == input.len() {
                    break;
                }
            } else {
                break;
            }
        }
    }

    docs.push(current);

    let mut global: HashMap<Vec<u8>, (u64, u64)> = HashMap::new();

    for doc in &docs {
        for (term, &tf) in doc {
            let entry = global.entry(term.clone()).or_insert((0, 0));
            entry.0 += tf;
            entry.1 += 1;
        }
    }

    let n_docs = docs.len() as i128;
    let mut out = Vec::new();

    for (idx, doc) in docs.iter().enumerate() {
        out.extend_from_slice(b"doc ");
        push_usize(&mut out, idx + 1);
        out.push(b':');

        let mut scored: Vec<(&[u8], i128)> = Vec::with_capacity(doc.len());

        for (term, &tf) in doc {
            let df = global.get(term).unwrap().1 as i128;
            let score =
                (tf as i128) * 1000 * (n_docs + 1) / (df * (tf as i128 + 2));
            scored.push((term.as_slice(), score));
        }

        scored.sort_unstable_by(|a, b| {
            b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0))
        });

        for (term, score) in scored.into_iter().take(k) {
            out.push(b' ');
            out.extend_from_slice(term);
            out.push(b'=');
            out.extend_from_slice(score.to_string().as_bytes());
        }

        out.push(b'\n');
    }

    let mut all: Vec<(&[u8], u64)> = global
        .iter()
        .map(|(term, value)| (term.as_slice(), value.0))
        .collect();

    all.sort_unstable_by(|a, b| {
        b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0))
    });

    out.extend_from_slice(b"all:");

    for (term, count) in all.into_iter().take(k) {
        out.push(b' ');
        out.extend_from_slice(term);
        out.push(b'=');
        out.extend_from_slice(count.to_string().as_bytes());
    }

    out.push(b'\n');

    let stdout = io::stdout();
    let mut lock = stdout.lock();

    if lock.write_all(&out).is_err() {
        std::process::exit(1);
    }
}
