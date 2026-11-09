use std::io::{self, Read, Write};

fn fail() -> ! {
    print!("error\n");
    std::process::exit(2);
}

fn parse_dim(s: &str) -> Option<usize> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut v: u64 = 0;
    for b in s.bytes() {
        v = v * 10 + (b - b'0') as u64;
        if v > 10000 {
            return None;
        }
    }
    Some(v as usize)
}

fn parse_val(s: &str) -> Option<i64> {
    if s.is_empty() || s.starts_with('+') {
        return None;
    }
    s.parse::<i64>().ok()
}

fn main() {
    let mut buf = Vec::new();
    if io::stdin().read_to_end(&mut buf).is_err() {
        fail();
    }
    let text = match String::from_utf8(buf) {
        Ok(t) => t,
        Err(_) => fail(),
    };

    let mut lines: Vec<&str> = text
        .split('\n')
        .map(|l| l.strip_suffix('\r').unwrap_or(l))
        .collect();
    if lines.last() == Some(&"") {
        lines.pop();
    }
    if lines.is_empty() {
        fail();
    }

    let header: Vec<&str> = lines[0].split_ascii_whitespace().collect();
    if header.len() != 2 {
        fail();
    }
    let r = match parse_dim(header[0]) {
        Some(v) => v,
        None => fail(),
    };
    let c = match parse_dim(header[1]) {
        Some(v) => v,
        None => fail(),
    };
    if r * c > 1_000_000 {
        fail();
    }

    if lines.len() < 1 + r {
        fail();
    }
    for extra in &lines[1 + r..] {
        if !extra.trim().is_empty() {
            fail();
        }
    }

    let mut matrix: Vec<Vec<i64>> = Vec::with_capacity(r);
    for i in 0..r {
        let toks: Vec<&str> = lines[1 + i].split_ascii_whitespace().collect();
        if toks.len() != c {
            fail();
        }
        let mut row = Vec::with_capacity(c);
        for t in toks {
            match parse_val(t) {
                Some(v) => row.push(v),
                None => fail(),
            }
        }
        matrix.push(row);
    }

    let mut out = String::new();

    for (i, row) in matrix.iter().enumerate() {
        let mut s: i64 = 0;
        for &v in row {
            s = s.wrapping_add(v);
        }
        out.push_str(&format!("row {} {}\n", i, s));
    }

    let mut col_sums = vec![0i64; c];
    for row in &matrix {
        for (j, &v) in row.iter().enumerate() {
            col_sums[j] = col_sums[j].wrapping_add(v);
        }
    }
    for (j, s) in col_sums.iter().enumerate() {
        out.push_str(&format!("col {} {}\n", j, s));
    }

    let mut best: Option<(i64, usize, usize)> = None;
    for (i, row) in matrix.iter().enumerate() {
        for (j, &v) in row.iter().enumerate() {
            match best {
                None => best = Some((v, i, j)),
                Some((bv, _, _)) if v > bv => best = Some((v, i, j)),
                _ => {}
            }
        }
    }
    match best {
        None => out.push_str("max none\n"),
        Some((v, i, j)) => out.push_str(&format!("max {} at {} {}\n", v, i, j)),
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
