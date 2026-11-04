use std::collections::HashMap;
use std::io::{Read, Write};

fn name_ok(f: &[u8]) -> bool {
    let n = f.len();
    if n < 1 || n > 24 {
        return false;
    }
    for &c in f {
        if c.is_ascii_uppercase() || c.is_ascii_lowercase() || c.is_ascii_digit()
            || c == b' ' || c == b'.' || c == b'_' || c == b'-'
        {
            continue;
        }
        return false;
    }
    true
}

fn country_ok(f: &[u8]) -> bool {
    f.len() == 2 && f[0].is_ascii_uppercase() && f[1].is_ascii_uppercase()
}

fn number(f: &[u8], lo: i64, hi: i64) -> Option<i64> {
    if f.is_empty() {
        return None;
    }
    let mut v: i64 = 0;
    for &c in f {
        if !c.is_ascii_digit() {
            return None;
        }
        if v <= hi {
            v = v * 10 + (c - b'0') as i64;
        }
    }
    if v < lo || v > hi {
        return None;
    }
    Some(v)
}

fn split3(line: &[u8]) -> Option<[&[u8]; 3]> {
    let mut f: [&[u8]; 3] = [&[][..]; 3];
    let mut nf = 0usize;
    let mut st = 0usize;
    for i in 0..=line.len() {
        if i == line.len() || line[i] == b'\t' {
            if nf < 3 {
                f[nf] = &line[st..i];
            }
            nf += 1;
            st = i + 1;
        }
    }
    if nf == 3 {
        Some(f)
    } else {
        None
    }
}

fn main() {
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let stdout = std::io::stdout();
    let mut w = std::io::BufWriter::new(stdout.lock());
    if data.is_empty() {
        w.write_all(b"users 0 orders 0 bad 0 unmatched 0\ntotal 0\n").unwrap();
        return;
    }
    let mut uidx: HashMap<i64, usize> = HashMap::new();
    let mut uid: Vec<i64> = Vec::new();
    let mut uname: Vec<String> = Vec::new();
    let mut uctry: Vec<String> = Vec::new();
    let mut uamt: Vec<i64> = Vec::new();
    let mut unum: Vec<i64> = Vec::new();
    let mut cidx: HashMap<String, usize> = HashMap::new();
    let mut cname: Vec<String> = Vec::new();
    let mut camt: Vec<i64> = Vec::new();
    let mut cnum: Vec<i64> = Vec::new();
    let mut good_users: i64 = 0;
    let mut good_orders: i64 = 0;
    let mut bad: i64 = 0;
    let mut unmatched: i64 = 0;
    let mut sec = 0;
    let mut found_users = false;
    let mut found_orders = false;
    let mut pos = 0usize;
    while pos < data.len() {
        let end = match data[pos..].iter().position(|&b| b == b'\n') {
            Some(k) => pos + k,
            None => data.len(),
        };
        let line = &data[pos..end];
        if sec == 0 && line == b"#users" {
            sec = 1;
            found_users = true;
        } else if sec == 1 && line == b"#orders" {
            sec = 2;
            found_orders = true;
        } else if sec == 1 {
            let mut ok = false;
            if let Some(f) = split3(line) {
                if !f[0].is_empty() && !f[1].is_empty() && !f[2].is_empty() {
                    if let (Some(id), true, true) =
                        (number(f[0], 1, 2000000000), name_ok(f[1]), country_ok(f[2]))
                    {
                        if !uidx.contains_key(&id) {
                            let name = std::str::from_utf8(f[1]).unwrap().to_string();
                            let cc = std::str::from_utf8(f[2]).unwrap().to_string();
                            uidx.insert(id, uid.len());
                            uid.push(id);
                            uname.push(name);
                            uctry.push(cc);
                            uamt.push(0);
                            unum.push(0);
                            good_users += 1;
                            ok = true;
                        }
                    }
                }
            }
            if !ok {
                bad += 1;
            }
        } else if sec == 2 {
            let mut ok = false;
            if let Some(f) = split3(line) {
                if !f[0].is_empty() && !f[1].is_empty() && !f[2].is_empty() {
                    if let (Some(_oid), Some(id), Some(amt)) = (
                        number(f[0], 1, 2000000000),
                        number(f[1], 1, 2000000000),
                        number(f[2], 0, 100000000),
                    ) {
                        good_orders += 1;
                        match uidx.get(&id) {
                            None => unmatched += 1,
                            Some(&ui) => {
                                uamt[ui] += amt;
                                unum[ui] += 1;
                                let cc = &uctry[ui];
                                let ci = match cidx.get(cc) {
                                    Some(&c) => c,
                                    None => {
                                        let c = cname.len();
                                        cidx.insert(cc.clone(), c);
                                        cname.push(cc.clone());
                                        camt.push(0);
                                        cnum.push(0);
                                        c
                                    }
                                };
                                camt[ci] += amt;
                                cnum[ci] += 1;
                            }
                        }
                        ok = true;
                    }
                }
            }
            if !ok {
                bad += 1;
            }
        }
        pos = if end < data.len() { end + 1 } else { data.len() };
    }
    if !found_users || !found_orders {
        w.write_all(b"users 0 orders 0 bad 0 unmatched 0\ntotal 0\n").unwrap();
        return;
    }
    writeln!(w, "users {} orders {} bad {} unmatched {}", good_users, good_orders, bad, unmatched).unwrap();
    let mut corder: Vec<usize> = (0..cname.len()).collect();
    corder.sort_by(|&a, &b| camt[b].cmp(&camt[a]).then(cname[a].cmp(&cname[b])));
    for i in corder {
        writeln!(w, "country {} orders {} amount {}", cname[i], cnum[i], camt[i]).unwrap();
    }
    let mut uorder: Vec<usize> = (0..uid.len()).filter(|&i| unum[i] > 0).collect();
    uorder.sort_by(|&a, &b| uamt[b].cmp(&uamt[a]).then(uid[a].cmp(&uid[b])));
    for &i in uorder.iter().take(10) {
        writeln!(w, "user {} {} {}", uid[i], uname[i], uamt[i]).unwrap();
    }
    let mut total: i64 = 0;
    for v in &uamt {
        total += *v;
    }
    writeln!(w, "total {}", total).unwrap();
}
