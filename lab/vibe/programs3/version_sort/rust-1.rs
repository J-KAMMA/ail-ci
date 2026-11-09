use std::cmp::Ordering;
use std::io::{self, Read, Write};

const MAX: u64 = 9_223_372_036_854_775_807;

enum PreId {
    Num(u64),
    Str(Vec<u8>),
}

struct Version {
    major: u64,
    minor: u64,
    patch: u64,
    pre: Option<Vec<PreId>>,
}

struct Entry {
    line: Vec<u8>,
    version: Version,
}

fn is_digit(b: u8) -> bool {
    b >= b'0' && b <= b'9'
}

fn is_ident_byte(b: u8) -> bool {
    (b >= b'0' && b <= b'9')
        || (b >= b'a' && b <= b'z')
        || (b >= b'A' && b <= b'Z')
        || b == b'-'
}

fn parse_digits(s: &[u8], i: &mut usize) -> Option<u64> {
    let start = *i;
    let mut value: u64 = 0;

    while *i < s.len() && is_digit(s[*i]) {
        let d = (s[*i] - b'0') as u64;
        value = value.checked_mul(10)?.checked_add(d)?;
        if value > MAX {
            return None;
        }
        *i += 1;
    }

    if *i == start {
        None
    } else {
        Some(value)
    }
}

fn parse_ident_list(s: &[u8], i: &mut usize, stop_at_plus: bool) -> Option<Vec<PreId>> {
    let mut ids = Vec::new();

    loop {
        let start = *i;

        while *i < s.len() && is_ident_byte(s[*i]) {
            *i += 1;
        }

        if *i == start {
            return None;
        }

        let bytes = &s[start..*i];
        let all_digits = bytes.iter().all(|&b| is_digit(b));

        if all_digits {
            let mut j = start;
            let value = parse_digits(s, &mut j)?;
            ids.push(PreId::Num(value));
        } else {
            ids.push(PreId::Str(bytes.to_vec()));
        }

        if *i == s.len() {
            break;
        }

        if s[*i] == b'.' {
            *i += 1;
            continue;
        }

        if stop_at_plus && s[*i] == b'+' {
            break;
        }

        return None;
    }

    Some(ids)
}

fn parse_version(s: &[u8]) -> Option<Version> {
    let mut i = 0;

    let major = parse_digits(s, &mut i)?;
    if s.get(i) != Some(&b'.') {
        return None;
    }
    i += 1;

    let minor = parse_digits(s, &mut i)?;
    if s.get(i) != Some(&b'.') {
        return None;
    }
    i += 1;

    let patch = parse_digits(s, &mut i)?;

    let mut pre = None;

    if i < s.len() && s[i] == b'-' {
        i += 1;
        pre = Some(parse_ident_list(s, &mut i, true)?);
    }

    if i < s.len() {
        if s[i] == b'+' {
            i += 1;
            parse_ident_list(s, &mut i, false)?;
        } else {
            return None;
        }
    }

    if i != s.len() {
        return None;
    }

    Some(Version {
        major,
        minor,
        patch,
        pre,
    })
}

fn compare_pre_id(a: &PreId, b: &PreId) -> Ordering {
    match (a, b) {
        (PreId::Num(x), PreId::Num(y)) => x.cmp(y),
        (PreId::Num(_), PreId::Str(_)) => Ordering::Less,
        (PreId::Str(_), PreId::Num(_)) => Ordering::Greater,
        (PreId::Str(x), PreId::Str(y)) => x.cmp(y),
    }
}

fn compare_pre(a: &[PreId], b: &[PreId]) -> Ordering {
    for (x, y) in a.iter().zip(b.iter()) {
        let order = compare_pre_id(x, y);
        if order != Ordering::Equal {
            return order;
        }
    }

    a.len().cmp(&b.len())
}

impl Version {
    fn cmp_precedence(&self, other: &Version) -> Ordering {
        self.major
            .cmp(&other.major)
            .then(self.minor.cmp(&other.minor))
            .then(self.patch.cmp(&other.patch))
            .then_with(|| match (&self.pre, &other.pre) {
                (None, None) => Ordering::Equal,
                (None, Some(_)) => Ordering::Greater,
                (Some(_), None) => Ordering::Less,
                (Some(a), Some(b)) => compare_pre(a, b),
            })
    }
}

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();

    let mut entries = Vec::new();
    let mut bad: usize = 0;

    for raw_line in input.split(|&b| b == b'\n') {
        let line = if raw_line.last() == Some(&b'\r') {
            &raw_line[..raw_line.len() - 1]
        } else {
            raw_line
        };

        if line.is_empty() {
            continue;
        }

        match parse_version(line) {
            Some(version) => entries.push(Entry {
                line: line.to_vec(),
                version,
            }),
            None => bad += 1,
        }
    }

    entries.sort_by(|a, b| {
        a.version
            .cmp_precedence(&b.version)
            .then_with(|| a.line.cmp(&b.line))
    });

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "bad {} sorted {}", bad, entries.len()).unwrap();

    for entry in entries {
        out.write_all(&entry.line).unwrap();
        out.write_all(b"\n").unwrap();
    }
}
