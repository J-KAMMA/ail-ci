use std::cmp::Reverse;
use std::collections::{BTreeSet, BinaryHeap};
use std::io::{self, BufWriter, Read, Write};

struct Ship {
    start: u64,
    id: u32,
    arr: u32,
    cargo: u32,
    op: u32,
    berth: u32,
    prio: u8,
    size: u8,
}

struct Berth {
    class: u8,
    rate: u64,
    last_op: Option<u32>,
    count: u64,
    busy: u64,
}

fn main() {
    let mut inp = Vec::new();
    io::stdin().read_to_end(&mut inp).unwrap();
    let mut pos = 0usize;
    let mut next = || -> u64 {
        while pos < inp.len() && !inp[pos].is_ascii_digit() {
            pos += 1;
        }
        let mut v = 0u64;
        while pos < inp.len() && inp[pos].is_ascii_digit() {
            v = v * 10 + (inp[pos] - b'0') as u64;
            pos += 1;
        }
        v
    };

    let nb = next() as usize;
    let ns = next() as usize;

    let mut berths: Vec<Berth> = Vec::with_capacity(nb);
    for _ in 0..nb {
        let c = next() as u8;
        let r = next();
        berths.push(Berth {
            class: c,
            rate: r,
            last_op: None,
            count: 0,
            busy: 0,
        });
    }

    let mut ships: Vec<Ship> = Vec::with_capacity(ns);
    for _ in 0..ns {
        let id = next() as u32;
        let arr = next() as u32;
        let size = next() as u8;
        let cargo = next() as u32;
        let prio = next() as u8;
        let op = next() as u32;
        ships.push(Ship {
            start: 0,
            id,
            arr,
            cargo,
            op,
            berth: 0,
            prio,
            size,
        });
    }

    let mut ord: Vec<u64> = (0..ns)
        .map(|i| ((ships[i].arr as u64) << 32) | i as u64)
        .collect();
    ord.sort_unstable();

    let mut waiting: [BinaryHeap<Reverse<(u32, u32, u32, u32)>>; 4] = Default::default();
    let mut free: [BTreeSet<usize>; 4] = Default::default();
    for b in 0..nb {
        free[berths[b].class as usize].insert(b);
    }

    let mut deps: BinaryHeap<Reverse<(u64, u32)>> = BinaryHeap::new();
    let mut makespan: u64 = 0;
    let mut ap = 0usize;
    let mut waiting_cnt = 0usize;

    loop {
        let next_arr = if ap < ns {
            Some(ord[ap] >> 32)
        } else {
            None
        };
        let next_dep = deps.peek().map(|Reverse((t, _))| *t);
        let t = match (next_arr, next_dep) {
            (None, None) => break,
            (Some(a), None) => a,
            (None, Some(d)) => d,
            (Some(a), Some(d)) => a.min(d),
        };

        while let Some(&Reverse((dt, b))) = deps.peek() {
            if dt != t {
                break;
            }
            deps.pop();
            let bi = b as usize;
            free[berths[bi].class as usize].insert(bi);
            makespan = t;
        }

        while ap < ns && (ord[ap] >> 32) == t {
            let idx = (ord[ap] & 0xffff_ffff) as usize;
            let s = &ships[idx];
            waiting[s.size as usize].push(Reverse((s.prio as u32, s.arr, s.id, idx as u32)));
            waiting_cnt += 1;
            ap += 1;
        }

        for c in 1..=3usize {
            loop {
                if waiting_cnt == 0 {
                    break;
                }
                let mut best: Option<usize> = None;
                let mut bestkey: Option<(u32, u32, u32, u32)> = None;
                for z in 1..=c {
                    if let Some(Reverse(k)) = waiting[z].peek() {
                        if bestkey.map_or(true, |bk| *k < bk) {
                            bestkey = Some(*k);
                            best = Some(z);
                        }
                    }
                }
                let Some(z) = best else { break };
                let Some(&b) = free[c].iter().next() else { break };
                free[c].remove(&b);
                let Reverse(k) = waiting[z].pop().unwrap();
                waiting_cnt -= 1;
                let idx = k.3 as usize;
                let ship = &mut ships[idx];
                let br = &mut berths[b];
                let setup: u64 = if br.last_op == Some(ship.op) { 1 } else { 4 };
                let svc = (ship.cargo as u64 + br.rate - 1) / br.rate + setup;
                ship.start = t;
                ship.berth = b as u32;
                br.last_op = Some(ship.op);
                br.count += 1;
                br.busy += svc;
                deps.push(Reverse((t + svc, b as u32)));
            }
        }
    }

    let mut total: u64 = 0;
    let mut mx: u64 = 0;
    let mut mxid: i64 = -1;
    for s in &ships {
        let w = s.start - s.arr as u64;
        total += w;
        if mxid < 0 || w > mx || (w == mx && (s.id as i64) < mxid) {
            mx = w;
            mxid = s.id as i64;
        }
    }

    ships.sort_unstable_by_key(|s| s.id);
    let mut g: u64 = 0;
    const MOD: u64 = 1_000_000_007;
    for s in &ships {
        g = (g * 1_000_003 + s.start * 31 + s.berth as u64) % MOD;
    }

    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    writeln!(out, "ships {}", ns).unwrap();
    writeln!(out, "makespan {}", makespan).unwrap();
    writeln!(out, "wait total {} max {} ship {}", total, mx, mxid).unwrap();
    for (b, br) in berths.iter().enumerate() {
        writeln!(out, "berth {} ships {} busy {}", b, br.count, br.busy).unwrap();
    }
    writeln!(out, "digest {}", g).unwrap();
}
