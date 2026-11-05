use std::collections::{HashMap, HashSet};
use std::io::{Read, Write};

struct Parsed {
    ip: u32,
    hour: usize,
    status: u32,
    nbytes: i64,
    ps: usize,
    pe: usize,
}

fn two(s: &[u8], i: usize, lo: u32, hi: u32) -> Option<usize> {
    if i + 2 > s.len() {
        return None;
    }
    let a = s[i].wrapping_sub(b'0');
    let b = s[i + 1].wrapping_sub(b'0');
    if a > 9 || b > 9 {
        return None;
    }
    let v = a as u32 * 10 + b as u32;
    if v < lo || v > hi {
        return None;
    }
    Some(v as usize)
}

fn month_ok(s: &[u8], i: usize) -> bool {
    if i + 3 > s.len() {
        return false;
    }
    let v = ((s[i] as u32) << 16) | ((s[i + 1] as u32) << 8) | (s[i + 2] as u32);
    matches!(v, 0x4A616E | 0x466562 | 0x4D6172 | 0x417072 | 0x4D6179 | 0x4A756E
        | 0x4A756C | 0x417567 | 0x536570 | 0x4F6374 | 0x4E6F76 | 0x446563)
}

fn method_ok(s: &[u8], a: usize, b: usize) -> bool {
    let n = b - a;
    if n == 3 {
        if s[a] == b'G' && s[a + 1] == b'E' && s[a + 2] == b'T' {
            return true;
        }
        return s[a] == b'P' && s[a + 1] == b'U' && s[a + 2] == b'T';
    }
    if n == 4 {
        return s[a] == b'P' && s[a + 1] == b'O' && s[a + 2] == b'S' && s[a + 3] == b'T';
    }
    if n == 6 {
        return s[a] == b'D' && s[a + 1] == b'E' && s[a + 2] == b'L'
            && s[a + 3] == b'E' && s[a + 4] == b'T' && s[a + 5] == b'E';
    }
    false
}

fn path_ok(s: &[u8], a: usize, b: usize) -> bool {
    let n = b - a;
    if n < 1 || n > 64 || s[a] != b'/' {
        return false;
    }
    for i in a..b {
        let c = s[i];
        if (c >= b'A' && c <= b'Z') || (c >= b'a' && c <= b'z') || (c >= b'0' && c <= b'9') {
            continue;
        }
        if c == b'/' || c == b'.' || c == b'_' || c == b'-' {
            continue;
        }
        return false;
    }
    true
}

fn parse_line(l: &[u8]) -> Option<Parsed> {
    let n = l.len();
    let mut i = 0usize;
    let mut ip: u32 = 0;
    for k in 0..4 {
        if k > 0 {
            if i >= n || l[i] != b'.' {
                return None;
            }
            i += 1;
        }
        let start = i;
        let mut v: u32 = 0;
        while i < n && i - start < 3 && l[i] >= b'0' && l[i] <= b'9' {
            v = v * 10 + (l[i] - b'0') as u32;
            i += 1;
        }
        if i == start || v > 255 {
            return None;
        }
        ip = (ip << 8) | v;
    }
    if i + 6 > n {
        return None;
    }
    if !(l[i] == b' ' && l[i + 1] == b'-' && l[i + 2] == b' ' && l[i + 3] == b'-'
        && l[i + 4] == b' ' && l[i + 5] == b'[')
    {
        return None;
    }
    i += 6;
    if two(l, i, 1, 31).is_none() {
        return None;
    }
    i += 2;
    if i >= n || l[i] != b'/' {
        return None;
    }
    i += 1;
    if !month_ok(l, i) {
        return None;
    }
    i += 3;
    if i >= n || l[i] != b'/' {
        return None;
    }
    i += 1;
    if i + 4 > n {
        return None;
    }
    for k in 0..4 {
        if l[i + k] < b'0' || l[i + k] > b'9' {
            return None;
        }
    }
    i += 4;
    if i >= n || l[i] != b':' {
        return None;
    }
    i += 1;
    let hh = match two(l, i, 0, 23) {
        Some(v) => v,
        None => return None,
    };
    i += 2;
    if i >= n || l[i] != b':' {
        return None;
    }
    i += 1;
    if two(l, i, 0, 59).is_none() {
        return None;
    }
    i += 2;
    if i >= n || l[i] != b':' {
        return None;
    }
    i += 1;
    if two(l, i, 0, 59).is_none() {
        return None;
    }
    i += 2;
    if i + 7 > n {
        return None;
    }
    if !(l[i] == b' ' && l[i + 1] == b'+' && l[i + 2] == b'0' && l[i + 3] == b'0'
        && l[i + 4] == b'0' && l[i + 5] == b'0' && l[i + 6] == b']')
    {
        return None;
    }
    i += 7;
    if i >= n || l[i] != b' ' {
        return None;
    }
    i += 1;
    if i >= n || l[i] != b'"' {
        return None;
    }
    i += 1;
    let ms = i;
    while i < n && l[i] != b' ' {
        i += 1;
    }
    if i >= n || !method_ok(l, ms, i) {
        return None;
    }
    i += 1;
    let ps = i;
    while i < n && l[i] != b' ' {
        i += 1;
    }
    if i >= n || !path_ok(l, ps, i) {
        return None;
    }
    let pe = i;
    i += 1;
    if i + 8 > n {
        return None;
    }
    if !(l[i] == b'H' && l[i + 1] == b'T' && l[i + 2] == b'T' && l[i + 3] == b'P'
        && l[i + 4] == b'/' && l[i + 5] == b'1' && l[i + 6] == b'.' && l[i + 7] == b'1')
    {
        return None;
    }
    i += 8;
    if i >= n || l[i] != b'"' {
        return None;
    }
    i += 1;
    if i >= n || l[i] != b' ' {
        return None;
    }
    i += 1;
    if i + 3 > n {
        return None;
    }
    let s0 = l[i].wrapping_sub(b'0');
    let s1 = l[i + 1].wrapping_sub(b'0');
    let s2 = l[i + 2].wrapping_sub(b'0');
    if s0 > 9 || s1 > 9 || s2 > 9 {
        return None;
    }
    let status = s0 as u32 * 100 + s1 as u32 * 10 + s2 as u32;
    if status < 100 || status > 599 {
        return None;
    }
    i += 3;
    if i >= n || l[i] != b' ' {
        return None;
    }
    i += 1;
    if i >= n {
        return None;
    }
    let mut nb: i64 = 0;
    if l[i] == b'-' {
        if i + 1 != n {
            return None;
        }
    } else {
        if l[i] < b'0' || l[i] > b'9' {
            return None;
        }
        while i < n {
            let c = l[i];
            if c < b'0' || c > b'9' {
                return None;
            }
            nb = nb * 10 + (c - b'0') as i64;
            if nb > 1000000000000 {
                return None;
            }
            i += 1;
        }
    }
    Some(Parsed { ip, hour: hh, status, nbytes: nb, ps, pe })
}

