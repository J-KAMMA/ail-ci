use std::cmp::Ordering;
use std::io::{self, Read, Write};

#[derive(Clone)]
enum Id {
    Num(u64),
    Str(Vec<u8>),
}

struct Version {
    major: u64,
    minor: u64,
    patch: u64,
    pre: Option<Vec<Id>>,
    original: Vec<u8>,
}

fn parse_number(bytes: &[u8]) -> Option<u64> {
    if bytes.is_empty() {
        return None;
    }

    let mut value: u64 = 0;
    for &b in bytes {
        if !b.is_ascii_digit() {
            return None;
        }
        let digit = (b - b'0') as u64;
        value = value.checked_mul(10)?;
        value = value.checked_add(digit)?;
    }

    if value > i64::MAX as u64 {
        None
    } else {
        Some(value)
    }
}

fn parse_component(line: &[u8], pos: &mut usize) -> Option<u64> {
    let start = *pos;
    while *pos < line.len() && line[*pos].is_ascii_digit() {
        *pos += 1;
    }
    if *pos == start {
        return None;
    }
    parse_number(&line[start..*pos])
}

fn parse_identifiers(bytes: &[u8]) -> Option<Vec<Id>> {
    if bytes.is_empty() {
        return None;
    }

    let mut ids = Vec::new();
    for part in bytes.split(|&b| b == b'.') {
        if part.is_empty() {
            return None;
        }

        let mut all_digits = true;
        for &b in part {
            if !(b.is_ascii_alphanumeric() || b == b'-') {
                return None;
            }
            if !b.is_ascii_digit() {
                all_digits = false;
            }
        }

        if all_digits {
            ids.push(Id::Num(parse_number(part)?));
        } else {
            ids.push(Id::Str(part.to_vec()));
        }
    }

    Some(ids)
}

fn parse_version(line: &[u8]) -> Option<Version> {
    let mut pos = 0;

    let major = parse_component(line, &mut pos)?;
    if line.get(pos) != Some(&b'.') {
        return None;
    }
    pos += 1;

    let minor = parse_component(line, &mut pos)?;
    if line.get(pos) != Some(&b'.') {
        return None;
    }
    pos += 1;

    let patch = parse_component(line, &mut pos)?;
    let mut pre = None;

    if pos < line.len() {
        match line[pos] {
            b'-' => {
                pos += 1;
                let start = pos;
                while pos < line.len() && line[pos] != b'+' {
                    pos += 1;
                }
                pre = Some(parse_identifiers(&line[start..pos])?);

                if pos < line.len() {
                    pos += 1;
                    parse_identifiers(&line[pos..])?;
                }
            }
            b'+' => {
                pos += 1;
                parse_identifiers(&line[pos..])?;
            }
            _ => return None,
        }
    }

    Some(Version {
        major,
        minor,
        patch,
        pre,
        original: line.to_vec(),
    })
}

fn cmp_version(a: &Version, b: &Version) -> Ordering {
    match a.major.cmp(&b.major) {
        Ordering::Equal => {}
        other => return other,
    }
    match a.minor.cmp(&b.minor) {
        Ordering::Equal => {}
        other => return other,
    }
    match a.patch.cmp(&b.patch) {
        Ordering::Equal => {}
        other => return other,
    }

    match (&a.pre, &b.pre) {
        (None, None) => Ordering::Equal,
        (None, Some(_)) => Ordering::Greater,
        (Some(_), None) => Ordering::Less,
        (Some(pa), Some(pb)) => {
            let common = pa.len().min(pb.len());

            for i in 0..common {
                let ord = match (&pa[i], &pb[i]) {
                    (Id::Num(x), Id::Num(y)) => x.cmp(y),
                    (Id::Num(_), Id::Str(_)) => Ordering::Less,
                    (Id::Str(_), Id::Num(_)) => Ordering::Greater,
                    (Id::Str(x), Id::Str(y)) => x.cmp(y),
                };

                if ord != Ordering::Equal {
                    return ord;
                }
            }

            pa.len().cmp(&pb.len())
        }
    }
}

fn main() {
    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        return;
    }

    let mut bad = 0usize;
    let mut versions = Vec::new();

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
            Some(v) => versions.push(v),
            None => bad += 1,
        }
    }

    versions.sort_by(|a, b| {
        cmp_version(a, b).then_with(|| a.original.cmp(&b.original))
    });

    let mut out = Vec::new();
    let _ = writeln!(out, "bad {} sorted {}", bad, versions.len());

    for v in &versions {
        out.extend_from_slice(&v.original);
        out.push(b'\n');
    }

    let _ = io::stdout().write_all(&out);
}
