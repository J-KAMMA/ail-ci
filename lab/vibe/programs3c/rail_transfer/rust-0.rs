use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

fn relax(
    dt: &mut [i64],
    db: &mut [i64],
    touched: &mut Vec<usize>,
    heap: &mut BinaryHeap<Reverse<(i64, i64, usize)>>,
    v: usize,
    nt: i64,
    nb: i64,
) {
    if nt < dt[v] || (nt == dt[v] && nb < db[v]) {
        if dt[v] == i64::MAX {
            touched.push(v);
        }
        dt[v] = nt;
        db[v] = nb;
        heap.push(Reverse((nt, nb, v)));
    }
}

fn main() {
    let mut buf = Vec::new();
    io::stdin().read_to_end(&mut buf).unwrap();
    let mut pos = 0usize;
    let mut next = || -> u64 {
        while pos < buf.len() && !buf[pos].is_ascii_digit() {
            pos += 1;
        }
        let mut v = 0u64;
        while pos < buf.len() && buf[pos].is_ascii_digit() {
            v = v * 10 + (buf[pos] - b'0') as u64;
            pos += 1;
        }
        v
    };

    let n = next() as usize;
    let m = next() as usize;
    let q = next() as usize;
    let x: Vec<i64> = (0..n).map(|_| next() as i64).collect();

    let two_m = 2 * m;
    let mut src = vec![0u32; two_m];
    let mut line = vec![0u32; two_m];
    let mut tt = vec![0i64; two_m];
    for i in 0..m {
        let u = next() as u32;
        let v = next() as u32;
        let l = next() as u32;
        let t = next() as i64;
        src[2 * i] = u;
        line[2 * i] = l;
        tt[2 * i] = t;
        src[2 * i + 1] = v;
        line[2 * i + 1] = l;
        tt[2 * i + 1] = t;
    }
    // Directed edge k goes src[k] -> src[k^1].
    let mut keys: Vec<(u64, u32)> = (0..two_m)
        .map(|k| (((src[k] as u64) << 20) | line[k] as u64, k as u32))
        .collect();
    keys.sort_unstable();

    let mut pos_of = vec![0u32; two_m];
    for (p, &(_, k)) in keys.iter().enumerate() {
        pos_of[k as usize] = p as u32;
    }

    // Station position ranges.
    let mut st = vec![0usize; n + 1];
    for k in 0..two_m {
        st[src[k] as usize + 1] += 1;
    }
    for v in 0..n {
        st[v + 1] += st[v];
    }

    // Groups: maximal runs of same (station, line) in sorted order.
    let mut g_start: Vec<usize> = Vec::new();
    let mut g_station: Vec<usize> = Vec::new();
    let mut e_group = vec![0usize; two_m];
    let mut prev_key = u64::MAX;
    for (p, &(key, k)) in keys.iter().enumerate() {
        if key != prev_key {
            g_start.push(p);
            g_station.push(src[k as usize] as usize);
            prev_key = key;
        }
        e_group[p] = g_start.len() - 1;
    }
    let gcount = g_start.len();
    g_start.push(two_m);

    // Per position: target node when traversing this directed edge (riding state at arrival).
    let mut e_arr = vec![0usize; two_m];
    let mut e_t = vec![0i64; two_m];
    for p in 0..two_m {
        let k = keys[p].1 as usize;
        let tw = pos_of[k ^ 1] as usize;
        e_arr[p] = n + e_group[tw];
        e_t[p] = tt[k];
    }
    drop(e_group);

    let start_node = n + gcount;
    let total = n + gcount + 1;
    let mut dt = vec![i64::MAX; total];
    let mut db = vec![i64::MAX; total];
    let mut touched: Vec<usize> = Vec::new();
    let mut heap: BinaryHeap<Reverse<(i64, i64, usize)>> = BinaryHeap::new();

    let mut out = String::new();
    for _ in 0..q {
        let s = next() as usize;
        let d = next() as usize;
        if s == d {
            out.push_str("0 0\n");
            continue;
        }

        heap.clear();
        dt[start_node] = 0;
        db[start_node] = 0;
        touched.push(start_node);
        heap.push(Reverse((0, 0, start_node)));

        let mut found = false;
        while let Some(Reverse((t, b, u))) = heap.pop() {
            if t != dt[u] || b != db[u] {
                continue;
            }
            if u == d {
                found = true;
                break;
            }
            if u == start_node {
                for p in st[s]..st[s + 1] {
                    relax(&mut dt, &mut db, &mut touched, &mut heap, e_arr[p], t + e_t[p], 1);
                }
            } else if u < n {
                let add = x[u];
                for p in st[u]..st[u + 1] {
                    relax(
                        &mut dt,
                        &mut db,
                        &mut touched,
                        &mut heap,
                        e_arr[p],
                        t + add + e_t[p],
                        b + 1,
                    );
                }
            } else {
                let g = u - n;
                for p in g_start[g]..g_start[g + 1] {
                    relax(&mut dt, &mut db, &mut touched, &mut heap, e_arr[p], t + e_t[p], b);
                }
                relax(&mut dt, &mut db, &mut touched, &mut heap, g_station[g], t, b);
            }
        }

        if found {
            out.push_str(&format!("{} {}\n", dt[d], db[d]));
        } else {
            out.push_str("none\n");
        }

        for &v in &touched {
            dt[v] = i64::MAX;
            db[v] = i64::MAX;
        }
        touched.clear();
    }

    io::stdout().write_all(out.as_bytes()).unwrap();
}
