use std::env;
use std::ffi::OsString;
use std::io::{self, Read, Write};
use std::process::exit;

fn fail() -> ! {
    eprintln!("error");
    exit(1);
}

fn code_val(c: u8) -> Option<usize> {
    match c {
        b'0'..=b'9' => Some((c - b'0') as usize),
        b'A' => Some(10),
        b'B' => Some(11),
        b'C' => Some(12),
        _ => None,
    }
}

fn parse_list(s: &[u8]) -> Option<[bool; 13]> {
    let mut m = [false; 13];
    let mut last: i64 = -1;
    for &c in s {
        let v = code_val(c)? as i64;
        if v <= last {
            return None;
        }
        last = v;
        m[v as usize] = true;
    }
    Some(m)
}

fn parse_rule(r: &[u8]) -> Option<([bool; 13], [bool; 13])> {
    if r.first() != Some(&b'B') {
        return None;
    }
    let slash = r.iter().position(|&c| c == b'/')?;
    let bpart = &r[1..slash];
    let rest = &r[slash + 1..];
    if rest.first() != Some(&b'S') {
        return None;
    }
    let spart = &rest[1..];
    Some((parse_list(bpart)?, parse_list(spart)?))
}

fn parse_gens(s: &[u8]) -> Option<usize> {
    if s.is_empty() {
        return None;
    }
    let mut v: u64 = 0;
    for &c in s {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (c - b'0') as u64;
        if v > 100000 {
            return None;
        }
    }
    Some(v as usize)
}

fn parse_dim(s: &[u8]) -> Option<usize> {
    if s.is_empty() || s[0] == b'0' {
        return None;
    }
    let mut v: u64 = 0;
    for &c in s {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (c - b'0') as u64;
        if v > 4096 {
            return None;
        }
    }
    if v < 1 {
        return None;
    }
    Some(v as usize)
}

fn parse_grid(data: &[u8]) -> Option<(usize, usize, Vec<u8>)> {
    let nl = data.iter().position(|&c| c == b'\n')?;
    let header = &data[..nl];
    let parts: Vec<&[u8]> = header.split(|&c| c == b' ').collect();
    if parts.len() != 2 {
        return None;
    }
    let w = parse_dim(parts[0])?;
    let h = parse_dim(parts[1])?;
    let mut pos = nl + 1;
    let mut cells = Vec::with_capacity(w * h);
    for y in 0..h {
        if pos + w > data.len() {
            return None;
        }
        for &c in &data[pos..pos + w] {
            match c {
                b'.' => cells.push(0u8),
                b'o' => cells.push(1u8),
                _ => return None,
            }
        }
        pos += w;
        if y + 1 < h {
            if pos >= data.len() || data[pos] != b'\n' {
                return None;
            }
            pos += 1;
        } else {
            if pos == data.len() {
                // no trailing newline
            } else if pos + 1 == data.len() && data[pos] == b'\n' {
                // optional trailing newline
            } else {
                return None;
            }
        }
    }
    Some((w, h, cells))
}

fn main() {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    if args.len() != 2 {
        fail();
    }
    let rule_str = match args[0].to_str() {
        Some(s) => s.as_bytes().to_vec(),
        None => fail(),
    };
    let gens_str = match args[1].to_str() {
        Some(s) => s.as_bytes().to_vec(),
        None => fail(),
    };
    let (bmask, smask) = match parse_rule(&rule_str) {
        Some(x) => x,
        None => fail(),
    };
    let gens = match parse_gens(&gens_str) {
        Some(g) => g,
        None => fail(),
    };

    let mut data = Vec::new();
    if io::stdin().read_to_end(&mut data).is_err() {
        fail();
    }
    let (w, h, cells) = match parse_grid(&data) {
        Some(x) => x,
        None => fail(),
    };

    let n = w * h;
    let mut cur = cells;
    let mut nxt = vec![0u8; n];

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for g in 1..=gens {
        for y in 0..h {
            let up = (y + h - 1) % h;
            let dn = (y + 1) % h;
            for x in 0..w {
                let l = (x + w - 1) % w;
                let r = (x + 1) % w;
                let a = |yy: usize, xx: usize| -> usize { (cur[yy * w + xx] == 1) as usize };
                let wt = 2 * (a(up, x) + a(dn, x) + a(y, l) + a(y, r))
                    + a(up, l)
                    + a(up, r)
                    + a(dn, l)
                    + a(dn, r);
                let st = cur[y * w + x];
                nxt[y * w + x] = match st {
                    1 => {
                        if smask[wt] {
                            1
                        } else {
                            2
                        }
                    }
                    0 => {
                        if bmask[wt] {
                            1
                        } else {
                            0
                        }
                    }
                    _ => 0,
                };
            }
        }
        std::mem::swap(&mut cur, &mut nxt);
        let mut alive = 0usize;
        let mut scars = 0usize;
        for &s in &cur {
            if s == 1 {
                alive += 1;
            } else if s == 2 {
                scars += 1;
            }
        }
        let _ = writeln!(out, "{} {} {}", g, alive, scars);
    }

    let mut line = Vec::with_capacity(w + 1);
    for y in 0..h {
        line.clear();
        for x in 0..w {
            line.push(match cur[y * w + x] {
                0 => b'.',
                1 => b'o',
                _ => b'x',
            });
        }
        line.push(b'\n');
        let _ = out.write_all(&line);
    }
    let _ = out.flush();
}
