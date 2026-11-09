use std::env;
use std::ffi::OsString;
use std::io::{self, Read, Write};
use std::process;

fn fail() -> ! {
    eprintln!("error");
    process::exit(1);
}

fn parse_codes(s: &str) -> Option<[bool; 13]> {
    let mut arr = [false; 13];
    let mut last: i32 = -1;
    for ch in s.chars() {
        let v: i32 = match ch {
            '0'..='9' => (ch as u32 - '0' as u32) as i32,
            'A' => 10,
            'B' => 11,
            'C' => 12,
            _ => return None,
        };
        if v <= last {
            return None;
        }
        last = v;
        arr[v as usize] = true;
    }
    Some(arr)
}

fn parse_rule(s: &str) -> Option<([bool; 13], [bool; 13])> {
    let parts: Vec<&str> = s.split('/').collect();
    if parts.len() != 2 {
        return None;
    }
    let b = parts[0].strip_prefix('B')?;
    let sp = parts[1].strip_prefix('S')?;
    Some((parse_codes(b)?, parse_codes(sp)?))
}

fn parse_gens(s: &str) -> Option<u32> {
    if s.is_empty() {
        return None;
    }
    let mut v: u32 = 0;
    for b in s.bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (b - b'0') as u32;
        if v > 100000 {
            return None;
        }
    }
    Some(v)
}

fn parse_dim(t: &[u8]) -> Option<usize> {
    if t.is_empty() || t[0] == b'0' {
        return None;
    }
    let mut v: usize = 0;
    for &b in t {
        if !b.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (b - b'0') as usize;
        if v > 4096 {
            return None;
        }
    }
    if v == 0 {
        return None;
    }
    Some(v)
}

fn step(
    cur: &[u8],
    nxt: &mut [u8],
    w: usize,
    h: usize,
    b: &[bool; 13],
    s: &[bool; 13],
) -> (usize, usize) {
    let up: Vec<usize> = (0..h).map(|r| (r + h - 1) % h).collect();
    let down: Vec<usize> = (0..h).map(|r| (r + 1) % h).collect();
    let left: Vec<usize> = (0..w).map(|c| (c + w - 1) % w).collect();
    let right: Vec<usize> = (0..w).map(|c| (c + 1) % w).collect();
    let mut alive = 0usize;
    let mut scars = 0usize;
    for r in 0..h {
        let ru = up[r] * w;
        let rd = down[r] * w;
        let rr = r * w;
        for c in 0..w {
            let cl = left[c];
            let cr = right[c];
            let a = |i: usize| (cur[i] == 1) as usize;
            let orth = a(ru + c) + a(rd + c) + a(rr + cl) + a(rr + cr);
            let diag = a(ru + cl) + a(ru + cr) + a(rd + cl) + a(rd + cr);
            let wgt = 2 * orth + diag;
            let i = rr + c;
            let ns: u8 = match cur[i] {
                1 => {
                    if s[wgt] {
                        1
                    } else {
                        2
                    }
                }
                0 => {
                    if b[wgt] {
                        1
                    } else {
                        0
                    }
                }
                _ => 0,
            };
            nxt[i] = ns;
            if ns == 1 {
                alive += 1;
            } else if ns == 2 {
                scars += 1;
            }
        }
    }
    (alive, scars)
}

fn main() {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    if args.len() != 2 {
        fail();
    }
    let rule_str = match args[0].to_str() {
        Some(s) => s,
        None => fail(),
    };
    let gens_str = match args[1].to_str() {
        Some(s) => s,
        None => fail(),
    };
    let (b_rule, s_rule) = match parse_rule(rule_str) {
        Some(r) => r,
        None => fail(),
    };
    let gens = match parse_gens(gens_str) {
        Some(g) => g,
        None => fail(),
    };

    let mut data: Vec<u8> = Vec::new();
    if io::stdin().read_to_end(&mut data).is_err() {
        fail();
    }
    let len = data.len();

    let nl = match data.iter().position(|&b| b == b'\n') {
        Some(p) => p,
        None => fail(),
    };
    let header = &data[..nl];
    let parts: Vec<&[u8]> = header.split(|&b| b == b' ').collect();
    if parts.len() != 2 {
        fail();
    }
    let w = match parse_dim(parts[0]) {
        Some(v) => v,
        None => fail(),
    };
    let h = match parse_dim(parts[1]) {
        Some(v) => v,
        None => fail(),
    };

    let mut grid = vec![0u8; w * h];
    let mut pos = nl + 1;
    for r in 0..h {
        if pos + w > len {
            fail();
        }
        for c in 0..w {
            grid[r * w + c] = match data[pos + c] {
                b'.' => 0,
                b'o' => 1,
                _ => fail(),
            };
        }
        pos += w;
        if r + 1 < h {
            if pos >= len || data[pos] != b'\n' {
                fail();
            }
            pos += 1;
        } else {
            if pos < len {
                if data[pos] != b'\n' {
                    fail();
                }
                pos += 1;
            }
            if pos != len {
                fail();
            }
        }
    }

    let n = w * h;
    let mut cur = grid;
    let mut nxt = vec![0u8; n];
    let mut out = String::new();

    for g in 1..=gens {
        let (a, s) = step(&cur, &mut nxt, w, h, &b_rule, &s_rule);
        std::mem::swap(&mut cur, &mut nxt);
        out.push_str(&format!("{} {} {}\n", g, a, s));
    }

    for r in 0..h {
        for c in 0..w {
            let ch = match cur[r * w + c] {
                0 => '.',
                1 => 'o',
                _ => 'x',
            };
            out.push(ch);
        }
        out.push('\n');
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
    process::exit(0);
}
