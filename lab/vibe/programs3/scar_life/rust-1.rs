use std::io::{self, Read, Write};

fn weight_code(c: u8) -> Option<u8> {
    match c {
        b'0'..=b'9' => Some(c - b'0'),
        b'A' => Some(10),
        b'B' => Some(11),
        b'C' => Some(12),
        _ => None,
    }
}

fn parse_rule(b: &[u8]) -> Option<(u16, u16)> {
    let mut i = 0usize;
    if i >= b.len() || b[i] != b'B' {
        return None;
    }
    i += 1;

    let mut bmask: u16 = 0;
    let mut last: i32 = -1;
    while i < b.len() && b[i] != b'/' {
        let v = weight_code(b[i])?;
        if (v as i32) <= last {
            return None;
        }
        last = v as i32;
        bmask |= 1u16 << (v as u32);
        i += 1;
    }
    if i >= b.len() || b[i] != b'/' {
        return None;
    }
    i += 1;
    if i >= b.len() || b[i] != b'S' {
        return None;
    }
    i += 1;

    let mut smask: u16 = 0;
    last = -1;
    while i < b.len() {
        let v = weight_code(b[i])?;
        if (v as i32) <= last {
            return None;
        }
        last = v as i32;
        smask |= 1u16 << (v as u32);
        i += 1;
    }

    Some((bmask, smask))
}

fn parse_gens(b: &[u8]) -> Option<u32> {
    if b.is_empty() {
        return None;
    }
    let mut v: u32 = 0;
    for &ch in b {
        if !ch.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (ch - b'0') as u32;
        if v > 100000 {
            return None;
        }
    }
    Some(v)
}

fn parse_dim(b: &[u8]) -> Option<usize> {
    if b.is_empty() || b.len() > 4 {
        return None;
    }
    if b.len() > 1 && b[0] == b'0' {
        return None;
    }
    let mut v: usize = 0;
    for &ch in b {
        if !ch.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (ch - b'0') as usize;
    }
    if v < 1 || v > 4096 {
        return None;
    }
    Some(v)
}

fn parse_header(header: &[u8]) -> Option<(usize, usize)> {
    let mut i = 0usize;
    while i < header.len() && header[i].is_ascii_digit() {
        i += 1;
    }
    if i == 0 {
        return None;
    }
    let wpart = &header[..i];
    if i >= header.len() || header[i] != b' ' {
        return None;
    }
    i += 1;
    let hstart = i;
    while i < header.len() && header[i].is_ascii_digit() {
        i += 1;
    }
    if i == hstart {
        return None;
    }
    if i != header.len() {
        return None;
    }
    let hpart = &header[hstart..];
    let w = parse_dim(wpart)?;
    let h = parse_dim(hpart)?;
    Some((w, h))
}

fn parse_input(data: &[u8]) -> Option<(usize, usize, Vec<u8>)> {
    let nl = data.iter().position(|&x| x == b'\n')?;
    let header = &data[..nl];
    let (w, h) = parse_header(header)?;

    let mut cur = nl + 1;
    let mut state = vec![0u8; w * h];

    for r in 0..h {
        let rest = &data[cur..];
        match rest.iter().position(|&x| x == b'\n') {
            Some(p) => {
                let line = &rest[..p];
                if line.len() != w {
                    return None;
                }
                for (c, &x) in line.iter().enumerate() {
                    state[r * w + c] = match x {
                        b'.' => 0,
                        b'o' => 1,
                        _ => return None,
                    };
                }
                cur += p + 1;
                if r == h - 1 && cur != data.len() {
                    return None;
                }
            }
            None => {
                if r != h - 1 {
                    return None;
                }
                if rest.len() != w {
                    return None;
                }
                for (c, &x) in rest.iter().enumerate() {
                    state[r * w + c] = match x {
                        b'.' => 0,
                        b'o' => 1,
                        _ => return None,
                    };
                }
                cur = data.len();
            }
        }
    }

    if cur != data.len() {
        return None;
    }
    Some((w, h, state))
}

fn simulate_and_print(w: usize, h: usize, start: Vec<u8>, gens: u32, bmask: u16, smask: u16) {
    let n = w * h;
    let mut cur = start;
    let mut next = vec![0u8; n];

    let mut up_row = vec![0usize; h];
    let mut down_row = vec![0usize; h];
    for r in 0..h {
        up_row[r] = if r == 0 { h - 1 } else { r - 1 };
        down_row[r] = if r + 1 == h { 0 } else { r + 1 };
    }

    let mut left_col = vec![0usize; w];
    let mut right_col = vec![0usize; w];
    for c in 0..w {
        left_col[c] = if c == 0 { w - 1 } else { c - 1 };
        right_col[c] = if c + 1 == w { 0 } else { c + 1 };
    }

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout);

    for g in 1..=gens {
        let mut alive: u64 = 0;
        let mut scar: u64 = 0;

        for r in 0..h {
            let row_u = up_row[r] * w;
            let row_d = down_row[r] * w;
            let row_c = r * w;
            for c in 0..w {
                let l = left_col[c];
                let rr = right_col[c];

                let weight: u32 = 2 * ((cur[row_u + c] & 1) as u32
                    + (cur[row_d + c] & 1) as u32
                    + (cur[row_c + l] & 1) as u32
                    + (cur[row_c + rr] & 1) as u32)
                    + ((cur[row_u + l] & 1) as u32
                        + (cur[row_u + rr] & 1) as u32
                        + (cur[row_d + l] & 1) as u32
                        + (cur[row_d + rr] & 1) as u32);

                let s = cur[row_c + c];
                let ns: u8 = match s {
                    1 => {
                        if ((smask as u32) >> weight) & 1 == 1 {
                            1
                        } else {
                            2
                        }
                    }
                    0 => {
                        if ((bmask as u32) >> weight) & 1 == 1 {
                            1
                        } else {
                            0
                        }
                    }
                    _ => 0,
                };

                next[row_c + c] = ns;
                if ns == 1 {
                    alive += 1;
                } else if ns == 2 {
                    scar += 1;
                }
            }
        }

        let _ = writeln!(out, "{} {} {}", g, alive, scar);
        std::mem::swap(&mut cur, &mut next);
    }

    for r in 0..h {
        let row = &cur[r * w..(r + 1) * w];
        let mut line = Vec::with_capacity(w + 1);
        for &s in row {
            line.push(match s {
                1 => b'o',
                2 => b'x',
                _ => b'.',
            });
        }
        line.push(b'\n');
        let _ = out.write_all(&line);
    }
    let _ = out.flush();
}

fn run() -> Option<()> {
    let mut args = std::env::args_os();
    let _prog = args.next();
    let rule_arg = args.next()?;
    let gens_arg = args.next()?;
    if args.next().is_some() {
        return None;
    }

    let rule_s = rule_arg.to_str()?;
    let gens_s = gens_arg.to_str()?;

    let (bmask, smask) = parse_rule(rule_s.as_bytes())?;
    let gens = parse_gens(gens_s.as_bytes())?;

    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).ok()?;
    let (w, h, start) = parse_input(&data)?;

    simulate_and_print(w, h, start, gens, bmask, smask);
    Some(())
}

fn main() {
    if run().is_none() {
        std::process::exit(1);
    }
}
