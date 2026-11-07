use std::collections::HashMap;
use std::env;
use std::fs;
use std::process::exit;

struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn byte(&mut self) -> Option<u8> {
        if self.pos < self.data.len() {
            let b = self.data[self.pos];
            self.pos += 1;
            Some(b)
        } else {
            None
        }
    }
}

fn read_var(r: &mut Reader) -> Result<u32, &'static str> {
    let mut value: u64 = 0;
    let mut shift: u32 = 0;
    let mut i: u32 = 0;
    while i < 5 {
        let b = match r.byte() {
            Some(b) => b,
            None => return Err("truncated"),
        };
        value |= ((b & 0x7f) as u64) << shift;
        if b & 0x80 != 0 {
            if i == 4 {
                return Err("varint");
            }
        } else {
            if i >= 1 && b == 0 {
                return Err("varint");
            }
            if value > 0xFFFF_FFFF {
                return Err("varint");
            }
            return Ok(value as u32);
        }
        shift += 7;
        i += 1;
    }
    Err("varint")
}

enum Rec {
    Open { id: u32, name: Vec<u8>, initial: u32 },
    Move { from: u32, to: u32, amount: u32 },
    Shut { id: u32 },
    Mint { id: u32, amount: u32 },
    Note,
}

fn parse(data: &[u8]) -> Result<(Vec<(usize, Rec)>, bool), (usize, &'static str)> {
    if data.len() < 6 {
        return Err((0, "header"));
    }
    if &data[0..4] != &[0xC7u8, 0x4C, 0x58, 0x46] {
        return Err((0, "header"));
    }
    if data[4] != 2 {
        return Err((0, "header"));
    }
    if data[5] & !1 != 0 {
        return Err((0, "header"));
    }
    let strict = data[5] & 1 == 1;

    let mut r = Reader { data, pos: 6 };
    let mut recs: Vec<(usize, Rec)> = Vec::new();

    while r.pos < data.len() {
        let start = r.pos;
        let op = r.byte().unwrap();

        let rec = match op {
            0x01 => {
                let id = read_var(&mut r).map_err(|e| (start, e))?;
                let name_len = match r.byte() {
                    Some(b) => b,
                    None => return Err((start, "truncated")),
                };
                if name_len < 1 || name_len > 32 {
                    return Err((start, "name"));
                }
                let mut name = Vec::with_capacity(name_len as usize);
                for _ in 0..name_len {
                    let b = match r.byte() {
                        Some(b) => b,
                        None => return Err((start, "truncated")),
                    };
                    if b < 0x21 || b > 0x7E {
                        return Err((start, "name"));
                    }
                    name.push(b);
                }
                let initial = read_var(&mut r).map_err(|e| (start, e))?;
                Rec::Open { id, name, initial }
            }
            0x02 => {
                let from = read_var(&mut r).map_err(|e| (start, e))?;
                let to = read_var(&mut r).map_err(|e| (start, e))?;
                let amount = read_var(&mut r).map_err(|e| (start, e))?;
                Rec::Move { from, to, amount }
            }
            0x03 => {
                let id = read_var(&mut r).map_err(|e| (start, e))?;
                Rec::Shut { id }
            }
            0x04 => {
                let id = read_var(&mut r).map_err(|e| (start, e))?;
                let amount = read_var(&mut r).map_err(|e| (start, e))?;
                Rec::Mint { id, amount }
            }
            0x05 => {
                let len = read_var(&mut r).map_err(|e| (start, e))?;
                let remaining = data.len() - r.pos;
                if (len as usize) > remaining {
                    return Err((start, "truncated"));
                }
                r.pos += len as usize;
                Rec::Note
            }
            _ => return Err((start, "opcode")),
        };

        let cb = match r.byte() {
            Some(b) => b,
            None => return Err((start, "truncated")),
        };
        let mut c: u32 = 0;
        for k in start..r.pos - 1 {
            c = (c * 31 + data[k] as u32) % 251;
        }
        if c != cb as u32 {
            return Err((start, "check"));
        }

        recs.push((start, rec));
    }

    Ok((recs, strict))
}