fn main() {
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let stdout = std::io::stdout();
    let mut w = std::io::BufWriter::new(stdout.lock());
    if data.is_empty() {
        w.write_all(b"lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n").unwrap();
        return;
    }
    let mut paths: HashMap<Vec<u8>, (i64, i64)> = HashMap::new();
    let mut ips: HashSet<u32> = HashSet::new();
    let mut scount = [0i64; 6];
    let mut hcount = [0i64; 24];
    let mut hbytes = [0i64; 24];
    let mut good: i64 = 0;
    let mut bad: i64 = 0;
    let mut total: i64 = 0;
    let mut pos = 0usize;
    while pos < data.len() {
        let end = match data[pos..].iter().position(|&b| b == b'\n') {
            Some(k) => pos + k,
            None => data.len(),
        };
        let line = &data[pos..end];
        match parse_line(line) {
            Some(p) => {
                good += 1;
                total += p.nbytes;
                let cls = (p.status / 100) as usize;
                if cls >= 2 && cls <= 5 {
                    scount[cls] += 1;
                }
                hcount[p.hour] += 1;
                hbytes[p.hour] += p.nbytes;
                let key = &line[p.ps..p.pe];
                match paths.get_mut(key) {
                    Some(e) => {
                        e.0 += 1;
                        e.1 += p.nbytes;
                    }
                    None => {
                        paths.insert(key.to_vec(), (1, p.nbytes));
                    }
                }
                ips.insert(p.ip);
            }
            None => bad += 1,
        }
        pos = if end < data.len() { end + 1 } else { data.len() };
    }
    writeln!(w, "lines {} bad {}", good, bad).unwrap();
    writeln!(w, "status 2xx {} 3xx {} 4xx {} 5xx {}",
             scount[2], scount[3], scount[4], scount[5]).unwrap();
    writeln!(w, "bytes {}", total).unwrap();
    for h in 0..24 {
        if hcount[h] > 0 {
            writeln!(w, "hour {:02} {} {}", h, hcount[h], hbytes[h]).unwrap();
        }
    }
    let mut pv: Vec<(&Vec<u8>, &(i64, i64))> = paths.iter().collect();
    pv.sort_by(|a, b| b.1.0.cmp(&a.1.0).then(a.0.cmp(b.0)));
    for &(p, e) in pv.iter().take(10) {
        writeln!(w, "path {} {} {}", std::str::from_utf8(p).unwrap(), e.0, e.1).unwrap();
    }
    writeln!(w, "ips {}", ips.len()).unwrap();
}
