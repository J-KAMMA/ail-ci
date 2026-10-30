use std::io::{Read, Write};
use std::process::exit;

fn fail() -> ! {
    eprintln!("error");
    exit(1);
}

fn code(c: u8) -> Option<usize> {
    match c {
        b'0'..=b'9' => Some((c - b'0') as usize),
        b'A'..=b'C' => Some((c - b'A') as usize + 10),
        _ => None,
    }
}

fn parse_list(s: &[u8]) -> [bool; 13] {
    let mut t = [false; 13];
    let mut prev: i32 = -1;
    for &c in s {
        let v = match code(c) {
            Some(v) => v,
            None => fail(),
        };
        if (v as i32) <= prev {
            fail();
        }
        prev = v as i32;
        t[v] = true;
    }
    t
}

fn parse_num(s: &[u8]) -> Option<usize> {
    if s.is_empty() || s.len() > 6 || !s.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let mut v = 0usize;
    for &c in s {
        v = v * 10 + (c - b'0') as usize;
    }
    Some(v)
}

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    if args.len() != 3 {
        fail();
    }
    let rule = match args[1].to_str() {
        Some(s) => s.as_bytes().to_vec(),
        None => fail(),
    };
    let gens_s = match args[2].to_str() {
        Some(s) => s.as_bytes().to_vec(),
        None => fail(),
    };
    if rule.is_empty() || rule[0] != b'B' {
        fail();
    }
    let slash = match rule.iter().position(|&c| c == b'/') {
        Some(p) => p,
        None => fail(),
    };
    if rule.len() < slash + 2 || rule[slash + 1] != b'S' {
        fail();
    }
    let birth = parse_list(&rule[1..slash]);
    let surv = parse_list(&rule[slash + 2..]);
    // GENS: strip leading zeros to allow long zero padding
    let mut gs = &gens_s[..];
    if gs.is_empty() || !gs.iter().all(|c| c.is_ascii_digit()) {
        fail();
    }
    while gs.len() > 1 && gs[0] == b'0' {
        gs = &gs[1..];
    }
    let gens = match parse_num(gs) {
        Some(v) if v <= 100000 => v,
        _ => fail(),
    };

    let mut data = Vec::new();
    if std::io::stdin().read_to_end(&mut data).is_err() {
        fail();
    }
    let nl = match data.iter().position(|&c| c == b'\n') {
        Some(p) => p,
        None => fail(),
    };
    let head = &data[..nl];
    let sp = match head.iter().position(|&c| c == b' ') {
        Some(p) => p,
        None => fail(),
    };
    let (ws, hs) = (&head[..sp], &head[sp + 1..]);
    for s in [ws, hs] {
        if s.is_empty() || s[0] == b'0' {
            fail();
        }
    }
    let w = match parse_num(ws) {
        Some(v) if v >= 1 && v <= 4096 => v,
        _ => fail(),
    };
    let h = match parse_num(hs) {
        Some(v) if v >= 1 && v <= 4096 => v,
        _ => fail(),
    };
    let mut rest = &data[nl + 1..];
    if let Some(&b'\n') = rest.last() {
        rest = &rest[..rest.len() - 1];
    }
    if rest.len() != h * w + (h - 1) {
        fail();
    }
    // state: 0 dead, 1 alive, 2 scar
    let mut cur = vec![0u8; w * h];
    for y in 0..h {
        let line = &rest[y * (w + 1)..y * (w + 1) + w];
        for x in 0..w {
            cur[y * w + x] = match line[x] {
                b'.' => 0,
                b'o' => 1,
                _ => fail(),
            };
        }
        if y + 1 < h && rest[y * (w + 1) + w] != b'\n' {
            fail();
        }
    }

    let xl: Vec<usize> = (0..w).map(|x| (x + w - 1) % w).collect();
    let xr: Vec<usize> = (0..w).map(|x| (x + 1) % w).collect();
    let mut nxt = vec![0u8; w * h];
    let mut out = String::new();
    for g in 1..=gens {
        let mut na = 0usize;
        let mut ns = 0usize;
        for y in 0..h {
            let yu = (y + h - 1) % h;
            let yd = (y + 1) % h;
            let ru = &cur[yu * w..yu * w + w];
            let rc = &cur[y * w..y * w + w];
            let rd = &cur[yd * w..yd * w + w];
            let rn = &mut nxt[y * w..y * w + w];
            for x in 0..w {
                let l = xl[x];
                let r = xr[x];
                let a = |v: u8| (v & 1) as usize;
                let wt = 2 * (a(ru[x]) + a(rd[x]) + a(rc[l]) + a(rc[r]))
                    + a(ru[l])
                    + a(ru[r])
                    + a(rd[l])
                    + a(rd[r]);
                let s = match rc[x] {
                    1 => {
                        if surv[wt] {
                            1
                        } else {
                            2
                        }
                    }
                    0 => {
                        if birth[wt] {
                            1
                        } else {
                            0
                        }
                    }
                    _ => 0,
                };
                if s == 1 {
                    na += 1;
                } else if s == 2 {
                    ns += 1;
                }
                rn[x] = s;
            }
        }
        std::mem::swap(&mut cur, &mut nxt);
        out.push_str(&format!("{} {} {}\n", g, na, ns));
    }
    let mut o = Vec::with_capacity(out.len() + h * (w + 1));
    o.extend_from_slice(out.as_bytes());
    for y in 0..h {
        for x in 0..w {
            o.push(match cur[y * w + x] {
                0 => b'.',
                1 => b'o',
                _ => b'x',
            });
        }
        o.push(b'\n');
    }
    let so = std::io::stdout();
    let mut so = so.lock();
    let _ = so.write_all(&o);
    let _ = so.flush();
}
