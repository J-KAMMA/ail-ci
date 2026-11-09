use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::process::exit;

fn hash(data: &[u8]) -> u32 {
    let mut h: u32 = 0;
    for &b in data {
        h = h.wrapping_mul(257).wrapping_add(b as u32 + 1);
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
    out.extend_from_slice(&[0x45, 0x50, 0x31]);
    out.extend_from_slice(&(n as u32).to_le_bytes());

    let mut lit: Vec<u8> = Vec::new();
    let mut map: HashMap<u32, Vec<usize>> = HashMap::new();
    let mut next_ins = 0usize;
    let mut i = 0usize;

    while i < n {
        // Insert all positions j < i that have 4 bytes available.
        while next_ins < i && next_ins + 4 <= n {
            let key = u32::from_le_bytes([
                d[next_ins],
                d[next_ins + 1],
                d[next_ins + 2],
                d[next_ins + 3],
            ]);
            map.entry(key).or_insert_with(Vec::new).push(next_ins);
            next_ins += 1;
        }

        let mut found = false;
        let mut best_m = 0usize;
        let mut best_p = 0usize;

        if i + 4 <= n {
            let key = u32::from_le_bytes([d[i], d[i + 1], d[i + 2], d[i + 3]]);
            if let Some(list) = map.get(&key) {
                let maxm = std::cmp::min(131, n - i);
                let mut cnt = 0usize;
                for &p in list.iter().rev() {
                    if i - p > 65535 {
                        break;
                    }
                    cnt += 1;
                    let mut m = 0usize;
                    while m < maxm && d[p + m] == d[i + m] {
                        m += 1;
                    }
                    if !found || m > best_m {
                        found = true;
                        best_m = m;
                        best_p = p;
                    }
                    if cnt == 8 {
                        break;
                    }
                }
            }
        }

        if found {
            if !lit.is_empty() {
                emit_lit(&mut out, &mut lit);
            }
            out.push(0x80 + (best_m - 4) as u8);
            let dist = (i - best_p) as u16;
            out.extend_from_slice(&dist.to_be_bytes());
            i += best_m;
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

    let h = hash(d);
    out.extend_from_slice(&h.to_le_bytes());
    out
}

fn unpack(s: &[u8]) -> Option<Vec<u8>> {
    if s.len() < 3 || s[0..3] != [0x45, 0x50, 0x31] {
        return None;
    }
    if s.len() < 7 {
        return None;
    }
    let n = u32::from_le_bytes([s[3], s[4], s[5], s[6]]) as usize;
    let mut pos = 7usize;
    let mut out: Vec<u8> = Vec::with_capacity(n);

    while out.len() < n {
        if pos >= s.len() {
            return None;
        }
        let c = s[pos];
        pos += 1;
        if c < 0x80 {
            let k = c as usize + 1;
            if pos + k > s.len() {
                return None;
            }
            if out.len() + k > n {
                return None;
            }
            out.extend_from_slice(&s[pos..pos + k]);
            pos += k;
        } else {
            if pos + 2 > s.len() {
                return None;
            }
            let dist = ((s[pos] as usize) << 8) | (s[pos + 1] as usize);
            pos += 2;
            let len = (c - 0x80) as usize + 4;
            if dist == 0 || dist > out.len() {
                return None;
            }
            if out.len() + len > n {
                return None;
            }
            for _ in 0..len {
                let b = out[out.len() - dist];
                out.push(b);
            }
        }
    }

    if pos + 4 > s.len() {
        return None;
    }
    let h = u32::from_le_bytes([s[pos], s[pos + 1], s[pos + 2], s[pos + 3]]);
    pos += 4;
    if pos != s.len() {
        return None;
    }
    if hash(&out) != h {
        return None;
    }
    Some(out)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        exit(1);
    }

    match args[1].as_str() {
        "pack" => {
            let mut input = Vec::new();
            if io::stdin().read_to_end(&mut input).is_err() {
                exit(1);
            }
            let out = pack(&input);
            let stdout = io::stdout();
            let mut lock = stdout.lock();
            let _ = lock.write_all(&out);
            let _ = lock.flush();
            exit(0);
        }
        "unpack" => {
            let mut input = Vec::new();
            if io::stdin().read_to_end(&mut input).is_err() {
                exit(2);
            }
            match unpack(&input) {
                Some(out) => {
                    let stdout = io::stdout();
                    let mut lock = stdout.lock();
                    let _ = lock.write_all(&out);
                    let _ = lock.flush();
                    exit(0);
                }
                None => exit(2),
            }
        }
        _ => exit(1),
    }
}
