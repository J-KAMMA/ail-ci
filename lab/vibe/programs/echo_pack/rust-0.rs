use std::io::{self, Read, Write};

const HASH_BITS: u32 = 20;
const HASH_SIZE: usize = 1usize << HASH_BITS;

#[inline]
fn hash4_index(d: &[u8], p: usize) -> usize {
    let key = u32::from_le_bytes([d[p], d[p + 1], d[p + 2], d[p + 3]]);
    (key.wrapping_mul(0x9E37_79B1) >> (32 - HASH_BITS)) as usize
}

fn hash_bytes(bytes: &[u8]) -> u32 {
    let mut h: u32 = 0;
    for &b in bytes {
        h = h.wrapping_mul(257).wrapping_add(b as u32 + 1);
    }
    h
}

fn emit_literal(out: &mut Vec<u8>, bytes: &[u8]) {
    out.push((bytes.len() - 1) as u8);
    out.extend_from_slice(bytes);
}

fn pack(data: &[u8]) -> Vec<u8> {
    let n = data.len();
    let mut out = Vec::with_capacity(n / 2 + 16);

    out.extend_from_slice(b"EP1");
    out.extend_from_slice(&(n as u32).to_le_bytes());

    let mut head = vec![u32::MAX; HASH_SIZE];
    let mut prev = vec![u32::MAX; n];
    let mut inserted = 0usize;

    let mut i = 0usize;
    let mut lit_start = 0usize;
    let mut lit_len = 0usize;

    while i < n {
        while inserted < i {
            if inserted + 4 <= n {
                let idx = hash4_index(data, inserted);
                prev[inserted] = head[idx];
                head[idx] = inserted as u32;
            }
            inserted += 1;
        }

        let mut found = false;
        let mut best_len = 0usize;
        let mut best_p = 0usize;

        if i + 4 <= n {
            let idx = hash4_index(data, i);
            let min_p = i.saturating_sub(65535);
            let mut p = head[idx];
            let mut count = 0usize;

            while p != u32::MAX {
                let pu = p as usize;
                if pu < min_p {
                    break;
                }

                if data[pu] == data[i]
                    && data[pu + 1] == data[i + 1]
                    && data[pu + 2] == data[i + 2]
                    && data[pu + 3] == data[i + 3]
                {
                    let max_m = std::cmp::min(131, n - i);
                    let mut m = 4usize;
                    while m < max_m && data[pu + m] == data[i + m] {
                        m += 1;
                    }

                    if m > best_len {
                        best_len = m;
                        best_p = pu;
                        found = true;
                    }

                    count += 1;
                    if count == 8 {
                        break;
                    }
                }

                p = prev[pu];
            }
        }

        if found {
            if lit_len > 0 {
                emit_literal(&mut out, &data[lit_start..lit_start + lit_len]);
                lit_len = 0;
            }

            let dist = i - best_p;
            out.push(0x80 + (best_len - 4) as u8);
            out.push((dist >> 8) as u8);
            out.push((dist & 0xFF) as u8);
            i += best_len;
        } else {
            if lit_len == 0 {
                lit_start = i;
            }
            lit_len += 1;

            if lit_len == 128 {
                emit_literal(&mut out, &data[lit_start..lit_start + lit_len]);
                lit_len = 0;
            }

            i += 1;
        }
    }

    if lit_len > 0 {
        emit_literal(&mut out, &data[lit_start..lit_start + lit_len]);
    }

    out.extend_from_slice(&hash_bytes(data).to_le_bytes());
    out
}

fn unpack(data: &[u8]) -> Option<Vec<u8>> {
    if data.len() < 3 || &data[0..3] != b"EP1" {
        return None;
    }
    if data.len() < 7 {
        return None;
    }

    let n = u32::from_le_bytes([data[3], data[4], data[5], data[6]]) as usize;
    let mut pos = 7usize;
    let mut out = Vec::new();

    while out.len() < n {
        if pos >= data.len() {
            return None;
        }

        let c = data[pos];
        pos += 1;

        if c < 0x80 {
            let k = c as usize + 1;
            if out.len() + k > n {
                return None;
            }
            if pos + k > data.len() {
                return None;
            }
            out.extend_from_slice(&data[pos..pos + k]);
            pos += k;
        } else {
            let len = (c - 0x80) as usize + 4;
            if pos + 2 > data.len() {
                return None;
            }

            let dist = ((data[pos] as usize) << 8) | (data[pos + 1] as usize);
            pos += 2;

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

    if pos + 4 > data.len() {
        return None;
    }
    if pos + 4 != data.len() {
        return None;
    }

    let expected = u32::from_le_bytes([
        data[pos],
        data[pos + 1],
        data[pos + 2],
        data[pos + 3],
    ]);

    if hash_bytes(&out) != expected {
        return None;
    }

    Some(out)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.len() != 2 {
        std::process::exit(1);
    }

    match args[1].as_str() {
        "pack" => {
            let mut input = Vec::new();
            let _ = io::stdin().read_to_end(&mut input);
            let out = pack(&input);

            let mut stdout = io::stdout().lock();
            let _ = stdout.write_all(&out);
            let _ = stdout.flush();
        }
        "unpack" => {
            let mut input = Vec::new();
            if io::stdin().read_to_end(&mut input).is_err() {
                std::process::exit(2);
            }

            match unpack(&input) {
                Some(out) => {
                    let mut stdout = io::stdout().lock();
                    if stdout.write_all(&out).is_err() {
                        std::process::exit(2);
                    }
                    let _ = stdout.flush();
                }
                None => std::process::exit(2),
            }
        }
        _ => std::process::exit(1),
    }
}
