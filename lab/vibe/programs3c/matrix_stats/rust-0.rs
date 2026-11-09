use std::io::{self, Read, Write};

fn fail() -> ! {
    println!("error");
    std::process::exit(2);
}

fn parse_dim(s: &str) -> Option<usize> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    s.parse::<u64>().ok().and_then(|v| usize::try_from(v).ok())
}

fn main() {
    let mut buf = Vec::new();
    if io::stdin().read_to_end(&mut buf).is_err() {
        fail();
    }
    let text = String::from_utf8_lossy(&buf);
    let mut lines = text.split('\n');

    let header = match lines.next() {
        Some(h) => h,
        None => fail(),
    };
    let toks: Vec<&str> = header.split_ascii_whitespace().collect();
    if toks.len() != 2 {
        fail();
    }
    let r = match parse_dim(toks[0]) {
        Some(v) => v,
        None => fail(),
    };
    let c = match parse_dim(toks[1]) {
        Some(v) => v,
        None => fail(),
    };
    if r > 10000 || c > 10000 {
        fail();
    }
    if r * c > 1_000_000 {
        fail();
    }

    let mut col_sums = vec![0i64; c];
    let mut out = String::new();
    let mut best: Option<(i64, usize, usize)> = None;

    for i in 0..r {
        let line: &str = match lines.next() {
            Some(l) => l,
            None => {
                if c == 0 {
                    ""
                } else {
                    fail()
                }
            }
        };

        let mut count = 0usize;
        let mut rs: i64 = 0;
        for tok in line.split_ascii_whitespace() {
            if count >= c {
                fail();
            }
            let v: i64 = match tok.parse::<i64>() {
                Ok(v) => v,
                Err(_) => fail(),
            };
            rs = rs.wrapping_add(v);
            col_sums[count] = col_sums[count].wrapping_add(v);
            match best {
                Some((b, _, _)) if v <= b => {}
                _ => best = Some((v, i, count)),
            }
            count += 1;
        }
        if count != c {
            fail();
        }
        out.push_str(&format!("row {} {}\n", i, rs));
    }

    for (j, s) in col_sums.iter().enumerate() {
        out.push_str(&format!("col {} {}\n", j, s));
    }

    match best {
        Some((v, r_idx, c_idx)) => {
            out.push_str(&format!("max {} at {} {}\n", v, r_idx, c_idx));
        }
        None => {
            out.push_str("max none\n");
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
