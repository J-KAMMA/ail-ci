use std::collections::BTreeMap;
use std::process::exit;

enum Op {
    Open { id: u64, name: Vec<u8>, initial: u64 },
    Move { from: u64, to: u64, amount: u64 },
    Shut { id: u64 },
    Mint { id: u64, amount: u64 },
    Note,
}

struct Rec {
    offset: usize,
    op: Op,
}

struct Reader<'a> {
    d: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn byte(&mut self) -> Result<u8, &'static str> {
        if self.pos >= self.d.len() {
            return Err("truncated");
        }
        let b = self.d[self.pos];
        self.pos += 1;
        Ok(b)
    }

    fn var(&mut self) -> Result<u64, &'static str> {
        let mut value: u64 = 0;
        for i in 0..5usize {
            let b = self.byte()?;
            if i == 4 && (b & 0x80) != 0 {
                return Err("varint");
            }
            value |= ((b & 0x7f) as u64) << (7 * i);
            if (b & 0x80) == 0 {
                if i >= 1 && b == 0 {
                    return Err("varint");
                }
                if value > 4_294_967_295u64 {
                    return Err("varint");
                }
                return Ok(value);
            }
        }
        Err("varint")
    }
}

type PErr = (usize, &'static str);

fn parse(d: &[u8]) -> Result<Vec<Rec>, PErr> {
    let mut recs = Vec::new();
    let mut r = Reader { d, pos: 6 };
    while r.pos < d.len() {
        let start = r.pos;
        let opcode = r.byte().map_err(|k| (start, k))?;
        let op = match opcode {
            1 => {
                let id = r.var().map_err(|k| (start, k))?;
                let n = r.byte().map_err(|k| (start, k))?;
                if n < 1 || n > 32 {
                    return Err((start, "name"));
                }
                let mut name = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    let b = r.byte().map_err(|k| (start, k))?;
                    if !(0x21..=0x7e).contains(&b) {
                        return Err((start, "name"));
                    }
                    name.push(b);
                }
                let initial = r.var().map_err(|k| (start, k))?;
                Op::Open { id, name, initial }
            }
            2 => {
                let from = r.var().map_err(|k| (start, k))?;
                let to = r.var().map_err(|k| (start, k))?;
                let amount = r.var().map_err(|k| (start, k))?;
                Op::Move { from, to, amount }
            }
            3 => {
                let id = r.var().map_err(|k| (start, k))?;
                Op::Shut { id }
            }
            4 => {
                let id = r.var().map_err(|k| (start, k))?;
                let amount = r.var().map_err(|k| (start, k))?;
                Op::Mint { id, amount }
            }
            5 => {
                let len = r.var().map_err(|k| (start, k))?;
                let remaining = (d.len() - r.pos) as u64;
                if len > remaining {
                    return Err((start, "truncated"));
                }
                r.pos += len as usize;
                Op::Note
            }
            _ => return Err((start, "opcode")),
        };
        let body_end = r.pos;
        let chk = r.byte().map_err(|k| (start, k))?;
        let mut c: u64 = 0;
        for &b in &d[start..body_end] {
            c = (c * 31 + b as u64) % 251;
        }
        if chk as u64 != c {
            return Err((start, "check"));
        }
        recs.push(Rec { offset: start, op });
    }
    Ok(recs)
}

struct Acc {
    name: Vec<u8>,
    bal: i64,
    open: bool,
}

const REASONS: [&str; 5] = ["dup", "unknown", "shut", "self", "funds"];

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };

    // Header
    let header_ok = data.len() >= 6
        && data[0..4] == [0xC7, 0x4C, 0x58, 0x46]
        && data[4] == 0x02
        && (data[5] & 0xFE) == 0;
    if !header_ok {
        println!("error at offset 0: header");
        exit(2);
    }
    let strict = (data[5] & 1) == 1;

    let recs = match parse(&data) {
        Ok(r) => r,
        Err((off, kind)) => {
            println!("error at offset {}: {}", off, kind);
            exit(2);
        }
    };

    let mut accts: BTreeMap<u64, Acc> = BTreeMap::new();
    let mut rej = [0u64; 5];

    for rec in &recs {
        let reject: Option<usize> = match &rec.op {
            Op::Open { id, name, initial } => {
                if accts.contains_key(id) {
                    Some(0)
                } else {
                    accts.insert(
                        *id,
                        Acc {
                            name: name.clone(),
                            bal: *initial as i64,
                            open: true,
                        },
                    );
                    None
                }
            }
            Op::Move { from, to, amount } => {
                let fi = accts.get(from).map(|a| (a.open, a.bal));
                let ti = accts.get(to).map(|a| (a.open, a.bal));
                match (fi, ti) {
                    (None, _) | (_, None) => Some(1),
                    (Some((fo, fb)), Some((tope, _))) => {
                        if !fo || !tope {
                            Some(2)
                        } else if from == to {
                            Some(3)
                        } else if (*amount as i64) > fb {
                            Some(4)
                        } else {
                            let a = *amount as i64;
                            accts.get_mut(from).unwrap().bal -= a;
                            accts.get_mut(to).unwrap().bal += a;
                            None
                        }
                    }
                }
            }
            Op::Shut { id } => match accts.get_mut(id) {
                None => Some(1),
                Some(a) => {
                    if !a.open {
                        Some(2)
                    } else {
                        a.open = false;
                        None
                    }
                }
            },
            Op::Mint { id, amount } => match accts.get_mut(id) {
                None => Some(1),
                Some(a) => {
                    if !a.open {
                        Some(2)
                    } else {
                        a.bal += *amount as i64;
                        None
                    }
                }
            },
            Op::Note => None,
        };

        if let Some(k) = reject {
            if strict {
                println!("rejected at offset {}: {}", rec.offset, REASONS[k]);
                exit(3);
            }
            rej[k] += 1;
        }
    }

    let mut open_cnt = 0u64;
    let mut shut_cnt = 0u64;
    let mut total: i64 = 0;
    for a in accts.values() {
        if a.open {
            open_cnt += 1;
        } else {
            shut_cnt += 1;
        }
        total += a.bal;
    }

    let mut opens: Vec<(u64, &Acc)> = accts
        .iter()
        .filter(|(_, a)| a.open)
        .map(|(id, a)| (*id, a))
        .collect();
    opens.sort_by(|x, y| y.1.bal.cmp(&x.1.bal).then(x.0.cmp(&y.0)));

    const MOD: i64 = 1_000_000_007;
    let mut g: i64 = 0;
    for (id, a) in &accts {
        let term = ((*id as i64) * 7 + a.bal) % MOD;
        g = (g * 1_000_003 + term) % MOD;
    }

    println!("records: {}", recs.len());
    println!("accounts: {} open, {} shut", open_cnt, shut_cnt);
    println!(
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        rej[0], rej[1], rej[2], rej[3], rej[4]
    );
    println!("total: {}", total);
    for (id, a) in opens.iter().take(5) {
        println!(
            "top: {} {} {}",
            id,
            String::from_utf8_lossy(&a.name),
            a.bal
        );
    }
    println!("digest: {}", g);
    exit(0);
}
