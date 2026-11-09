use std::collections::HashMap;
use std::process::exit;

enum Body {
    Open { id: u32, name: Vec<u8>, initial: u32 },
    Move { from: u32, to: u32, amount: u32 },
    Shut { id: u32 },
    Mint { id: u32, amount: u32 },
    Note,
}

struct Record {
    offset: usize,
    body: Body,
}

struct Account {
    name: Vec<u8>,
    balance: i64,
    open: bool,
}

struct Parser<'a> {
    d: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn byte(&mut self, start: usize) -> Result<u8, (usize, &'static str)> {
        if self.pos >= self.d.len() {
            return Err((start, "truncated"));
        }
        let b = self.d[self.pos];
        self.pos += 1;
        Ok(b)
    }

    fn var(&mut self, start: usize) -> Result<u32, (usize, &'static str)> {
        let mut value: u64 = 0;
        let mut shift: u32 = 0;
        let mut count = 0;
        let mut last = 0u8;
        loop {
            let b = self.byte(start)?;
            count += 1;
            last = b;
            if count == 5 && (b & 0x80) != 0 {
                return Err((start, "varint"));
            }
            value |= ((b & 0x7f) as u64) << shift;
            shift += 7;
            if (b & 0x80) == 0 {
                break;
            }
        }
        if count >= 2 && last == 0 {
            return Err((start, "varint"));
        }
        if value > 0xFFFF_FFFF {
            return Err((start, "varint"));
        }
        Ok(value as u32)
    }
}

fn parse(data: &[u8]) -> Result<(Vec<Record>, bool), (usize, &'static str)> {
    if data.len() < 6 {
        return Err((0, "header"));
    }
    if data[0] != 0xC7 || data[1] != 0x4C || data[2] != 0x58 || data[3] != 0x46 {
        return Err((0, "header"));
    }
    if data[4] != 0x02 {
        return Err((0, "header"));
    }
    if data[5] & 0xFE != 0 {
        return Err((0, "header"));
    }
    let strict = (data[5] & 1) != 0;
    let mut p = Parser { d: data, pos: 6 };
    let mut records = Vec::new();
    while p.pos < data.len() {
        let start = p.pos;
        let op = p.d[p.pos];
        p.pos += 1;
        let body = match op {
            0x01 => {
                let id = p.var(start)?;
                let nl = p.byte(start)?;
                if nl < 1 || nl > 32 {
                    return Err((start, "name"));
                }
                let mut name = Vec::with_capacity(nl as usize);
                for _ in 0..nl {
                    let b = p.byte(start)?;
                    if b < 0x21 || b > 0x7E {
                        return Err((start, "name"));
                    }
                    name.push(b);
                }
                let initial = p.var(start)?;
                Body::Open { id, name, initial }
            }
            0x02 => {
                let from = p.var(start)?;
                let to = p.var(start)?;
                let amount = p.var(start)?;
                Body::Move { from, to, amount }
            }
            0x03 => {
                let id = p.var(start)?;
                Body::Shut { id }
            }
            0x04 => {
                let id = p.var(start)?;
                let amount = p.var(start)?;
                Body::Mint { id, amount }
            }
            0x05 => {
                let len = p.var(start)?;
                let remaining = (p.d.len() - p.pos) as u64;
                if remaining < len as u64 {
                    return Err((start, "truncated"));
                }
                p.pos += len as usize;
                Body::Note
            }
            _ => return Err((start, "opcode")),
        };
        if p.pos >= p.d.len() {
            return Err((start, "truncated"));
        }
        let expected = p.d[p.pos];
        let mut c: u32 = 0;
        for i in start..p.pos {
            c = (c * 31 + p.d[i] as u32) % 251;
        }
        if c as u8 != expected {
            return Err((start, "check"));
        }
        p.pos += 1;
        records.push(Record { offset: start, body });
    }
    Ok((records, strict))
}

