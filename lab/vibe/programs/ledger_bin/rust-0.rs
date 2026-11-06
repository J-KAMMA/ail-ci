use std::collections::HashMap;

enum Rec {
    Open { id: u32, name: Vec<u8>, initial: u32 },
    Move { from: u32, to: u32, amount: u32 },
    Shut { id: u32 },
    Mint { id: u32, amount: u32 },
    Note,
}

fn read_var(data: &[u8], mut idx: usize) -> Result<(u32, usize), &'static str> {
    let mut val: u64 = 0;
    let mut shift: u32 = 0;
    let mut count = 0;
    loop {
        if idx >= data.len() {
            return Err("truncated");
        }
        let b = data[idx];
        idx += 1;
        count += 1;
        if count == 5 && (b & 0x80) != 0 {
            return Err("varint");
        }
        val |= ((b & 0x7F) as u64) << shift;
        if (b & 0x80) == 0 {
            if val > 4294967295 {
                return Err("varint");
            }
            if count >= 2 && b == 0 {
                return Err("varint");
            }
            return Ok((val as u32, idx));
        }
        shift += 7;
    }
}

fn parse(data: &[u8]) -> Result<Vec<(usize, Rec)>, (usize, &'static str)> {
    if data.len() < 6 {
        return Err((0, "header"));
    }
    if data[0] != 0xC7 || data[1] != b'L' || data[2] != b'X' || data[3] != b'F' {
        return Err((0, "header"));
    }
    if data[4] != 0x02 {
        return Err((0, "header"));
    }
    if (data[5] & !1u8) != 0 {
        return Err((0, "header"));
    }

    let mut idx = 6;
    let mut recs: Vec<(usize, Rec)> = Vec::new();

    while idx < data.len() {
        let start = idx;
        let op = data[idx];
        idx += 1;

        let rec = match op {
            1 => {
                let (id, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                if idx >= data.len() {
                    return Err((start, "truncated"));
                }
                let nl = data[idx];
                idx += 1;
                if nl < 1 || nl > 32 {
                    return Err((start, "name"));
                }
                let mut name = Vec::new();
                for _ in 0..nl {
                    if idx >= data.len() {
                        return Err((start, "truncated"));
                    }
                    let b = data[idx];
                    idx += 1;
                    if b < 0x21 || b > 0x7E {
                        return Err((start, "name"));
                    }
                    name.push(b);
                }
                let (initial, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                Rec::Open { id, name, initial }
            }
            2 => {
                let (from, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                let (to, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                let (amount, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                Rec::Move { from, to, amount }
            }
            3 => {
                let (id, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                Rec::Shut { id }
            }
            4 => {
                let (id, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                let (amount, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                Rec::Mint { id, amount }
            }
            5 => {
                let (len, ni) = read_var(data, idx).map_err(|k| (start, k))?;
                idx = ni;
                let len = len as usize;
                if data.len() - idx < len {
                    return Err((start, "truncated"));
                }
                idx += len;
                Rec::Note
            }
            _ => return Err((start, "opcode")),
        };

        if idx >= data.len() {
            return Err((start, "truncated"));
        }
        let chk = data[idx];
        idx += 1;

        let mut c: u32 = 0;
        for j in start..idx - 1 {
            c = (c * 31 + data[j] as u32) % 251;
        }
        if c != chk as u32 {
            return Err((start, "check"));
        }

        recs.push((start, rec));
    }

    Ok(recs)
}

struct Acc {
    name: Vec<u8>,
    balance: i64,
    open: bool,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        std::process::exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => std::process::exit(1),
    };

    let recs = match parse(&data) {
        Ok(r) => r,
        Err((off, kind)) => {
            println!("error at offset {}: {}", off, kind);
            std::process::exit(2);
        }
    };

    let strict = (data[5] & 1) == 1;
    let mut accounts: HashMap<u32, Acc> = HashMap::new();
    let mut dup: u64 = 0;
    let mut unknown: u64 = 0;
    let mut shut_c: u64 = 0;
    let mut self_c: u64 = 0;
    let mut funds_c: u64 = 0;

    for (off, rec) in &recs {
        match rec {
            Rec::Open { id, name, initial } => {
                if accounts.contains_key(id) {
                    dup += 1;
                    if strict {
                        println!("rejected at offset {}: dup", off);
                        std::process::exit(3);
                    }
                } else {
                    accounts.insert(
                        *id,
                        Acc {
                            name: name.clone(),
                            balance: *initial as i64,
                            open: true,
                        },
                    );
                }
            }
            Rec::Move { from, to, amount } => {
                let reason: Option<&'static str> = if !accounts.contains_key(from) {
                    Some("unknown")
                } else if !accounts.contains_key(to) {
                    Some("unknown")
                } else if !accounts[from].open {
                    Some("shut")
                } else if !accounts[to].open {
                    Some("shut")
                } else if from == to {
                    Some("self")
                } else if *amount as i64 > accounts[from].balance {
                    Some("funds")
                } else {
                    None
                };

                match reason {
                    Some(r) => {
                        let cnt = match r {
                            "unknown" => &mut unknown,
                            "shut" => &mut shut_c,
                            "self" => &mut self_c,
                            _ => &mut funds_c,
                        };
                        *cnt += 1;
                        if strict {
                            println!("rejected at offset {}: {}", off, r);
                            std::process::exit(3);
                        }
                    }
                    None => {
                        let a = *amount as i64;
                        accounts.get_mut(from).unwrap().balance -= a;
                        accounts.get_mut(to).unwrap().balance += a;
                    }
                }
            }
            Rec::Shut { id } => {
                let reason: Option<&'static str> = if !accounts.contains_key(id) {
                    Some("unknown")
                } else if !accounts[id].open {
                    Some("shut")
                } else {
                    None
                };

                match reason {
                    Some(r) => {
                        let cnt = match r {
                            "unknown" => &mut unknown,
                            _ => &mut shut_c,
                        };
                        *cnt += 1;
                        if strict {
                            println!("rejected at offset {}: {}", off, r);
                            std::process::exit(3);
                        }
                    }
                    None => {
                        accounts.get_mut(id).unwrap().open = false;
                    }
                }
            }
            Rec::Mint { id, amount } => {
                let reason: Option<&'static str> = if !accounts.contains_key(id) {
                    Some("unknown")
                } else if !accounts[id].open {
                    Some("shut")
                } else {
                    None
                };

                match reason {
                    Some(r) => {
                        let cnt = match r {
                            "unknown" => &mut unknown,
                            _ => &mut shut_c,
                        };
                        *cnt += 1;
                        if strict {
                            println!("rejected at offset {}: {}", off, r);
                            std::process::exit(3);
                        }
                    }
                    None => {
                        accounts.get_mut(id).unwrap().balance += *amount as i64;
                    }
                }
            }
            Rec::Note => {}
        }
    }

    let mut ids: Vec<u32> = accounts.keys().cloned().collect();
    ids.sort_unstable();

    let mut open_count: u64 = 0;
    let mut shut_count: u64 = 0;
    let mut total: i64 = 0;
    let mut g: i64 = 0;
    let mut tops: Vec<(u32, &Acc)> = Vec::new();

    for id in &ids {
        let acc = &accounts[id];
        if acc.open {
            open_count += 1;
            tops.push((*id, acc));
        } else {
            shut_count += 1;
        }
        total += acc.balance;
        g = (g * 1000003 + (*id as i64) * 7 + acc.balance) % 1000000007;
    }

    tops.sort_by(|a, b| b.1.balance.cmp(&a.1.balance).then(a.0.cmp(&b.0)));

    println!("records: {}", recs.len());
    println!("accounts: {} open, {} shut", open_count, shut_count);
    println!(
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        dup, unknown, shut_c, self_c, funds_c
    );
    println!("total: {}", total);
    for (id, acc) in tops.iter().take(5) {
        println!(
            "top: {} {} {}",
            id,
            std::str::from_utf8(&acc.name).unwrap(),
            acc.balance
        );
    }
    println!("digest: {}", g);
}
