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
    let n = next() as usize;
    let m = next() as usize;
    let q = next() as usize;
    let x: Vec<i64> = (0..n).map(|_| next() as i64).collect();
    let mut su = Vec::with_capacity(m);
    let mut sv = Vec::with_capacity(m);
    let mut st = Vec::with_capacity(m);
    let mut ent: Vec<(u64, u32)> = Vec::with_capacity(2 * m);
    for i in 0..m {
        let u = next();
        let v = next();
        let l = next();
        let t = next() as i64;
        su.push(0u32);
        sv.push(0u32);
        st.push(t);
        ent.push((u * 100000 + l, (2 * i) as u32));
        ent.push((v * 100000 + l, (2 * i + 1) as u32));
    }
    ent.sort_unstable();
    // assign node ids
    let mut slot_node = vec![0u32; 2 * m];
    let mut node_station: Vec<u32> = Vec::new();
    let mut last = u64::MAX;
    for &(k, s) in &ent {
        if k != last {
            node_station.push((k / 100000) as u32);
            last = k;
        }
        slot_node[s as usize] = (node_station.len() - 1) as u32;
    }
    let nn = node_station.len();
    // station ranges over nodes
    let mut st_start = vec![0u32; n + 1];
    for &s in &node_station {
        st_start[s as usize + 1] += 1;
    }
    for i in 0..n {
        st_start[i + 1] += st_start[i];
    }
    for i in 0..m {
        su[i] = slot_node[2 * i];
        sv[i] = slot_node[2 * i + 1];
    }
    // CSR
    let mut deg = vec![0u32; nn + 1];
    for i in 0..m {
        if su[i] != sv[i] {
            deg[su[i] as usize + 1] += 1;
            deg[sv[i] as usize + 1] += 1;
        }
    }
    for i in 0..nn {
        deg[i + 1] += deg[i];
    }
    let mut fill = deg.clone();
    let mut adj = vec![(0u32, 0i64); deg[nn] as usize];
    for i in 0..m {
        if su[i] != sv[i] {
            let a = su[i] as usize;
            let b = sv[i] as usize;
            adj[fill[a] as usize] = (b as u32, st[i]);
            fill[a] += 1;
            adj[fill[b] as usize] = (a as u32, st[i]);
            fill[b] += 1;
        }
    }
    // ids: hubs 0..n, line nodes n..n+nn
    let total = n + nn;
    let inf = (i64::MAX, i64::MAX);
    let mut dist = [vec![inf; total], vec![inf; total]];
    let mut touched: [Vec<u32>; 2] = [Vec::new(), Vec::new()];
    let mut out = String::new();
    type H = BinaryHeap<Reverse<(i64, i64, u32)>>;
    for _ in 0..q {
        let s = next() as usize;
        let d = next() as usize;
        if s == d {
            out.push_str("0 0\n");
            continue;
        }
        for k in 0..2 {
            for &t in &touched[k] {
                dist[k][t as usize] = inf;
            }
            touched[k].clear();
        }
        let mut heaps: [H; 2] = [BinaryHeap::new(), BinaryHeap::new()];
        dist[0][s] = (-x[s], 0);
        touched[0].push(s as u32);
        heaps[0].push(Reverse((-x[s], 0, s as u32)));
        dist[1][d] = (0, 0);
        touched[1].push(d as u32);
        heaps[1].push(Reverse((0, 0, d as u32)));
        let mut best = inf;
        loop {
            let tf = heaps[0].peek().map(|r| (r.0 .0, r.0 .1));
            let tr = heaps[1].peek().map(|r| (r.0 .0, r.0 .1));
            let (tf, tr) = match (tf, tr) {
                (Some(a), Some(b)) => (a, b),
                _ => break,
            };
            if best != inf && (tf.0 + tr.0, tf.1 + tr.1 - 1) >= best {
                break;
            }
            let dir = if tf <= tr { 0 } else { 1 };
            let Reverse((t, b, u)) = heaps[dir].pop().unwrap();
            let u = u as usize;
            if dist[dir][u] != (t, b) {
                continue;
            }
            if u < n {
                let o = dist[1 - dir][u];
                if o != inf {
                    let c = (t + o.0, b + o.1);
                    if c < best {
                        best = c;
                    }
                }
                let (nt, nb) = if dir == 0 { (t + x[u], b + 1) } else { (t, b + 1) };
                for k in st_start[u]..st_start[u + 1] {
                    let v = n + k as usize;
                    if (nt, nb) < dist[dir][v] {
                        if dist[dir][v] == inf {
                            touched[dir].push(v as u32);
                        }
                        dist[dir][v] = (nt, nb);
                        heaps[dir].push(Reverse((nt, nb, v as u32)));
                        let o = dist[1 - dir][v];
                        if o != inf {
                            let c = (nt + o.0, nb + o.1 - 1);
                            if c < best {
                                best = c;
                            }
                        }
                    }
                }
            } else {
                let id = u - n;
                let h = node_station[id] as usize;
                let ht = if dir == 1 { t + x[h] } else { t };
                if (ht, b) < dist[dir][h] {
                    if dist[dir][h] == inf {
                        touched[dir].push(h as u32);
                    }
                    dist[dir][h] = (ht, b);
                    heaps[dir].push(Reverse((ht, b, h as u32)));
                    let o = dist[1 - dir][h];
                    if o != inf {
                        let c = (ht + o.0, b + o.1);
                        if c < best {
                            best = c;
                        }
                    }
                }
                for k in deg[id]..deg[id + 1] {
                    let (v, w) = adj[k as usize];
                    let v = n + v as usize;
                    let nt = t + w;
                    if (nt, b) < dist[dir][v] {
                        if dist[dir][v] == inf {
                            touched[dir].push(v as u32);
                        }
                        dist[dir][v] = (nt, b);
                        heaps[dir].push(Reverse((nt, b, v as u32)));
                        let o = dist[1 - dir][v];
                        if o != inf {
                            let c = (nt + o.0, b + o.1 - 1);
                            if c < best {
                                best = c;
                            }
                        }
                    }
                }
            }
        }
        if best == inf {
            out.push_str("none\n");
        } else {
            out.push_str(&format!("{} {}\n", best.0, best.1));
        }
    }
    std::io::stdout().write_all(out.as_bytes()).unwrap();
}
