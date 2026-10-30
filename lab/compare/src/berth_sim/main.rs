use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{Read, Write};

fn main() {
    let mut inp = Vec::new();
    std::io::stdin().read_to_end(&mut inp).unwrap();
    let mut pos = 0usize;
    let mut next = || -> u64 {
        while pos < inp.len() && !(inp[pos] >= b'0' && inp[pos] <= b'9') {
            pos += 1;
        }
        let mut v = 0u64;
        while pos < inp.len() && inp[pos] >= b'0' && inp[pos] <= b'9' {
            v = v * 10 + (inp[pos] - b'0') as u64;
            pos += 1;
        }
        v
    };
    let b = next() as usize;
    let s = next() as usize;
    let mut class = vec![0usize; b];
    let mut rate = vec![0u64; b];
    for i in 0..b {
        class[i] = next() as usize;
        rate[i] = next();
    }
    let mut id = vec![0u32; s];
    let mut arr = vec![0u32; s];
    let mut size = vec![0u8; s];
    let mut cargo = vec![0u32; s];
    let mut prio = vec![0u8; s];
    let mut op = vec![0u32; s];
    for i in 0..s {
        id[i] = next() as u32;
        arr[i] = next() as u32;
        size[i] = next() as u8;
        cargo[i] = next() as u32;
        prio[i] = next() as u8;
        op[i] = next() as u32;
    }
    let mut order: Vec<u32> = (0..s as u32).collect();
    order.sort_unstable_by_key(|&i| arr[i as usize]);

    let mut start = vec![0u64; s];
    let mut sber = vec![0u32; s];
    let mut last_op = vec![u32::MAX; b];
    let mut cnt = vec![0u64; b];
    let mut busy = vec![0u64; b];
    let mut free: Vec<BinaryHeap<Reverse<u32>>> = (0..4).map(|_| BinaryHeap::new()).collect();
    for i in 0..b {
        free[class[i]].push(Reverse(i as u32));
    }
    let mut wait: Vec<BinaryHeap<Reverse<(u64, u32)>>> = (0..4).map(|_| BinaryHeap::new()).collect();
    let mut deps: BinaryHeap<Reverse<(u64, u32)>> = BinaryHeap::new();
    let mut ni = 0usize;
    let mut makespan = 0u64;
    loop {
        let ta = if ni < s { Some(arr[order[ni] as usize] as u64) } else { None };
        let td = deps.peek().map(|r| (r.0).0);
        let t = match (ta, td) {
            (None, None) => break,
            (Some(a), None) => a,
            (None, Some(d)) => d,
            (Some(a), Some(d)) => a.min(d),
        };
        while let Some(Reverse((dt, bb))) = deps.peek().cloned() {
            if dt != t {
                break;
            }
            deps.pop();
            free[class[bb as usize]].push(Reverse(bb));
            makespan = makespan.max(dt);
        }
        while ni < s && arr[order[ni] as usize] as u64 == t {
            let i = order[ni] as usize;
            let key = ((prio[i] as u64) << 60) | ((arr[i] as u64) << 30) | id[i] as u64;
            wait[size[i] as usize].push(Reverse((key, i as u32)));
            ni += 1;
        }
        for c in 1..=3usize {
            loop {
                if free[c].is_empty() {
                    break;
                }
                // best among sizes <= c
                let mut best: Option<(u64, usize)> = None;
                for z in 1..=c {
                    if let Some(Reverse((k, _))) = wait[z].peek() {
                        if best.map_or(true, |(bk, _)| *k < bk) {
                            best = Some((*k, z));
                        }
                    }
                }
                let z = match best {
                    Some((_, z)) => z,
                    None => break,
                };
                let Reverse((_, si)) = wait[z].pop().unwrap();
                let si = si as usize;
                let Reverse(bb) = free[c].pop().unwrap();
                let bu = bb as usize;
                let setup = if last_op[bu] == op[si] { 1 } else { 4 };
                let r = rate[bu];
                let svc = (cargo[si] as u64 + r - 1) / r + setup;
                last_op[bu] = op[si];
                cnt[bu] += 1;
                busy[bu] += svc;
                start[si] = t;
                sber[si] = bb;
                deps.push(Reverse((t + svc, bb)));
            }
        }
    }
    let mut total = 0u64;
    let mut mx = 0u64;
    let mut mxid = -1i64;
    let mut ids: Vec<u32> = (0..s as u32).collect();
    ids.sort_unstable_by_key(|&i| id[i as usize]);
    let mut g = 0u64;
    for &i in &ids {
        let i = i as usize;
        let w = start[i] - arr[i] as u64;
        total += w;
        if mxid < 0 || w > mx {
            mx = w;
            mxid = id[i] as i64;
        }
        g = (g * 1000003 + start[i] * 31 + sber[i] as u64) % 1000000007;
    }
    let mut out = String::new();
    out.push_str(&format!("ships {}\nmakespan {}\n", s, makespan));
    out.push_str(&format!("wait total {} max {} ship {}\n", total, mx, mxid));
    for i in 0..b {
        out.push_str(&format!("berth {} ships {} busy {}\n", i, cnt[i], busy[i]));
    }
    out.push_str(&format!("digest {}\n", g));
    std::io::stdout().write_all(out.as_bytes()).unwrap();
}
