use std::io::{Read, Write};

const OPEN: u8 = b'.';
const WALL: u8 = b'#';

fn next_line<'a>(data: &'a [u8], pos: &mut usize) -> Option<&'a [u8]> {
    if *pos >= data.len() {
        return None;
    }
    let start = *pos;
    let mut p = start;
    while p < data.len() && data[p] != b'\n' {
        p += 1;
    }
    let line = &data[start..p];
    if p < data.len() {
        p += 1;
    }
    *pos = p;
    Some(line)
}

fn parse_uint(s: &[u8], idx: &mut usize) -> Option<i64> {
    let n = s.len();
    let mut i = *idx;
    if i >= n {
        return None;
    }
    if s[i] < b'0' || s[i] > b'9' {
        return None;
    }
    let mut v: i64 = 0;
    while i < n {
        let c = s[i];
        if c < b'0' || c > b'9' {
            break;
        }
        v = v * 10 + (c - b'0') as i64;
        if v > 100000000 {
            return None;
        }
        i += 1;
    }
    *idx = i;
    Some(v)
}

fn main() {
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let mut pos = 0usize;

    let header = match next_line(&data, &mut pos) {
        Some(l) => l,
        None => std::process::exit(2),
    };
    let mut idx = 0usize;
    let h = match parse_uint(header, &mut idx) { Some(v) => v, None => std::process::exit(2) };
    if idx >= header.len() || header[idx] != b' ' { std::process::exit(2); }
    idx += 1;
    let w = match parse_uint(header, &mut idx) { Some(v) => v, None => std::process::exit(2) };
    if idx >= header.len() || header[idx] != b' ' { std::process::exit(2); }
    idx += 1;
    let q = match parse_uint(header, &mut idx) { Some(v) => v, None => std::process::exit(2) };
    if idx != header.len() { std::process::exit(2); }
    if h < 1 || h > 2000 || w < 1 || w > 2000 || q < 0 || q > 20 { std::process::exit(2); }
    let h = h as usize;
    let w = w as usize;
    let q = q as usize;
    let n = h * w;

    let mut grid = vec![0u8; n];
    for r in 0..h {
        let line = match next_line(&data, &mut pos) { Some(l) => l, None => std::process::exit(2) };
        if line.len() != w { std::process::exit(2); }
        for j in 0..w {
            if line[j] != OPEN && line[j] != WALL { std::process::exit(2); }
            grid[r * w + j] = line[j];
        }
    }

    let mut qs = Vec::with_capacity(q);
    let mut qt = Vec::with_capacity(q);
    for _ in 0..q {
        let line = match next_line(&data, &mut pos) { Some(l) => l, None => std::process::exit(2) };
        let mut i = 0usize;
        let r1 = match parse_uint(line, &mut i) { Some(v) => v, None => std::process::exit(2) };
        if i >= line.len() || line[i] != b' ' { std::process::exit(2); }
        i += 1;
        let c1 = match parse_uint(line, &mut i) { Some(v) => v, None => std::process::exit(2) };
        if i >= line.len() || line[i] != b' ' { std::process::exit(2); }
        i += 1;
        let r2 = match parse_uint(line, &mut i) { Some(v) => v, None => std::process::exit(2) };
        if i >= line.len() || line[i] != b' ' { std::process::exit(2); }
        i += 1;
        let c2 = match parse_uint(line, &mut i) { Some(v) => v, None => std::process::exit(2) };
        if i != line.len() { std::process::exit(2); }
        if r1 < 0 || r1 >= h as i64 || c1 < 0 || c1 >= w as i64
            || r2 < 0 || r2 >= h as i64 || c2 < 0 || c2 >= w as i64
        {
            std::process::exit(2);
        }
        qs.push((r1 as usize) * w + (c1 as usize));
        qt.push((r2 as usize) * w + (c2 as usize));
    }
    if next_line(&data, &mut pos).is_some() {
        std::process::exit(2);
    }

    let stdout = std::io::stdout();
    let mut out = std::io::BufWriter::new(stdout.lock());
    let mut dist = vec![-1i32; n];
    let mut queue = vec![0i32; n];
    let mut total: i64 = 0;
    for k in 0..q {
        let s = qs[k];
        let t = qt[k];
        if grid[s] == WALL || grid[t] == WALL {
            writeln!(out, "dist -1 seen 0").unwrap();
            continue;
        }
        for x in dist.iter_mut() {
            *x = -1;
        }
        let mut head = 0usize;
        let mut tail = 1usize;
        queue[0] = s as i32;
        dist[s] = 0;
        let mut seen: i64 = 0;
        let mut d: i32 = -1;
        while head < tail {
            let v = queue[head] as usize;
            head += 1;
            seen += 1;
            if v == t {
                d = dist[v];
                break;
            }
            let nd = dist[v] + 1;
            let rr = v / w;
            let cc = v - rr * w;
            if rr > 0 {
                let u = v - w;
                if grid[u] == OPEN && dist[u] == -1 {
                    dist[u] = nd;
                    queue[tail] = u as i32;
                    tail += 1;
                }
            }
            if rr + 1 < h {
                let u = v + w;
                if grid[u] == OPEN && dist[u] == -1 {
                    dist[u] = nd;
                    queue[tail] = u as i32;
                    tail += 1;
                }
            }
            if cc > 0 {
                let u = v - 1;
                if grid[u] == OPEN && dist[u] == -1 {
                    dist[u] = nd;
                    queue[tail] = u as i32;
                    tail += 1;
                }
            }
            if cc + 1 < w {
                let u = v + 1;
                if grid[u] == OPEN && dist[u] == -1 {
                    dist[u] = nd;
                    queue[tail] = u as i32;
                    tail += 1;
                }
            }
        }
        writeln!(out, "dist {} seen {}", d, seen).unwrap();
        if d != -1 {
            total += d as i64;
        }
    }
    writeln!(out, "total {}", total).unwrap();
}
