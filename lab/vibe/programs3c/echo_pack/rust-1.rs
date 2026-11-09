use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::process;

fn hash_of(data: &[u8]) -> u32 {
    let mut h: u32 = 0;
    for &b in data {
        h = h.wrapping_mul(257).wrapping_add(b as u32).wrapping_add(1);
    }
    h
}

fn emit_lit(out: &mut Vec<u8>, lit: &mut Vec<u8>) {
    out.push((lit.len() - 1) as u8);
    out.extend_from_slice(lit);
    lit.clear();
}

fn pack(d: &[u8]) -> Vec<u8> {
    let n = d.len();
    let mut out: Vec<u8> = Vec::new();
    out.extend_from_slice(b"EP1");
    out.extend_from_slice(&(n as u32).to_le_bytes());

    let mut map: HashMap<[u8; 4], Vec<usize>> = HashMap::new();
    let mut next_ins: usize = 0;
    let mut lit: Vec<u8> = Vec::new();
    let mut i: usize = 0;

    while i < n {
        // Make every position < i (with 4 bytes available) a candidate.
        while next_ins < i {
            if next_ins + 4 <= n {
                let key = [
                    d[next_ins],
                    d[next_ins + 1],
                    d[next_ins + 2],
                    d[next_ins + 3],
                ];
                map.entry(key).or_insert_with(Vec::new).push(next_ins);
            }
            next_ins += 1;
        }

        let mut best: Option<(usize, usize)> = None; // (match length, p)
        if i + 4 <= n {
            let key = [d[i], d[i + 1], d[i + 2], d[i + 3]];
            if let Some(list) = map.get(&key) {
                let maxm = std::cmp::min(131, n - i);
                let mut count = 0usize;
                for &p in list.iter().rev() {
                    if i - p > 65535 {
                        break;
                    }
                    count += 1;
                    let mut m = 0usize;
                    while m < maxm && d[p + m] == d[i + m] {
                        m += 1;
                    }
                    match best {
                        None => best = Some((m, p)),
                        Some((bm, _)) => {
                            if m > bm {
                                best = Some((m, p));
                            }
                        }
                    }
                    if count == 8 {
                        break;
                    }
                }
            }
        }

        if let Some((m, p)) = best {
            if !lit.is_empty() {
                emit_lit(&mut out, &mut lit);
            }
            out.push(0x80 + (m - 4) as u8);
            let dist = i - p;
            out.push((dist >> 8) as u8);
            out.push(dist as u8);
            i += m;
        } else {
            lit.push(d[i]);
            if lit.len() == 128 {
                emit_lit(&mut out, &mut lit);
            }
            i += 1;
        }
    }

    if !lit.is_empty() {
        emit_lit(&mut out, &mut lit);
    }

    out.extend_from_slice(&hash_of(d).to_le_bytes());
    out
}

fn unpack(b: &[u8]) -> Option<Vec<u8>> {
    if b.len() < 3 || &b[0..3] != b"EP1" {
        return None;
    }
    if b.len() < 7 {
        return None;
    }
    let n = u32::from_le_bytes([b[3], b[4], b[5], b[6]]) as usize;
    let mut pos: usize = 7;
    let mut out: Vec<u8> = Vec::new();

    while out.len() < n {
        if pos >= b.len() {
            return None;
        }
        let c = b[pos];
        pos += 1;
        if c < 0x80 {
            let cnt = c as usize + 1;
            if pos + cnt > b.len() {
                return None;
            }
            if out.len() + cnt > n {
                return None;
            }
            out.extend_from_slice(&b[pos..pos + cnt]);
            pos += cnt;
        } else {
            if pos + 2 > b.len() {
                return None;
            }
            let dist = ((b[pos] as usize) << 8) | (b[pos + 1] as usize);
            pos += 2;
            let len = (c - 0x80) as usize + 4;
            if dist == 0 || dist > out.len() {
                return None;
            }
            if out.len() + len > n {
                return None;
            }
            for _ in 0..len {
                let byte = out[out.len() - dist];
                out.push(byte);
            }
        }
    }

    if b.len() - pos != 4 {
        return None;
    }
    let h = u32::from_le_bytes([b[pos], b[pos + 1], b[pos + 2], b[pos + 3]]);
    if h != hash_of(&out) {
        return None;
    }
    Some(out)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let mode = args[1].as_str();
    if mode != "pack" && mode != "unpack" {
        process::exit(1);
    }

    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        process::exit(2);
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();

    if mode == "pack" {
        let out = pack(&input);
        if lock.write_all(&out).is_err() || lock.flush().is_err() {
            process::exit(1);
        }
    } else {
        match unpack(&input) {
            Some(out) => {
                if lock.write_all(&out).is_err() || lock.flush().is_err() {
                    process::exit(2);
                }
            }
            None => {
                process::exit(2);
            }
        }
    }
}
