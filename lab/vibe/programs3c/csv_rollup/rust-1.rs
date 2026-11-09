use std::collections::{BTreeMap, HashMap};
use std::io::{self, Read, Write};

fn valid_name(f: &[u8]) -> bool {
    !f.is_empty()
        && f.len() <= 16
        && f.iter()
            .all(|&c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
}

fn parse_int(f: &[u8], signed: bool) -> Option<i64> {
    let (neg, digits) = if signed && !f.is_empty() && f[0] == b'-' {
        (true, &f[1..])
    } else {
        (false, f)
    };
    if digits.is_empty() || !digits.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let mut v: i64 = 0;
    for &c in digits {
        v = v.checked_mul(10)?.checked_add((c - b'0') as i64)?;
    }
    Some(if neg { -v } else { v })
}

fn parse_line(line: &[u8]) -> Option<(&[u8], &[u8], i64, i64)> {
    let f: Vec<&[u8]> = line.split(|&c| c == b',').collect();
    if f.len() != 4 {
        return None;
    }
    if !valid_name(f[0]) || !valid_name(f[1]) {
        return None;
    }
    let qty = parse_int(f[2], true)?;
    if !(-1000..=1000).contains(&qty) {
        return None;
    }
    let price = parse_int(f[3], false)?;
    if !(0..=10_000_000).contains(&price) {
        return None;
    }
    Some((f[0], f[1], qty, price))
}

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();
    let mut out: Vec<u8> = Vec::new();

    if input.is_empty() {
        out.extend_from_slice(b"rows 0 bad 0 groups 0\ntotal 0\n");
    } else {
        let rest: &[u8] = match input.iter().position(|&c| c == b'\n') {
            Some(p) => &input[p + 1..],
            None => &[],
        };

        let mut good: u64 = 0;
        let mut bad: u64 = 0;
        let mut groups: HashMap<(Vec<u8>, Vec<u8>), (i64, i64)> = HashMap::new();

        if !rest.is_empty() {
            let body: &[u8] = if rest.last() == Some(&b'\n') {
                &rest[..rest.len() - 1]
            } else {
                rest
            };
            for line in body.split(|&c| c == b'\n') {
                match parse_line(line) {
                    Some((r, p, q, pr)) => {
                        good += 1;
                        let e = groups
                            .entry((r.to_vec(), p.to_vec()))
                            .or_insert((0, 0));
                        e.0 += q;
                        e.1 += q * pr;
                    }
                    None => bad += 1,
                }
            }
        }

        writeln!(out, "rows {} bad {} groups {}", good, bad, groups.len()).unwrap();

        let mut v: Vec<(&Vec<u8>, &Vec<u8>, i64, i64)> = groups
            .iter()
            .map(|((r, p), (q, rev))| (r, p, *q, *rev))
            .collect();
        v.sort_by(|a, b| {
            b.3.cmp(&a.3)
                .then_with(|| a.0.cmp(b.0))
                .then_with(|| a.1.cmp(b.1))
        });

        for item in v.iter().take(10) {
            out.extend_from_slice(item.0);
            out.push(b' ');
            out.extend_from_slice(item.1);
            writeln!(out, " {} {}", item.2, item.3).unwrap();
        }

        let mut regions: BTreeMap<&Vec<u8>, i64> = BTreeMap::new();
        let mut total: i64 = 0;
        for ((r, _), (_, rev)) in groups.iter() {
            *regions.entry(r).or_insert(0) += *rev;
            total += *rev;
        }

        for (r, sum) in regions.iter() {
            out.extend_from_slice(b"region ");
            out.extend_from_slice(r);
            writeln!(out, " revenue {}", sum).unwrap();
        }

        writeln!(out, "total {}", total).unwrap();
    }

    io::stdout().lock().write_all(&out).unwrap();
}
