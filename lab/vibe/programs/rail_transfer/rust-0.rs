use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

struct Scanner {
    data: Vec<u8>,
    pos: usize,
}

impl Scanner {
    fn new() -> Self {
        let mut data = Vec::new();
        io::stdin().read_to_end(&mut data).unwrap();
        Scanner { data, pos: 0 }
    }

    #[inline]
    fn next_u64(&mut self) -> u64 {
        let len = self.data.len();
        let mut i = self.pos;

        while i < len && self.data[i] <= b' ' {
            i += 1;
        }

        let mut value = 0u64;
        while i < len && self.data[i] > b' ' {
            value = value * 10 + (self.data[i] - b'0') as u64;
            i += 1;
        }

        self.pos = i;
        value
    }
}

fn main() {
    let mut scanner = Scanner::new();

    let n = scanner.next_u64() as usize;
    let m = scanner.next_u64() as usize;
    let q = scanner.next_u64() as usize;

    let mut transfer_time = vec![0u32; n];
    for value in &mut transfer_time {
        *value = scanner.next_u64() as u32;
    }

    let mut seg_u = vec![0u32; m];
    let mut seg_v = vec![0u32; m];
    let mut seg_line = vec![0u32; m];
    let mut seg_time = vec![0u32; m];

    let mut incidences: Vec<u64> = Vec::with_capacity(2 * m);

    for i in 0..m {
        let u = scanner.next_u64() as u32;
        let v = scanner.next_u64() as u32;
        let line = scanner.next_u64() as u32;
        let t = scanner.next_u64() as u32;

        seg_u[i] = u;
        seg_v[i] = v;
        seg_line[i] = line;
        seg_time[i] = t;

        incidences.push(((line as u64) << 32) | (u as u64));
        incidences.push(((line as u64) << 32) | (v as u64));
    }

    let mut queries = Vec::with_capacity(q);
    for _ in 0..q {
        let s = scanner.next_u64() as u32;
        let d = scanner.next_u64() as u32;
        queries.push((s, d));
    }

    drop(scanner);

    incidences.sort_unstable();
    incidences.dedup();

    let k = incidences.len();
    let node_count = k + n;

    let mut seg_id_u = vec![0u32; m];
    let mut seg_id_v = vec![0u32; m];

    for i in 0..m {
        let line = seg_line[i] as u64;
        let key_u = (line << 32) | (seg_u[i] as u64);
        let key_v = (line << 32) | (seg_v[i] as u64);

        seg_id_u[i] = incidences.binary_search(&key_u).unwrap() as u32;
        seg_id_v[i] = incidences.binary_search(&key_v).unwrap() as u32;
    }

    drop(seg_u);
    drop(seg_v);
    drop(seg_line);

    let mut degree = vec![0u32; node_count];

    for i in 0..m {
        let a = seg_id_u[i] as usize;
        let b = seg_id_v[i] as usize;
        degree[a] += 1;
        degree[b] += 1;
    }

    for i in 0..k {
        let station = (incidences[i] & 0xffff_ffff) as usize;
        degree[i] += 1;
        degree[k + station] += 1;
    }

    let mut start = vec![0u32; node_count + 1];
    let mut total_edges = 0u32;
    for i in 0..node_count {
        start[i] = total_edges;
        total_edges += degree[i];
    }
    start[node_count] = total_edges;

    for i in 0..node_count {
        degree[i] = start[i];
    }

    let edge_count = total_edges as usize;
    let mut to = vec![0u32; edge_count];
    let mut weight = vec![0u64; edge_count];

    for i in 0..m {
        let a = seg_id_u[i] as usize;
        let b = seg_id_v[i] as usize;
        let t = seg_time[i] as u64;

        let p = degree[a] as usize;
        to[p] = b as u32;
        weight[p] = t;
        degree[a] += 1;

        let p = degree[b] as usize;
        to[p] = a as u32;
        weight[p] = t;
        degree[b] += 1;
    }

    for i in 0..k {
        let station = (incidences[i] & 0xffff_ffff) as usize;
        let station_node = k + station;

        let p = degree[i] as usize;
        to[p] = station_node as u32;
        weight[p] = 0;
        degree[i] += 1;

        let p = degree[station_node] as usize;
        to[p] = i as u32;
        weight[p] = transfer_time[station] as u64;
        degree[station_node] += 1;
    }

    drop(degree);
    drop(seg_id_u);
    drop(seg_id_v);
    drop(seg_time);
    drop(incidences);

    const INF: u64 = u64::MAX / 2;

    let mut dist_time = vec![INF; node_count];
    let mut dist_boards = vec![0u32; node_count];
    let mut touched: Vec<u32> = Vec::with_capacity(node_count);

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for &(s, d) in &queries {
        for &node in &touched {
            dist_time[node as usize] = INF;
        }
        touched.clear();

        if s == d {
            writeln!(out, "0 0").unwrap();
            continue;
        }

        let source_node = k + s as usize;
        let target_node = k + d as usize;

        let mut heap = BinaryHeap::new();

        let lo = start[source_node] as usize;
        let hi = start[source_node + 1] as usize;

        for ei in lo..hi {
            let v = to[ei] as usize;

            if dist_time[v] == INF {
                dist_time[v] = 0;
                dist_boards[v] = 1;
                touched.push(v as u32);
                heap.push(Reverse((0u64, 1u32, v as u32)));
            }
        }

        let mut answer: Option<(u64, u32)> = None;

        while let Some(Reverse((current_time, current_boards, node))) = heap.pop() {
            let u = node as usize;

            if current_time != dist_time[u] || current_boards != dist_boards[u] {
                continue;
            }

            if u == target_node {
                answer = Some((current_time, current_boards));
                break;
            }

            let extra_board = if u >= k { 1u32 } else { 0u32 };

            let edge_lo = start[u] as usize;
            let edge_hi = start[u + 1] as usize;

            for ei in edge_lo..edge_hi {
                let v = to[ei] as usize;
                let next_time = current_time + weight[ei];
                let next_boards = current_boards + extra_board;

                if next_time < dist_time[v]
                    || (next_time == dist_time[v] && next_boards < dist_boards[v])
                {
                    if dist_time[v] == INF {
                        touched.push(v as u32);
                    }

                    dist_time[v] = next_time;
                    dist_boards[v] = next_boards;
                    heap.push(Reverse((next_time, next_boards, v as u32)));
                }
            }
        }

        match answer {
            Some((time, boards)) => writeln!(out, "{} {}", time, boards).unwrap(),
            None => writeln!(out, "none").unwrap(),
        }
    }
}
