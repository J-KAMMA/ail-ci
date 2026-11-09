use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

fn add(
    fp: &mut [usize],
    to: &mut [u32],
    tt: &mut [u32],
    bb: &mut [u8],
    from: usize,
    dst: u32,
    w: u32,
    b: u8,
) {
    let p = fp[from];
    fp[from] += 1;
    to[p] = dst;
    tt[p] = w;
    bb[p] = b;
}

fn main() {
    let mut inp = Vec::new();
    io::stdin().read_to_end(&mut inp).unwrap();
    let mut pos = 0usize;
    let mut rd = || -> u64 {
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

    let n = rd() as usize;
    let m = rd() as usize;
    let q = rd() as usize;

    let mut x = vec![0u32; n];
    for i in 0..n {
        x[i] = rd() as u32;
    }

    let mut segs: Vec<(u32, u32, u32, u32)> = Vec::with_capacity(m);
    let mut keys: Vec<u64> = Vec::with_capacity(2 * m);
    for _ in 0..m {
        let u = rd();
        let v = rd();
        let l = rd();
        let t = rd();
        segs.push((u as u32, v as u32, l as u32, t as u32));
        keys.push((u << 32) | l);
        keys.push((v << 32) | l);
    }
    keys.sort_unstable();
    keys.dedup();

    let kc = keys.len();
    let total = kc + n;

    let mut sa: Vec<u32> = Vec::with_capacity(m);
    let mut sb: Vec<u32> = Vec::with_capacity(m);
    let mut st: Vec<u32> = Vec::with_capacity(m);
    for &(u, v, l, t) in &segs {
        let ka = ((u as u64) << 32) | l as u64;
        let kb = ((v as u64) << 32) | l as u64;
        let a = keys.binary_search(&ka).unwrap();
        let b = keys.binary_search(&kb).unwrap();
        sa.push(a as u32);
        sb.push(b as u32);
        st.push(t);
    }
    drop(segs);

    // Degree counting
    let mut cnt = vec![0usize; total];
    for i in 0..m {
        cnt[sa[i] as usize] += 1;
        cnt[sb[i] as usize] += 1;
    }
    for r in 0..kc {
        let v = (keys[r] >> 32) as usize;
        cnt[r] += 1;
        cnt[kc + v] += 1;
    }
    let mut off = vec![0usize; total + 1];
    for i in 0..total {
        off[i + 1] = off[i] + cnt[i];
    }
    let e_total = off[total];
    let mut to = vec![0u32; e_total];
    let mut tt = vec![0u32; e_total];
    let mut bb = vec![0u8; e_total];
    let mut fp: Vec<usize> = off[..total].to_vec();

    for i in 0..m {
        let a = sa[i] as usize;
        let b = sb[i] as usize;
        let t = st[i];
        add(&mut fp, &mut to, &mut tt, &mut bb, a, b as u32, t, 0);
        add(&mut fp, &mut to, &mut tt, &mut bb, b, a as u32, t, 0);
    }
    for r in 0..kc {
        let v = (keys[r] >> 32) as usize;
        add(&mut fp, &mut to, &mut tt, &mut bb, r, (kc + v) as u32, 0, 0);
        add(&mut fp, &mut to, &mut tt, &mut bb, kc + v, r as u32, x[v], 1);
    }
    drop(fp);
    drop(cnt);

    let mut dist: Vec<(i64, u32)> = vec![(i64::MAX, u32::MAX); total];
    let mut out = String::new();

    for _ in 0..q {
        let s = rd();
        let d = rd();
        if s == d {
            out.push_str("0 0\n");
            continue;
        }
        for e in dist.iter_mut() {
            *e = (i64::MAX, u32::MAX);
        }
        let mut heap: BinaryHeap<Reverse<(i64, u32, u32)>> = BinaryHeap::new();
        let lo = keys.partition_point(|&k| (k >> 32) < s);
        let hi = keys.partition_point(|&k| (k >> 32) <= s);
        for r in lo..hi {
            dist[r] = (0, 1);
            heap.push(Reverse((0, 1, r as u32)));
        }
        let target = kc + d as usize;
        let mut ans: Option<(i64, u32)> = None;
        while let Some(Reverse((t, b, u))) = heap.pop() {
            let u = u as usize;
            if (t, b) != dist[u] {
                continue;
            }
            if u == target {
                ans = Some((t, b));
                break;
            }
            for e in off[u]..off[u + 1] {
                let v = to[e] as usize;
                let nt = t + tt[e] as i64;
                let nb = b + bb[e] as u32;
                if (nt, nb) < dist[v] {
                    dist[v] = (nt, nb);
                    heap.push(Reverse((nt, nb, v as u32)));
                }
            }
        }
        match ans {
            Some((t, b)) => out.push_str(&format!("{} {}\n", t, b)),
            None => out.push_str("none\n"),
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    lock.write_all(out.as_bytes()).unwrap();
    lock.flush().unwrap();
}
