use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

fn main() {
    let mut inp = Vec::new();
    io::stdin().read_to_end(&mut inp).unwrap();
    let mut pos = 0usize;
    let mut next = || -> u64 {
        while pos < inp.len() && !inp[pos].is_ascii_digit() {
            pos += 1;
        }
        let mut v: u64 = 0;
        while pos < inp.len() && inp[pos].is_ascii_digit() {
            v = v * 10 + (inp[pos] - b'0') as u64;
            pos += 1;
        }
        v
    };

    let nb = next() as usize;
    let s = next() as usize;
    let mut cls = vec![0usize; nb];
    let mut rate = vec![1u64; nb];
    for b in 0..nb {
        cls[b] = next() as usize;
        rate[b] = next();
    }
    // (arrival, prio, id, size, cargo, op)
    let mut arr: Vec<(u64, u64, u64, usize, u64, u64)> = Vec::with_capacity(s);
    for _ in 0..s {
        let id = next();
        let a = next();
        let sz = next() as usize;
        let cg = next();
        let pr = next();
        let op = next();
        arr.push((a, pr, id, sz, cg, op));
    }
    drop(inp);
    arr.sort_unstable_by_key(|x| x.0);

    // waiting heaps per size: (prio, arrival, id, cargo, op)
    let mut wait: Vec<BinaryHeap<Reverse<(u64, u64, u64, u64, u64)>>> =
        (0..3).map(|_| BinaryHeap::new()).collect();
    // free berths per class (index class-1)
    let mut free: Vec<BinaryHeap<Reverse<usize>>> = (0..3).map(|_| BinaryHeap::new()).collect();
    for b in 0..nb {
        free[cls[b] - 1].push(Reverse(b));
    }
    let mut dep: BinaryHeap<Reverse<(u64, usize)>> = BinaryHeap::new();
    let mut cnt = vec![0u64; nb];
    let mut busy = vec![0u64; nb];
    let mut last_op = vec![u64::MAX; nb];
    let mut res: Vec<(u64, u64, usize)> = Vec::with_capacity(s); // (id, start, berth)
    let mut total_wait: u64 = 0;
    let mut max_w: i64 = -1;
    let mut max_id: i64 = -1;
    let mut makespan: u64 = 0;
    let mut ai = 0usize;

    loop {
        let na = if ai < s { arr[ai].0 } else { u64::MAX };
        let nd = match dep.peek() {
            Some(&Reverse((t, _))) => t,
            None => u64::MAX,
        };
        if na == u64::MAX && nd == u64::MAX {
            break;
        }
        let t = na.min(nd);

        // 1. departures at t
        while let Some(&Reverse((dt, b))) = dep.peek() {
            if dt != t {
                break;
            }
            dep.pop();
            free[cls[b] - 1].push(Reverse(b));
        }

        // 2. arrivals at t
        while ai < s && arr[ai].0 == t {
            let (a, pr, id, sz, cg, op) = arr[ai];
            wait[sz - 1].push(Reverse((pr, a, id, cg, op)));
            ai += 1;
        }

        // 3. assignment, classes ascending, berths ascending within class
        for cc in 0..3usize {
            loop {
                if free[cc].is_empty() {
                    break;
                }
                let mut best: Option<usize> = None;
                for sidx in 0..=cc {
                    if let Some(top) = wait[sidx].peek() {
                        match best {
                            None => best = Some(sidx),
                            Some(bs) => {
                                if top > wait[bs].peek().unwrap() {
                                    best = Some(sidx);
                                }
                            }
                        }
                    }
                }
                let sidx = match best {
                    Some(x) => x,
                    None => break,
                };
                let Reverse(b) = free[cc].pop().unwrap();
                let Reverse((_pr, a, id, cg, op)) = wait[sidx].pop().unwrap();
                let r = rate[b];
                let setup = if last_op[b] == op { 1 } else { 4 };
                let dur = (cg + r - 1) / r + setup;
                let end = t + dur;
                let w = t - a;
                total_wait += w;
                let wi = w as i64;
                let idi = id as i64;
                if wi > max_w || (wi == max_w && idi < max_id) {
                    max_w = wi;
                    max_id = idi;
                }
                cnt[b] += 1;
                busy[b] += dur;
                last_op[b] = op;
                dep.push(Reverse((end, b)));
                if end > makespan {
                    makespan = end;
                }
                res.push((id, t, b));
            }
        }
    }

    res.sort_unstable_by_key(|x| x.0);
    let md = 1_000_000_007u64;
    let mut g = 0u64;
    for &(_, st, b) in &res {
        g = (g * 1000003 + st * 31 + b as u64) % md;
    }

    let (mw, mi) = if s == 0 { (0i64, -1i64) } else { (max_w, max_id) };

    let mut out = String::new();
    out.push_str(&format!("ships {}\n", s));
    out.push_str(&format!("makespan {}\n", makespan));
    out.push_str(&format!("wait total {} max {} ship {}\n", total_wait, mw, mi));
    for b in 0..nb {
        out.push_str(&format!("berth {} ships {} busy {}\n", b, cnt[b], busy[b]));
    }
    out.push_str(&format!("digest {}\n", g));

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    lock.write_all(out.as_bytes()).unwrap();
    lock.flush().unwrap();
}
