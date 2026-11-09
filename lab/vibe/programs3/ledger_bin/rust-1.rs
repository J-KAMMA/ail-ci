use std::collections::HashMap;
use std::fmt::Write as _;
use std::process::exit;

enum Rec {
    Open { id: u32, name: Vec<u8>, initial: i128 },
    Move { from: u32, to: u32, amount: i128 },
    Shut { id: u32 },
    Mint { id: u32, amount: i128 },
    Note,
}

struct Record {
    offset: usize,
    rec: Rec,
}

struct Acc {
    name: Vec<u8>,
    balance: i128,
    open: bool,
}

fn fail(offset: usize, kind: &str) -> ! {
    println!("error at offset {}: {}", offset, kind);
    exit(2);
}

fn reject(offset: usize, reason: &str) -> ! {
    println!("rejected at offset {}: {}", offset, reason);
    exit(3);
}

fn read_var(data: &[u8], pos: &mut usize) -> Result<u32, &'static str> {
    let mut value: u64 = 0;
    let mut shift: u32 = 0;
    let mut count: usize = 0;
    loop {
        if *pos >= data.len() {
            return Err("truncated");
        }
        let b = data[*pos];
        *pos += 1;
        count += 1;
        value |= ((b & 0x7f) as u64) << shift;
        if b & 0x80 != 0 {
            if count == 5 {
                return Err("varint");
            }
            shift += 7;
        } else {
            if count >= 2 && b == 0 {
                return Err("varint");
            }
            if value > 0xFFFF_FFFF {
                return Err("varint");
            }
            return Ok(value as u32);
        }
    }
}

