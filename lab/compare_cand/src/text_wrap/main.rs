use std::io::{Read, Write};

fn main() {
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data).unwrap();
    let n = data.len();

    let mut e = 0usize;
    while e < n && data[e] != 10 {
        e += 1;
    }
    if e < 1 || e > 3 {
        std::process::exit(2);
    }
    let mut w: i64 = 0;
    for k in 0..e {
        let c = data[k];
        if c < 48 || c > 57 {
            std::process::exit(2);
        }
        w = w * 10 + (c - 48) as i64;
    }
    if w < 10 || w > 200 {
        std::process::exit(2);
    }

    let mut pos = if e < n { e + 1 } else { n };
    let mut paragraphs: i64 = 0;
    let mut lines: i64 = 0;
    let mut words: i64 = 0;
    let mut longest: i64 = 0;
    let mut h: i64 = 0;
    let mut emitted_any = false;
    let mut in_para = false;
    let mut first_line = false;
    let mut cur_len: i64 = 0;

    loop {
        let mut e = pos;
        while e < n && data[e] != 10 {
            e += 1;
        }
        let a = pos;
        let mut blank = true;
        let mut k = a;
        while k < e {
            if data[k] != 32 {
                blank = false;
                break;
            }
            k += 1;
        }
        if blank {
            if in_para {
                in_para = false;
                cur_len = 0;
            }
        } else {
            let mut k = a;
            while k < e {
                let c = data[k];
                if c == 32 || c == 9 {
                    k += 1;
                    continue;
                }
                let ws = k;
                while k < e {
                    let c = data[k];
                    if c == 32 || c == 9 {
                        break;
                    }
                    k += 1;
                }
                let wl = (k - ws) as i64;
                words += 1;
                if !in_para {
                    in_para = true;
                    first_line = true;
                    paragraphs += 1;
                }
                if cur_len == 0 {
                    if first_line {
                        if emitted_any {
                            h = (h * 131 + 10) % 1000000007;
                            h = (h * 131 + 10) % 1000000007;
                        }
                        emitted_any = true;
                        first_line = false;
                    } else {
                        h = (h * 131 + 10) % 1000000007;
                    }
                    lines += 1;
                    cur_len = wl;
                } else if cur_len + 1 + wl <= w {
                    h = (h * 131 + 32) % 1000000007;
                    cur_len += 1 + wl;
                } else {
                    h = (h * 131 + 10) % 1000000007;
                    lines += 1;
                    cur_len = wl;
                }
                for p in ws..k {
                    h = (h * 131 + data[p] as i64) % 1000000007;
                }
                if cur_len > longest {
                    longest = cur_len;
                }
            }
        }
        if e >= n {
            break;
        }
        pos = e + 1;
    }

    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    writeln!(out, "paragraphs {} lines {} words {} longest {} hash {}",
             paragraphs, lines, words, longest, h).unwrap();
}
