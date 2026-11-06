use std::env;
use std::io::{self, Read, Write};
use std::process;

fn invalid() -> ! {
    process::exit(1);
}

fn parse_dim(tok: &[u8]) -> Option<usize> {
    if tok.is_empty() {
        return None;
    }
    if tok.len() > 1 && tok[0] == b'0' {
        return None;
    }
    let mut v: usize = 0;
    for &c in tok {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v.checked_mul(10)?.checked_add((c - b'0') as usize)?;
    }
    if (1..=4096).contains(&v) {
        Some(v)
    } else {
        None
    }
}

fn parse_codes(codes: &[u8]) -> Option<[bool; 13]> {
    let mut result = [false; 13];
    let mut prev: i32 = -1;

    for &c in codes {
        let code: i32 = if c.is_ascii_digit() {
            (c - b'0') as i32
        } else {
            match c {
                b'A' => 10,
                b'B' => 11,
                b'C' => 12,
                _ => return None,
            }
        };

        if code <= prev {
            return None;
        }
        prev = code;
        result[code as usize] = true;
    }

    Some(result)
}

fn parse_rule(s: &str) -> Option<([bool; 13], [bool; 13])> {
    let b = s.as_bytes();

    if b.first() != Some(&b'B') {
        return None;
    }

    let slash = b.iter().position(|&c| c == b'/')?;

    if b.get(slash + 1) != Some(&b'S') {
        return None;
    }

    let birth = parse_codes(&b[1..slash])?;
    let survive = parse_codes(&b[slash + 2..])?;

    Some((birth, survive))
}

fn parse_gens(s: &str) -> Option<usize> {
    let b = s.as_bytes();
    if b.is_empty() {
        return None;
    }

    let mut v: u64 = 0;
    for &c in b {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v.checked_mul(10)?.checked_add((c - b'0') as u64)?;
    }

    if v <= 100_000 {
        Some(v as usize)
    } else {
        None
    }
}

fn parse_grid(data: &[u8]) -> Option<(usize, usize, Vec<u8>)> {
    let first_newline = data.iter().position(|&b| b == b'\n')?;
    let header = &data[..first_newline];

    let space = header.iter().position(|&b| b == b' ')?;
    let w = parse_dim(&header[..space])?;
    let h = parse_dim(&header[space + 1..])?;

    let mut pos = first_newline + 1;
    let mut grid = Vec::with_capacity(w.checked_mul(h)?);

    for y in 0..h {
        if data.len() - pos < w {
            return None;
        }

        let row = &data[pos..pos + w];
        for &b in row {
            match b {
                b'.' => grid.push(0),
                b'o' => grid.push(1),
                _ => return None,
            }
        }
        pos += w;

        if y + 1 < h {
            if pos >= data.len() || data[pos] != b'\n' {
                return None;
            }
            pos += 1;
        } else if pos < data.len() {
            if data[pos] != b'\n' {
                return None;
            }
            pos += 1;
        }
    }

    if pos != data.len() {
        return None;
    }

    Some((w, h, grid))
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() != 2 {
        invalid();
    }

    let rule_s = match args[0].to_str() {
        Some(s) => s,
        None => invalid(),
    };
    let gens_s = match args[1].to_str() {
        Some(s) => s,
        None => invalid(),
    };

    let (birth, survive) = match parse_rule(rule_s) {
        Some(r) => r,
        None => invalid(),
    };
    let gens = match parse_gens(gens_s) {
        Some(g) => g,
        None => invalid(),
    };

    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        invalid();
    }

    let (w, h, mut cur) = match parse_grid(&input) {
        Some(g) => g,
        None => invalid(),
    };

    let n = w * h;
    let mut next = vec![0u8; n];

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for g in 1..=gens {
        let mut alive = 0usize;
        let mut scars = 0usize;

        for y in 0..h {
            let row = y * w;
            let up = if y == 0 { h - 1 } else { y - 1 } * w;
            let down = if y + 1 == h { 0 } else { y + 1 } * w;

            for x in 0..w {
                let xm = if x == 0 { w - 1 } else { x - 1 };
                let xp = if x + 1 == w { 0 } else { x + 1 };

                let mut weight: u8 = 0;

                if cur[up + xm] == 1 {
                    weight += 1;
                }
                if cur[up + x] == 1 {
                    weight += 2;
                }
                if cur[up + xp] == 1 {
                    weight += 1;
                }
                if cur[row + xm] == 1 {
                    weight += 2;
                }
                if cur[row + xp] == 1 {
                    weight += 2;
                }
                if cur[down + xm] == 1 {
                    weight += 1;
                }
                if cur[down + x] == 1 {
                    weight += 2;
                }
                if cur[down + xp] == 1 {
                    weight += 1;
                }

                let idx = row + x;
                let new_state = match cur[idx] {
                    1 => {
                        if survive[weight as usize] {
                            1
                        } else {
                            2
                        }
                    }
                    0 => {
                        if birth[weight as usize] {
                            1
                        } else {
                            0
                        }
                    }
                    _ => 0,
                };

                next[idx] = new_state;

                if new_state == 1 {
                    alive += 1;
                } else if new_state == 2 {
                    scars += 1;
                }
            }
        }

        std::mem::swap(&mut cur, &mut next);

        writeln!(out, "{} {} {}", g, alive, scars).unwrap();
    }

    let mut line = Vec::with_capacity(w + 1);
    for y in 0..h {
        line.clear();
        for &cell in &cur[y * w..(y + 1) * w] {
            line.push(match cell {
                0 => b'.',
                1 => b'o',
                _ => b'x',
            });
        }
        line.push(b'\n');
        out.write_all(&line).unwrap();
    }

    out.flush().unwrap();
}