fn reject(strict: bool, offset: usize, reason: &str) {
    if strict {
        println!("rejected at offset {}: {}", offset, reason);
        exit(3);
    }
}

fn run(records: &[Record], strict: bool) {
    let mut accounts: HashMap<u32, Account> = HashMap::new();
    let mut dup: u64 = 0;
    let mut unknown: u64 = 0;
    let mut rshut: u64 = 0;
    let mut rself: u64 = 0;
    let mut funds: u64 = 0;

    for rec in records {
        match &rec.body {
            Body::Open { id, name, initial } => {
                if accounts.contains_key(id) {
                    reject(strict, rec.offset, "dup");
                    dup += 1;
                } else {
                    accounts.insert(
                        *id,
                        Account {
                            name: name.clone(),
                            balance: *initial as i64,
                            open: true,
                        },
                    );
                }
            }
            Body::Move { from, to, amount } => {
                if !accounts.contains_key(from) || !accounts.contains_key(to) {
                    reject(strict, rec.offset, "unknown");
                    unknown += 1;
                } else {
                    let f_open = accounts[from].open;
                    let t_open = accounts[to].open;
                    if !f_open || !t_open {
                        reject(strict, rec.offset, "shut");
                        rshut += 1;
                    } else if from == to {
                        reject(strict, rec.offset, "self");
                        rself += 1;
                    } else {
                        let amt = *amount as i64;
                        let balance = accounts[from].balance;
                        if amt > balance {
                            reject(strict, rec.offset, "funds");
                            funds += 1;
                        } else {
                            accounts.get_mut(from).unwrap().balance -= amt;
                            accounts.get_mut(to).unwrap().balance += amt;
                        }
                    }
                }
            }
            Body::Shut { id } => match accounts.get_mut(id) {
                None => {
                    reject(strict, rec.offset, "unknown");
                    unknown += 1;
                }
                Some(a) => {
                    if a.open {
                        a.open = false;
                    } else {
                        reject(strict, rec.offset, "shut");
                        rshut += 1;
                    }
                }
            },
            Body::Mint { id, amount } => match accounts.get_mut(id) {
                None => {
                    reject(strict, rec.offset, "unknown");
                    unknown += 1;
                }
                Some(a) => {
                    if a.open {
                        a.balance += *amount as i64;
                    } else {
                        reject(strict, rec.offset, "shut");
                        rshut += 1;
                    }
                }
            },
            Body::Note => {}
        }
    }

    let mut open_count: u64 = 0;
    let mut shut_count: u64 = 0;
    let mut total: i64 = 0;
    for a in accounts.values() {
        if a.open {
            open_count += 1;
        } else {
            shut_count += 1;
        }
        total += a.balance;
    }

    let mut ids: Vec<u32> = accounts.keys().copied().collect();
    ids.sort_unstable();
    let mut g: i64 = 0;
    for id in ids.iter() {
        let a = &accounts[id];
        g = (g * 1000003 + (*id as i64) * 7 + a.balance) % 1000000007;
    }

    println!("records: {}", records.len());
    println!("accounts: {} open, {} shut", open_count, shut_count);
    println!(
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        dup, unknown, rshut, rself, funds
    );
    println!("total: {}", total);

    let mut top: Vec<(&u32, &Account)> = accounts.iter().filter(|(_, a)| a.open).collect();
    top.sort_by(|x, y| y.1.balance.cmp(&x.1.balance).then(x.0.cmp(y.0)));
    for (id, a) in top.iter().take(5) {
        println!("top: {} {} {}", id, String::from_utf8_lossy(&a.name), a.balance);
    }

    println!("digest: {}", g);
}

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    if args.len() != 2 {
        exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };
    match parse(&data) {
        Err((off, kind)) => {
            println!("error at offset {}: {}", off, kind);
            exit(2);
        }
        Ok((records, strict)) => run(&records, strict),
    }
}
