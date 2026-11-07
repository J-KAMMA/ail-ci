use std::collections::HashMap;
use std::io::{self, Read, Write};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        std::process::exit(1);
    }
    match args[1].as_str() {
        "pack" => pack(),
        "unpack" => match unpack() {
            Ok(out) => {
                let stdout = io::stdout();
                let mut lock = stdout.lock();
                if lock.write_all(&out).is_err() {
                    std::process::exit(2);
                }
            }
            Err(()) => std::process::exit(2),
        },
        _ => std::process::exit(1),
    }
}

fn emit_lit(out: &mut Vec<u8>, lit: &[u8]) {
    out.push((lit.len() - 1) as u8);
    out.extend_from_slice(lit);
}

fn insert_key(map: &mut HashMap<u32, Vec<u32>>, input: &[u8], p: usize, n: usize) {
    if p + 4 <= n {
        let key = u32::from_le_bytes([input[p], input[p + 1], input[p + 2], input[p + 3]]);
        let v = map.entry(key).or_insert_with(Vec::new);
        if v.len() == 8 {
            v.remove(0);
        }
        v.push(p as u32);
    }
}

fn pack() {
    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        std::process::exit(1);
    }
    let n = input.len();

    let mut h: u32 = 0;
    for &b in &input {
        h = h.wrapping_mul(257).wrapping_add(b as u32 + 1);
    }

    let mut out: Vec<u8> = Vec::with_capacity(n / 2 + 16);
    out.extend_from_slice(b"EP1");
    out.extend_from_slice(&(n as u32).to_le_bytes());

    let mut map: HashMap<u32, Vec<u32>> = HashMap::new();
    let mut next_insert: usize = 0;
    let mut lit: Vec<u8> = Vec::new();
    let mut i: usize = 0;

    while i < n {
        while next_insert < i {
            insert_key(&mut map, &input, next_insert, n);
            next_insert += 1;
        }

        let mut best_m = 0usize;
        let mut best_p = 0usize;

        if i + 4 <= n {
            let key = u32::from_le_bytes([input[i], input[i + 1], input[i + 2], input[i + 3]]);
            if let Some(v) = map.get(&key) {
                let max_len = std::cmp::min(131, n - i);
                for &pp in v.iter() {
                    let p = pp as usize;
                    let dist = i - p;
                    if dist > 65535 {
                        continue;
                    }
                    let mut m = 0usize;
                    while m < max_len && input[p + m] == input[i + m] {
                        m += 1;
                    }
                    if m > best_m || (m == best_m && p > best_p) {
                        best_m = m;
                        best_p = p;
                    }
                }
            }
        }

        if best_m >= 4 {
            if !lit.is_empty() {
                emit_lit(&mut out, &lit);
                lit.clear();
            }
            out.push(0x80u8 | ((best_m - 4) as u8));
            let dist = (i - best_p) as u16;
            out.extend_from_slice(&dist.to_be_bytes());
            i += best_m;
        } else {
            lit.push(input[i]);
            if lit.len() == 128 {
                emit_lit(&mut out, &lit);
                lit.clear();
            }
            i += 1;
        }
    }

    if !lit.is_empty() {
        emit_lit(&mut out, &lit);
    }

    out.extend_from_slice(&h.to_le_bytes());

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
}

fn unpack() -> Result<Vec<u8>, ()> {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).map_err(|_| ())?;

    if data.len() < 3 || &data[0..3] != b"EP1" {
        return Err(());
    }
    if data.len() < 7 {
        return Err(());
    }

    let n = u32::from_le_bytes([data[3], data[4], data[5], data[6]]) as usize;
    let mut out: Vec<u8> = Vec::new();
    let mut pos: usize = 7;

    while out.len() < n {
        if pos >= data.len() {
            return Err(());
        }
        let c = data[pos];
        pos += 1;

        if c < 0x80 {
            let k = c as usize + 1;
            if data.len() - pos < k {
                return Err(());
            }
            if out.len() + k > n {
                return Err(());
            }
            out.extend_from_slice(&data[pos..pos + k]);
            pos += k;
        } else {
            let len = (c - 0x80) as usize + 4;
            if data.len() - pos < 2 {
                return Err(());
            }
            let dist = u16::from_be_bytes([data[pos], data[pos + 1]]) as usize;
            pos += 2;
            if dist == 0 || dist > out.len() {
                return Err(());
            }
            if out.len() + len > n {
                return Err(());
            }
            for _ in 0..len {
                let b = out[out.len() - dist];
                out.push(b);
            }
        }
    }

    if data.len() < pos + 4 {
        return Err(());
    }
    if data.len() != pos + 4 {
        return Err(());
    }

    let stored = u32::from_le_bytes([
        data[pos],
        data[pos + 1],
        data[pos + 2],
        data[pos + 3],
    ]);

    let mut h: u32 = 0;
    for &b in &out {
        h = h.wrapping_mul(257).wrapping_add(b as u32 + 1);
    }

    if h != stored {
        return Err(());
    }

    Ok(out)
}
