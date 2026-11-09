// par_sum: sum over n in 1..N of steps(n) * (n % 7 - 3) on 4 scoped threads with per-thread partial sums.
use std::io::Read;

const NTHREADS: i64 = 4;

fn add(a: i64, b: i64) -> i64 {
    match a.checked_add(b) {
        Some(r) => r,
        None => {
            eprintln!("OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)");
            std::process::exit(1);
        }
    }
}

fn steps(mut m: i64) -> i64 {
    let mut c = 0i64;
    while m != 1 {
        if m & 1 == 1 {
            m = 3 * m + 1;
        } else {
            m >>= 1;
        }
        c += 1;
    }
    c
}

fn main() {
    let mut text = String::new();
    std::io::stdin().read_to_string(&mut text).unwrap();
    let n: i64 = text.split_whitespace().next().unwrap().parse().unwrap();
    if n < 0 {
        std::process::exit(1);
    }
    if n == 0 {
        println!("0");
        return;
    }
    let threads = if n < NTHREADS { n } else { NTHREADS };
    let chunk = (n + threads - 1) / threads;
    let parts: Vec<i64> = std::thread::scope(|s| {
        let mut handles = Vec::new();
        for t in 0..threads {
            let lo = t * chunk + 1;
            let mut hi = lo + chunk - 1;
            if lo > n {
                break;
            }
            if hi > n {
                hi = n;
            }
            handles.push(s.spawn(move || {
                let mut acc = 0i64;
                for k in lo..=hi {
                    acc = add(acc, steps(k) * (k % 7 - 3));
                }
                acc
            }));
        }
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut total = 0i64;
    for v in parts {
        total = add(total, v);
    }
    println!("{}", total);
}
