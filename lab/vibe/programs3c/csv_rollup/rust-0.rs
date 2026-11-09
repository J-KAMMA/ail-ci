use std::collections::{BTreeMap, HashMap};
use std::io::{self, Read, Write};

fn valid_name(s: &[u8]) -> bool {
    !s.is_empty()
        && s.len() <= 16
        && s.iter()
            .all(|&b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

fn parse_num(s: &[u8], allow_neg: bool) -> Option<i64> {
    let (neg, digits) = if allow_neg && !s.is_empty() && s[0] == b'-' {
        (true, &s[1..])
    } else {
        (false, s)
    };
    if digits.is_empty() {
        return None;
    }
    let mut v: i64 = 0;
    for &b in digits {
        if !b.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (b - b'0') as i64;
        if v > 1_000_000_000 {
            return None;
        }
    }
    Some(if neg { -v } else { v })
}

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();

    let rest: &[u8] = match input.iter().position(|&b| b == b'\n') {
        Some(i) => &input[i + 1..],
        None => &[],
    };

    let mut lines: Vec<&[u8]> = rest.split(|&b| b == b'\n').collect();
    if rest.is_empty() || rest[rest.len() - 1] == b'\n' {
        lines.pop();
    }

    let mut good: u64 = 0;
    let mut bad: u64 = 0;
    let mut groups: HashMap<(&[u8], &[u8]), (i64, i64)> = HashMap::new();

    for line in lines {
        let f: Vec<&[u8]> = line.split(|&b| b == b',').collect();
        if f.len() != 4 {
            bad += 1;
            continue;
        }
        let (r, p, q, pr) = (f[0], f[1], f[2], f[3]);
        if !valid_name(r) || !valid_name(p) {
            bad += 1;
            continue;
        }
        let qty = match parse_num(q, true) {
            Some(v) if (-1000..=1000).contains(&v) => v,
            _ => {
                bad += 1;
                continue;
            }
        };
        let price = match parse_num(pr, false) {
            Some(v) if (0..=10_000_000).contains(&v) => v,
            _ => {
                bad += 1;
                continue;
            }
        };
        good += 1;
        let e = groups.entry((r, p)).or_insert((0, 0));
        e.0 += qty;
        e.1 += qty * price;
    }

    let mut rows: Vec<(&[u8], &[u8], i64, i64)> = groups
        .iter()
        .map(|(k, v)| (k.0, k.1, v.0, v.1))
        .collect();
    rows.sort_by(|a, b| b.3.cmp(&a.3).then(a.0.cmp(b.0)).then(a.1.cmp(b.1)));

    let mut regions: BTreeMap<&[u8], i64> = BTreeMap::new();
    let mut total: i64 = 0;
    for row in &rows {
        *regions.entry(row.0).or_insert(0) += row.3;
        total += row.3;
    }

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    writeln!(out, "rows {} bad {} groups {}", good, bad, groups.len()).unwrap();
    for row in rows.iter().take(10) {
        writeln!(
            out,
            "{} {} {} {}",
            String::from_utf8_lossy(row.0),
            String::from_utf8_lossy(row.1),
            row.2,
            row.3
        )
        .unwrap();
    }
    for (r, s) in &regions {
        writeln!(out, "region {} revenue {}", String::from_utf8_lossy(r), s).unwrap();
    }
    writeln!(out, "total {}", total).unwrap();
    out.flush().unwrap();
}