fn main() {
    let mut it = std::env::args_os();
    let _prog = it.next();
    let path = match it.next() {
        Some(p) => p,
        None => exit(1),
    };
    if it.next().is_some() {
        exit(1);
    }
    let data = match std::fs::read(&path) {
        Ok(d) => d,
        Err(_) => exit(1),
    };

    let n = data.len();
    if n < 6 {
        fail(0, "header");
    }
    if data[0] != 0xC7
        || data[1] != b'L'
        || data[2] != b'X'
        || data[3] != b'F'
        || data[4] != 0x02
        || data[5] > 0x01
    {
        fail(0, "header");
    }
    let strict = data[5] & 1 != 0;

    let mut pos = 6usize;
    let mut records: Vec<Record> = Vec::new();

    while pos < n {
        let start = pos;
        let op = data[pos];
        pos += 1;

        let rec = match op {
            0x01 => {
                let id = match read_var(&data, &mut pos) {
                    Ok(v) => v,
                    Err(e) => fail(start, e),
                };
                if pos >= n {
                    fail(start, "truncated");
                }
                let nl = data[pos] as usize;
                pos += 1;
                if nl < 1 || nl > 32 {
                    fail(start, "name");
                }
                let mut name = Vec::with_capacity(nl);
                for _ in 0..nl {
                    if pos >= n {
                        fail(start, "truncated");
                    }
                    let b = data[pos];
                    pos += 1;
                    if b < 0x21 || b > 0x7E {
                        fail(start, "name");
                    }
                    name.push(b);
                }
                let initial = match read_var(&data, &mut pos) {
                    Ok(v) => v as i128,
                    Err(e) => fail(start, e),
                };
                Rec::Open { id, name, initial }
            }
            0x02 => {
                let from = match read_var(&data, &mut pos) {
                    Ok(v) => v,
                    Err(e) => fail(start, e),
                };
                let to = match read_var(&data, &mut pos) {
                    Ok(v) => v,
                    Err(e) => fail(start, e),
                };
                let amount = match read_var(&data, &mut pos) {
                    Ok(v) => v as i128,
                    Err(e) => fail(start, e),
                };
                Rec::Move { from, to, amount }
            }
            0x03 => {
                let id = match read_var(&data, &mut pos) {
                    Ok(v) => v,
                    Err(e) => fail(start, e),
                };
                Rec::Shut { id }
            }
            0x04 => {
                let id = match read_var(&data, &mut pos) {
                    Ok(v) => v,
                    Err(e) => fail(start, e),
                };
                let amount = match read_var(&data, &mut pos) {
                    Ok(v) => v as i128,
                    Err(e) => fail(start, e),
                };
                Rec::Mint { id, amount }
            }
            0x05 => {
                let len = match read_var(&data, &mut pos) {
                    Ok(v) => v as usize,
                    Err(e) => fail(start, e),
                };
                if n - pos < len {
                    fail(start, "truncated");
                }
                pos += len;
                Rec::Note
            }
            _ => fail(start, "opcode"),
        };

        if pos >= n {
            fail(start, "truncated");
        }
        let check = data[pos];
        let mut c: u32 = 0;
        for &b in &data[start..pos] {
            c = (c * 31 + b as u32) % 251;
        }
        if c as u8 != check {
            fail(start, "check");
        }
        pos += 1;

        records.push(Record {
            offset: start,
            rec,
        });
    }

    let mut map: HashMap<u32, Acc> = HashMap::new();
    let mut dup: u64 = 0;
    let mut unknown: u64 = 0;
    let mut shut_c: u64 = 0;
    let mut self_c: u64 = 0;
    let mut funds: u64 = 0;

    for r in &records {
        match &r.rec {
            Rec::Open { id, name, initial } => {
                if map.contains_key(id) {
                    dup += 1;
                    if strict {
                        reject(r.offset, "dup");
                    }
                } else {
                    map.insert(
                        *id,
                        Acc {
                            name: name.clone(),
                            balance: *initial,
                            open: true,
                        },
                    );
                }
            }
            Rec::Move { from, to, amount } => {
                if !map.contains_key(from) || !map.contains_key(to) {
                    unknown += 1;
                    if strict {
                        reject(r.offset, "unknown");
                    }
                } else if !map[from].open || !map[to].open {
                    shut_c += 1;
                    if strict {
                        reject(r.offset, "shut");
                    }
                } else if from == to {
                    self_c += 1;
                    if strict {
                        reject(r.offset, "self");
                    }
                } else if *amount > map[from].balance {
                    funds += 1;
                    if strict {
                        reject(r.offset, "funds");
                    }
                } else {
                    map.get_mut(from).unwrap().balance -= *amount;
                    map.get_mut(to).unwrap().balance += *amount;
                }
            }
            Rec::Shut { id } => {
                if !map.contains_key(id) {
                    unknown += 1;
                    if strict {
                        reject(r.offset, "unknown");
                    }
                } else if !map[id].open {
                    shut_c += 1;
                    if strict {
                        reject(r.offset, "shut");
                    }
                } else {
                    map.get_mut(id).unwrap().open = false;
                }
            }
            Rec::Mint { id, amount } => {
                if !map.contains_key(id) {
                    unknown += 1;
                    if strict {
                        reject(r.offset, "unknown");
                    }
                } else if !map[id].open {
                    shut_c += 1;
                    if strict {
                        reject(r.offset, "shut");
                    }
                } else {
                    map.get_mut(id).unwrap().balance += *amount;
                }
            }
            Rec::Note => {}
        }
    }

    let mut a: u64 = 0;
    let mut s: u64 = 0;
    let mut total: i128 = 0;
    for acc in map.values() {
        if acc.open {
            a += 1;
        } else {
            s += 1;
        }
        total += acc.balance;
    }

    let mut open: Vec<(u32, &Acc)> = map
        .iter()
        .filter(|(_, acc)| acc.open)
        .map(|(id, acc)| (*id, acc))
        .collect();
    open.sort_by(|x, y| y.1.balance.cmp(&x.1.balance).then(x.0.cmp(&y.0)));

    let mut ids: Vec<u32> = map.keys().cloned().collect();
    ids.sort();
    let mut g: i128 = 0;
    for id in ids {
        let b = map[&id].balance;
        g = (g * 1000003 + (id as i128) * 7 + b) % 1000000007;
    }

    let mut out = String::new();
    writeln!(out, "records: {}", records.len()).unwrap();
    writeln!(out, "accounts: {} open, {} shut", a, s).unwrap();
    writeln!(
        out,
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        dup, unknown, shut_c, self_c, funds
    )
    .unwrap();
    writeln!(out, "total: {}", total).unwrap();
    for &(id, acc) in open.iter().take(5) {
        let name = String::from_utf8_lossy(&acc.name);
        writeln!(out, "top: {} {} {}", id, name, acc.balance).unwrap();
    }
    writeln!(out, "digest: {}", g).unwrap();
    print!("{}", out);
}
