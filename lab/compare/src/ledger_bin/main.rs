use std::collections::BTreeMap;
use std::io::Write;

enum Rec {
    Open(u32, Vec<u8>, u32),
    Move(u32, u32, u32),
    Shut(u32),
    Mint(u32, u32),
    Note,
}

struct P<'a> {
    d: &'a [u8],
    p: usize,
}

impl<'a> P<'a> {
    fn byte(&mut self) -> Result<u8, &'static str> {
        if self.p >= self.d.len() {
            return Err("truncated");
        }
        let b = self.d[self.p];
        self.p += 1;
        Ok(b)
    }
    fn var(&mut self) -> Result<u32, &'static str> {
        let mut v: u64 = 0;
        let mut n = 0;
        let mut last;
        loop {
            let b = self.byte()?;
            last = b;
            v |= ((b & 0x7f) as u64) << (7 * n);
            n += 1;
            if b & 0x80 == 0 {
                break;
            }
            if n == 5 {
                return Err("varint");
            }
        }
        if n >= 2 && last == 0 {
            return Err("varint");
        }
        if v > 0xFFFF_FFFF {
            return Err("varint");
        }
        Ok(v as u32)
    }
    fn record(&mut self) -> Result<Rec, &'static str> {
        let start = self.p;
        let op = self.byte()?;
        let r = match op {
            1 => {
                let id = self.var()?;
                let nl = self.byte()?;
                if nl < 1 || nl > 32 {
                    return Err("name");
                }
                let mut name = Vec::new();
                for _ in 0..nl {
                    let b = self.byte()?;
                    if b < 0x21 || b > 0x7e {
                        return Err("name");
                    }
                    name.push(b);
                }
                let init = self.var()?;
                Rec::Open(id, name, init)
            }
            2 => {
                let a = self.var()?;
                let b = self.var()?;
                let c = self.var()?;
                Rec::Move(a, b, c)
            }
            3 => Rec::Shut(self.var()?),
            4 => {
                let a = self.var()?;
                let b = self.var()?;
                Rec::Mint(a, b)
            }
            5 => {
                let l = self.var()? as usize;
                if self.d.len() - self.p < l {
                    return Err("truncated");
                }
                self.p += l;
                Rec::Note
            }
            _ => return Err("opcode"),
        };
        let end = self.p;
        let cb = self.byte()?;
        let mut c: u32 = 0;
        for &b in &self.d[start..end] {
            c = (c * 31 + b as u32) % 251;
        }
        if cb as u32 != c {
            return Err("check");
        }
        Ok(r)
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        std::process::exit(1);
    }
    let d = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => std::process::exit(1),
    };
    if d.len() < 6 || d[0..4] != [0xC7, 0x4C, 0x58, 0x46] || d[4] != 2 || d[5] > 1 {
        println!("error at offset 0: header");
        std::process::exit(2);
    }
    let strict = d[5] == 1;
    let mut p = P { d: &d, p: 6 };
    let mut recs: Vec<(usize, Rec)> = Vec::new();
    while p.p < d.len() {
        let x = p.p;
        match p.record() {
            Ok(r) => recs.push((x, r)),
            Err(k) => {
                println!("error at offset {}: {}", x, k);
                std::process::exit(2);
            }
        }
    }
    // (name, balance, shut)
    let mut acc: BTreeMap<u32, (Vec<u8>, i128, bool)> = BTreeMap::new();
    let mut rej = [0u64; 5]; // dup unknown shut self funds
    let names = ["dup", "unknown", "shut", "self", "funds"];
    for (x, r) in &recs {
        let res: Option<usize> = match r {
            Rec::Open(id, name, init) => {
                if acc.contains_key(id) {
                    Some(0)
                } else {
                    acc.insert(*id, (name.clone(), *init as i128, false));
                    None
                }
            }
            Rec::Move(f, t, a) => {
                if !acc.contains_key(f) || !acc.contains_key(t) {
                    Some(1)
                } else if acc[f].2 || acc[t].2 {
                    Some(2)
                } else if f == t {
                    Some(3)
                } else if (*a as i128) > acc[f].1 {
                    Some(4)
                } else {
                    acc.get_mut(f).unwrap().1 -= *a as i128;
                    acc.get_mut(t).unwrap().1 += *a as i128;
                    None
                }
            }
            Rec::Shut(id) => match acc.get_mut(id) {
                None => Some(1),
                Some(a) if a.2 => Some(2),
                Some(a) => {
                    a.2 = true;
                    None
                }
            },
            Rec::Mint(id, amt) => match acc.get_mut(id) {
                None => Some(1),
                Some(a) if a.2 => Some(2),
                Some(a) => {
                    a.1 += *amt as i128;
                    None
                }
            },
            Rec::Note => None,
        };
        if let Some(k) = res {
            if strict {
                println!("rejected at offset {}: {}", x, names[k]);
                std::process::exit(3);
            }
            rej[k] += 1;
        }
    }
    let open = acc.values().filter(|a| !a.2).count();
    let shut = acc.len() - open;
    let total: i128 = acc.values().map(|a| a.1).sum();
    let mut g: i128 = 0;
    for (id, a) in &acc {
        g = (g * 1000003 + (*id as i128) * 7 + a.1) % 1000000007;
    }
    let mut top: Vec<(&u32, &(Vec<u8>, i128, bool))> = acc.iter().filter(|(_, a)| !a.2).collect();
    top.sort_by(|a, b| b.1 .1.cmp(&a.1 .1).then(a.0.cmp(b.0)));
    let mut o = String::new();
    o.push_str(&format!("records: {}\n", recs.len()));
    o.push_str(&format!("accounts: {} open, {} shut\n", open, shut));
    o.push_str(&format!(
        "rejected: dup={} unknown={} shut={} self={} funds={}\n",
        rej[0], rej[1], rej[2], rej[3], rej[4]
    ));
    o.push_str(&format!("total: {}\n", total));
    for (id, a) in top.iter().take(5) {
        o.push_str(&format!("top: {} {} {}\n", id, String::from_utf8_lossy(&a.0), a.1));
    }
    o.push_str(&format!("digest: {}\n", g));
    std::io::stdout().write_all(o.as_bytes()).unwrap();
}
