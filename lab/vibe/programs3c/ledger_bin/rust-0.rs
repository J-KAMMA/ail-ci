use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::process;

enum Rec {
    Open { id: u64, name: Vec<u8>, initial: u64 },
    Move { from: u64, to: u64, amount: u64 },
    Shut { id: u64 },
    Mint { id: u64, amount: u64 },
    Note,
}

struct Parsed {
    start: usize,
    rec: Rec,
}

struct Acc {
    name: Vec<u8>,
    bal: i64,
    shut: bool,
}

fn fail(off: usize, kind: &str) -> ! {
    println!("error at offset {}: {}", off, kind);
    process::exit(2);
}

fn read_var(data: &[u8], p: &mut usize, start: usize) -> u64 {
    let mut value: u64 = 0;
    let mut i: u32 = 0;
    loop {
        if *p >= data.len() {
            fail(start, "truncated");
        }
        let b = data[*p];
        *p += 1;
        value |= ((b & 0x7f) as u64) << (7 * i);
        if b & 0x80 == 0 {
            if i >= 1 && b == 0 {
                fail(start, "varint");
            }
            if value > 4294967295u64 {
                fail(start, "varint");
            }
            return value;
        }
        if i == 4 {
            fail(start, "varint");
        }
        i += 1;
    }
}

fn parse(data: &[u8]) -> Vec<Parsed> {
    let mut recs = Vec::new();
    let mut pos = 6usize;
    while pos < data.len() {
        let start = pos;
        let op = data[pos];
        let mut p = pos + 1;
        let rec = match op {
            1 => {
                let id = read_var(data, &mut p, start);
                if p >= data.len() {
                    fail(start, "truncated");
                }
                let nl = data[p] as usize;
                p += 1;
                if nl < 1 || nl > 32 {
                    fail(start, "name");
                }
                let mut name = Vec::with_capacity(nl);
                for _ in 0..nl {
                    if p >= data.len() {
                        fail(start, "truncated");
                    }
                    let b = data[p];
                    p += 1;
                    if !(0x21..=0x7e).contains(&b) {
                        fail(start, "name");
                    }
                    name.push(b);
                }
                let initial = read_var(data, &mut p, start);
                Rec::Open { id, name, initial }
            }
            2 => {
                let from = read_var(data, &mut p, start);
                let to = read_var(data, &mut p, start);
                let amount = read_var(data, &mut p, start);
                Rec::Move { from, to, amount }
            }
            3 => {
                let id = read_var(data, &mut p, start);
                Rec::Shut { id }
            }
            4 => {
                let id = read_var(data, &mut p, start);
                let amount = read_var(data, &mut p, start);
                Rec::Mint { id, amount }
            }
            5 => {
                let len = read_var(data, &mut p, start);
                let remaining = (data.len() - p) as u64;
                if len > remaining {
                    fail(start, "truncated");
                }
                p += len as usize;
                Rec::Note
            }
            _ => fail(start, "opcode"),
        };
        let mut c: u64 = 0;
        for &b in &data[start..p] {
            c = (c * 31 + b as u64) % 251;
        }
        if p >= data.len() {
            fail(start, "truncated");
        }
        if data[p] as u64 != c {
            fail(start, "check");
        }
        p += 1;
        recs.push(Parsed { start, rec });
        pos = p;
    }
    recs
}

fn apply(accts: &mut BTreeMap<u64, Acc>, rec: &Rec) -> Option<&'static str> {
    match rec {
        Rec::Open { id, name, initial } => {
            if accts.contains_key(id) {
                return Some("dup");
            }
            accts.insert(
                *id,
                Acc {
                    name: name.clone(),
                    bal: *initial as i64,
                    shut: false,
                },
            );
            None
        }
        Rec::Move { from, to, amount } => {
            if !accts.contains_key(from) || !accts.contains_key(to) {
                return Some("unknown");
            }
            let fsh = accts[from].shut;
            let tsh = accts[to].shut;
            if fsh || tsh {
                return Some("shut");
            }
            if from == to {
                return Some("self");
            }
            let amt = *amount as i64;
            if amt > accts[from].bal {
                return Some("funds");
            }
            accts.get_mut(from).unwrap().bal -= amt;
            accts.get_mut(to).unwrap().bal += amt;
            None
        }
        Rec::Shut { id } => match accts.get_mut(id) {
            None => Some("unknown"),
            Some(a) => {
                if a.shut {
                    Some("shut")
                } else {
                    a.shut = true;
                    None
                }
            }
        },
        Rec::Mint { id, amount } => match accts.get_mut(id) {
            None => Some("unknown"),
            Some(a) => {
                if a.shut {
                    Some("shut")
                } else {
                    a.bal += *amount as i64;
                    None
                }
            }
        },
        Rec::Note => None,
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let data = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => process::exit(1),
    };

    if data.len() < 6
        || data[0] != 0xC7
        || data[1] != 0x4C
        || data[2] != 0x58
        || data[3] != 0x46
        || data[4] != 2
        || (data[5] & !1u8) != 0
    {
        fail(0, "header");
    }
    let strict = data[5] & 1 == 1;

    let recs = parse(&data);

    let mut accts: BTreeMap<u64, Acc> = BTreeMap::new();
    let mut rej = [0u64; 5];
    for pr in &recs {
        if let Some(r) = apply(&mut accts, &pr.rec) {
            if strict {
                println!("rejected at offset {}: {}", pr.start, r);
                process::exit(3);
            }
            let idx = match r {
                "dup" => 0,
                "unknown" => 1,
                "shut" => 2,
                "self" => 3,
                _ => 4,
            };
            rej[idx] += 1;
        }
    }

    let open_count = accts.values().filter(|a| !a.shut).count();
    let shut_count = accts.values().filter(|a| a.shut).count();
    let total: i64 = accts.values().map(|a| a.bal).sum();

    let mut open_list: Vec<(u64, &Acc)> = accts
        .iter()
        .filter(|(_, a)| !a.shut)
        .map(|(id, a)| (*id, a))
        .collect();
    open_list.sort_by(|x, y| y.1.bal.cmp(&x.1.bal).then(x.0.cmp(&y.0)));

    let mut g: i128 = 0;
    for (id, a) in &accts {
        g = (g * 1000003 + (*id as i128) * 7 + a.bal as i128).rem_euclid(1000000007);
    }

    println!("records: {}", recs.len());
    println!("accounts: {} open, {} shut", open_count, shut_count);
    println!(
        "rejected: dup={} unknown={} shut={} self={} funds={}",
        rej[0], rej[1], rej[2], rej[3], rej[4]
    );
    println!("total: {}", total);
    for (id, a) in open_list.iter().take(5) {
        println!(
            "top: {} {} {}",
            id,
            String::from_utf8_lossy(&a.name),
            a.bal
        );
    }
    println!("digest: {}", g);
    process::exit(0);
}
