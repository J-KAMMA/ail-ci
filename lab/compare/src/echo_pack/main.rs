use std::collections::HashMap;
use std::io::{Read, Write};

fn hash(d: &[u8]) -> u32 {
    let mut h: u32 = 0;
    for &b in d {
        h = h.wrapping_mul(257).wrapping_add(b as u32 + 1);
    }
    h
}

fn flush(out: &mut Vec<u8>, l: &mut Vec<u8>) {
    if !l.is_empty() {
        out.push((l.len() - 1) as u8);
        out.extend_from_slice(l);
        l.clear();
    }
}

fn pack(d: &[u8]) -> Vec<u8> {
    let n = d.len();
    let mut out = vec![b'E', b'P', b'1'];
    out.extend_from_slice(&(n as u32).to_le_bytes());
    let mut head: HashMap<u32, usize> = HashMap::new();
    let mut prev: Vec<usize> = vec![usize::MAX; n];
    let key = |p: usize| u32::from_le_bytes([d[p], d[p + 1], d[p + 2], d[p + 3]]);
    let mut inserted = 0usize; // positions < inserted are inserted
    let mut l: Vec<u8> = Vec::new();
    let mut i = 0;
    while i < n {
        let mut best_m = 0usize;
        let mut best_p = 0usize;
        if i + 4 <= n {
            while inserted < i {
                if inserted + 4 <= n {
                    let k = key(inserted);
                    if let Some(&h) = head.get(&k) {
                        prev[inserted] = h;
                    }
                    head.insert(k, inserted);
                }
                inserted += 1;
            }
            let mut cur = head.get(&key(i)).copied().unwrap_or(usize::MAX);
            let mut cnt = 0;
            let maxm = 131.min(n - i);
            while cur != usize::MAX && cnt < 8 && i - cur <= 65535 {
                let mut m = 0;
                while m < maxm && d[cur + m] == d[i + m] {
                    m += 1;
                }
                if m > best_m {
                    best_m = m;
                    best_p = cur;
                }
                cnt += 1;
                cur = prev[cur];
            }
        }
        if best_m >= 4 {
            flush(&mut out, &mut l);
            out.push(0x80 + (best_m - 4) as u8);
            out.extend_from_slice(&((i - best_p) as u16).to_be_bytes());
            i += best_m;
        } else {
            l.push(d[i]);
            if l.len() == 128 {
                flush(&mut out, &mut l);
            }
            i += 1;
        }
    }
    flush(&mut out, &mut l);
    out.extend_from_slice(&hash(d).to_le_bytes());
    out
}

fn unpack(s: &[u8]) -> Option<Vec<u8>> {
    if s.len() < 7 || &s[0..3] != b"EP1" {
        return None;
    }
    let n = u32::from_le_bytes([s[3], s[4], s[5], s[6]]) as usize;
    let mut pos = 7;
    let mut out: Vec<u8> = Vec::new();
    while out.len() < n {
        let c = *s.get(pos)? as usize;
        pos += 1;
        if c < 0x80 {
            let k = c + 1;
            if pos + k > s.len() || out.len() + k > n {
                return None;
            }
            out.extend_from_slice(&s[pos..pos + k]);
            pos += k;
        } else {
            if pos + 2 > s.len() {
                return None;
            }
            let dist = ((s[pos] as usize) << 8) | s[pos + 1] as usize;
            pos += 2;
            let len = c - 0x80 + 4;
            if dist == 0 || dist > out.len() || out.len() + len > n {
                return None;
            }
            for _ in 0..len {
                let b = out[out.len() - dist];
                out.push(b);
            }
        }
    }
    if s.len() != pos + 4 {
        return None;
    }
    let h = u32::from_le_bytes([s[pos], s[pos + 1], s[pos + 2], s[pos + 3]]);
    if h != hash(&out) {
        return None;
    }
    Some(out)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 || (args[1] != "pack" && args[1] != "unpack") {
        std::process::exit(1);
    }
    let mut input = Vec::new();
    std::io::stdin().read_to_end(&mut input).unwrap();
    let res = if args[1] == "pack" {
        Some(pack(&input))
    } else {
        unpack(&input)
    };
    match res {
        Some(o) => {
            let so = std::io::stdout();
            let mut so = so.lock();
            so.write_all(&o).unwrap();
            so.flush().unwrap();
        }
        None => std::process::exit(2),
    }
}
