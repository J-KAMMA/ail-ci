use std::collections::HashMap;
use std::io::{Read, Write};

fn name_ok(f: &[u8]) -> bool {
    let n = f.len();
    if n < 1 || n > 16 {
        return false;
    }
    for &c in f {
        if !(c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_') {
            return false;
        }
    }
    true
}

fn number(f: &[u8], allow_neg: bool) -> Option<i64> {
    let mut i = 0;
    let mut neg = false;
    if allow_neg && i < f.len() && f[i] == b'-' {
        neg = true;
        i = 1;
    }
    if i >= f.len() {
        return None;
    }
    let mut v: i64 = 0;
    while i < f.len() {
        let c = f[i];
        if c < b'0' || c > b'9' {
            return None;
        }
        if v <= 10000001 {
            v = v * 10 + (c - b'0') as i64;
        }
        i += 1;
    }
    Some(if neg { -v } else { v })
}

fn main() {
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let stdout = std::io::stdout();
    let mut w = std::io::BufWriter::new(stdout.lock());
    if data.is_empty() {
        w.write_all(b"rows 0 bad 0 groups 0\ntotal 0\n").unwrap();
        return;
    }
    let mut groups: HashMap<(String, String), (i64, i64)> = HashMap::new();
    let mut regions: HashMap<String, i64> = HashMap::new();
    let mut good: i64 = 0;
    let mut bad: i64 = 0;
    let mut pos = 0usize;
    let mut first = true;
    while pos < data.len() {
        let end = match data[pos..].iter().position(|&b| b == b'\n') {
            Some(k) => pos + k,
            None => data.len(),
        };
        let line = &data[pos..end];
        if first {
            first = false;
        } else {
            let mut fs: [&[u8]; 4] = [&[][..]; 4];
            let mut nf = 0usize;
            let mut st = 0usize;
            for i in 0..=line.len() {
                if i == line.len() || line[i] == b',' {
                    if nf < 4 {
                        fs[nf] = &line[st..i];
                    }
                    nf += 1;
                    st = i + 1;
                }
            }
            if nf != 4 {
                bad += 1;
            } else {
                let (reg, prod, qf, pf) = (fs[0], fs[1], fs[2], fs[3]);
                if !name_ok(reg) || !name_ok(prod) || qf.is_empty() || pf.is_empty() {
                    bad += 1;
                } else {
                    match (number(qf, true), number(pf, false)) {
                        (Some(q), Some(p)) if q >= -1000 && q <= 1000 && p >= 0 && p <= 10000000 => {
                            let rev = q * p;
                            let r = std::str::from_utf8(reg).unwrap().to_string();
                            let pr = std::str::from_utf8(prod).unwrap().to_string();
                            let e = groups.entry((r.clone(), pr)).or_insert((0, 0));
                            e.0 += q;
                            e.1 += rev;
                            *regions.entry(r).or_insert(0) += rev;
                            good += 1;
                        }
                        _ => bad += 1,
                    }
                }
            }
        }
        pos = if end < data.len() { end + 1 } else { data.len() };
    }
    writeln!(w, "rows {} bad {} groups {}", good, bad, groups.len()).unwrap();
    let mut gv: Vec<(&String, &String, i64, i64)> = groups
        .iter()
        .map(|((r, p), &(q, rev))| (r, p, q, rev))
        .collect();
    gv.sort_by(|a, b| b.3.cmp(&a.3).then(a.0.cmp(b.0)).then(a.1.cmp(b.1)));
    for &(r, p, q, rev) in gv.iter().take(10) {
        writeln!(w, "{} {} {} {}", r, p, q, rev).unwrap();
    }
    let mut rv: Vec<(&String, &i64)> = regions.iter().collect();
    rv.sort_by(|a, b| a.0.cmp(b.0));
    let mut total: i64 = 0;
    for (r, v) in &rv {
        writeln!(w, "region {} revenue {}", r, v).unwrap();
        total += *v;
    }
    writeln!(w, "total {}", total).unwrap();
}
