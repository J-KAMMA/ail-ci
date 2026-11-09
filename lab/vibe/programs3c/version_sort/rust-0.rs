use std::cmp::Ordering;
use std::io::{self, Read, Write};

#[derive(PartialEq, Eq, PartialOrd, Ord, Clone)]
enum Ident {
    Num(u64),
    Alpha(Vec<u8>),
}

struct Ver {
    major: u64,
    minor: u64,
    patch: u64,
    pre: Vec<Ident>,
    line: Vec<u8>,
}

fn all_digits(d: &[u8]) -> bool {
    !d.is_empty() && d.iter().all(|c| c.is_ascii_digit())
}

fn parse_num(d: &[u8]) -> Option<u64> {
    if !all_digits(d) {
        return None;
    }
    let mut i = 0;
    while i + 1 < d.len() && d[i] == b'0' {
        i += 1;
    }
    let s = &d[i..];
    if s.len() > 19 {
        return None;
    }
    if s.len() == 19 && s > &b"9223372036854775807"[..] {
        return None;
    }
    let mut v: u64 = 0;
    for &c in s {
        v = v * 10 + (c - b'0') as u64;
    }
    Some(v)
}

fn parse_idents(s: &[u8]) -> Option<Vec<Ident>> {
    let mut out = Vec::new();
    for part in s.split(|&c| c == b'.') {
        if part.is_empty() {
            return None;
        }
        if !part.iter().all(|&c| c.is_ascii_alphanumeric() || c == b'-') {
            return None;
        }
        if all_digits(part) {
            out.push(Ident::Num(parse_num(part)?));
        } else {
            out.push(Ident::Alpha(part.to_vec()));
        }
    }
    Some(out)
}

fn parse_line(line: &[u8]) -> Option<(u64, u64, u64, Vec<Ident>)> {
    let (rest, build) = match line.iter().position(|&c| c == b'+') {
        Some(p) => (&line[..p], Some(&line[p + 1..])),
        None => (line, None),
    };
    if let Some(b) = build {
        parse_idents(b)?;
    }
    let (core, pre) = match rest.iter().position(|&c| c == b'-') {
        Some(p) => (&rest[..p], Some(&rest[p + 1..])),
        None => (rest, None),
    };
    let parts: Vec<&[u8]> = core.split(|&c| c == b'.').collect();
    if parts.len() != 3 {
        return None;
    }
    let major = parse_num(parts[0])?;
    let minor = parse_num(parts[1])?;
    let patch = parse_num(parts[2])?;
    let pre_ids = match pre {
        Some(p) => parse_idents(p)?,
        None => Vec::new(),
    };
    Some((major, minor, patch, pre_ids))
}

fn cmp_prec(a: &Ver, b: &Ver) -> Ordering {
    a.major
        .cmp(&b.major)
        .then(a.minor.cmp(&b.minor))
        .then(a.patch.cmp(&b.patch))
        .then_with(|| match (a.pre.is_empty(), b.pre.is_empty()) {
            (true, true) => Ordering::Equal,
            (true, false) => Ordering::Greater,
            (false, true) => Ordering::Less,
            _ => a.pre.cmp(&b.pre),
        })
}

fn main() {
    let mut buf = Vec::new();
    let _ = io::stdin().read_to_end(&mut buf);

    let mut vers: Vec<Ver> = Vec::new();
    let mut bad: usize = 0;

    for piece in buf.split(|&c| c == b'\n') {
        let line: &[u8] = if piece.last() == Some(&b'\r') {
            &piece[..piece.len() - 1]
        } else {
            piece
        };
        if line.iter().all(|c| c.is_ascii_whitespace()) {
            continue;
        }
        match parse_line(line) {
            Some((major, minor, patch, pre)) => vers.push(Ver {
                major,
                minor,
                patch,
                pre,
                line: line.to_vec(),
            }),
            None => bad += 1,
        }
    }

    vers.sort_by(|a, b| cmp_prec(a, b).then_with(|| a.line.cmp(&b.line)));

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    let _ = write!(out, "bad {} sorted {}\n", bad, vers.len());
    for v in &vers {
        let _ = out.write_all(&v.line);
        let _ = out.write_all(b"\n");
    }
    let _ = out.flush();
}