struct Acct {
    name: Vec<u8>,
    balance: i64,
    open: bool,
}

fn do_reject(strict: bool, off: usize, reason: &str, count: &mut u64) {
    *count += 1;
    if strict {
        println!("rejected at offset {}: {}", off, reason);
        exit(3);
    }
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() != 1 {
        exit(1);
    }
    let data = match fs::read(&args[0]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };

    let (recs, strict) = match parse(&data) {
        Ok(v) => v,
        Err((off, kind)) => {
            println!("error at offset {}: {}", off, kind);
            exit(2);
        }
    };

    let mut accounts: HashMap<u32, Acct> = HashMap::new();
    let mut dup: u64 = 0;
    let mut unknown: u64 = 0;
    let mut shut_count: u64 = 0;
    let mut self_count: u64 = 0;
    let mut funds: u64 = 0;

    for (off, rec) in &recs {
        match rec {
            Rec::Open { id, name, initial } => {
                if accounts.contains_key(id) {
                    do_reject(strict, *off, "dup", &mut dup);
                } else {
                    accounts.insert(
                        *id,
                        Acct {
                            name: name.clone(),
                            balance: *initial as i64,
                            open: true,
                        },
                    );
                }
            }
            Rec::Move { from, to, amount } => {
                if !accounts.contains_key(from) {
                    do_reject(strict, *off, "unknown", &mut unknown);
                } else if !accounts.contains_key(to) {
                    do_reject(strict, *off, "unknown", &mut unknown);
                } else {
                    let f_open = accounts[from].open;
                    let t_open = accounts[to].open;
                    if !f_open {
                        do_reject(strict, *off, "shut", &mut shut_count);
                    } else if !t_open {
                        do_reject(strict, *off, "shut", &mut shut_count);
                    } else if from == to {
                        do_reject(strict, *off, "self", &mut self_count);
                    } else if (*amount as i64) > accounts[from].balance {
                        do_reject(strict, *off, "funds", &mut funds);
                    } else {
                        let amt = *amount as i64;
                        accounts.get_mut(from).unwrap().balance -= amt;
                        accounts.get_mut(to).unwrap().balance += amt;
                    }
                }
            }
            Rec::Shut { id } => {
                if !accounts.contains_key(id) {
                    do_reject(strict, *off, "unknown", &mut unknown);
                } else if !accounts[id].open {
                    do_reject(strict, *off, "shut", &mut shut_count);
                } else {
                    accounts.get_mut(id).unwrap().open = false;
                }
            }
            Rec::Mint { id, amount } => {
                if !accounts.contains_key(id) {
                    do_reject(strict, *off, "unknown", &mut unknown);
                } else if !accounts[id].open {
                    do_reject(strict, *off, "shut", &mut shut_count);
                } else {
                    accounts.get_mut(id).unwrap().balance += *amount as i64;
                }
            }
            Rec::Note => {}
        }
    }

    let open_count = accounts.values().filter(|a| a.open).count();
    let closed_count = accounts.values().filter(|a| !a.open).count();
    let total: i64 = accounts.values().map(|a| a.balance).sum();

    let mut ids: Vec<u32> = accounts.keys().cloned().collect();
    ids.sort();
    let mut g: i64 = 0;
    for id in ids {
        let a = &accounts[&id];
        g = (g * 1000003 + (id as i64) * 7 + a.balance) % 1000000007;
    }

    let mut tops: Vec<(u32, &Vec<u8>, i64)> = accounts
        .iter()
        .filter(|(_, a)| a.open)
        .map(|(id, a)| (*id, &a.name, a.balance))
        .collect();
    tops.sort_by(|a, b| b.2.cmp(&a.2).then(a.0.cmp(&b.0)));

    println!("records: {}", recs.len());
    println!("accounts: {} open, {} shut", open_count, closed_count);
    println!(
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        dup, unknown, shut_count, self_count, funds
    );
    println!("total: {}", total);
    for t in tops.iter().take(5) {
        println!("top: {} {} {}", t.0, String::from_utf8_lossy(t.1), t.2);
    }
    println!("digest: {}", g);
}
