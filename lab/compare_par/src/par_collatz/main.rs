// par_collatz: Collatz step counts for 1..N on W scoped threads over chunks_mut (see spec.md).
use std::io::Read;

fn steps(mut m: u64) -> u64 {
    let mut c = 0u64;
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
    let mut it = text.split_whitespace();
    let n: usize = it.next().unwrap().parse().unwrap();
    let w: usize = it.next().unwrap().parse().unwrap();
    let threads = if w < n { w } else { n.max(1) };
    let chunk = (n + threads - 1) / threads;
    let mut res = vec![0u64; n];
    std::thread::scope(|s| {
        for (i, part) in res.chunks_mut(chunk).enumerate() {
            let lo = i * chunk + 1;
            s.spawn(move || {
                for (k, slot) in part.iter_mut().enumerate() {
                    *slot = steps((lo + k) as u64);
                }
            });
        }
    });
    let mut best: i64 = -1;
    let mut bestn: usize = 0;
    let mut total: u64 = 0;
    for (i, &v) in res.iter().enumerate() {
        total += v;
        if v as i64 > best {
            best = v as i64;
            bestn = i + 1;
        }
    }
    println!("{} {} {}", best, bestn, total);
}
