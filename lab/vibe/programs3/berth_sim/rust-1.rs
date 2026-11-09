use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

#[derive(Clone, Copy, Eq, PartialEq, Ord, PartialOrd)]
struct WaitItem {
    priority: u8,
    arrival: u32,
    id: u32,
    pos: u32,
}

struct Ship {
    start: u64,
    id: u32,
    arrival: u32,
    cargo: u32,
    operator: u32,
    berth: u16,
    size: u8,
    priority: u8,
}

struct Scanner<R: Read> {
    reader: R,
    buf: Vec<u8>,
    pos: usize,
    len: usize,
}

impl<R: Read> Scanner<R> {
    fn new(reader: R) -> Self {
        Self {
            reader,
            buf: vec![0u8; 1 << 20],
            pos: 0,
            len: 0,
        }
    }

    #[inline]
    fn fill(&mut self) {
        self.len = self.reader.read(&mut self.buf).unwrap_or(0);
        self.pos = 0;
    }

    #[inline]
    fn next_u64(&mut self) -> u64 {
        loop {
            if self.pos >= self.len {
                self.fill();
                if self.pos >= self.len {
                    return 0;
                }
            }
            let b = self.buf[self.pos];
            if b.is_ascii_whitespace() {
                self.pos += 1;
            } else {
                break;
            }
        }

        let mut n = 0u64;
        loop {
            if self.pos >= self.len {
                self.fill();
                if self.pos >= self.len {
                    break;
                }
            }
            let b = self.buf[self.pos];
            if b.is_ascii_whitespace() {
                self.pos += 1;
                break;
            }
            n = n * 10 + (b - b'0') as u64;
            self.pos += 1;
        }
        n
    }
}

fn main() {
    let stdin = io::stdin();
    let mut sc = Scanner::new(stdin.lock());

    let b_count = sc.next_u64() as usize;
    let s_count = sc.next_u64() as usize;

    let mut berth_class = vec![0u8; b_count];
    let mut berth_rate = vec![0u32; b_count];
    for b in 0..b_count {
        berth_class[b] = sc.next_u64() as u8;
        berth_rate[b] = sc.next_u64() as u32;
    }

    let mut ships = Vec::with_capacity(s_count);
    for _ in 0..s_count {
        let id = sc.next_u64() as u32;
        let arrival = sc.next_u64() as u32;
        let size = sc.next_u64() as u8;
        let cargo = sc.next_u64() as u32;
        let priority = sc.next_u64() as u8;
        let operator = sc.next_u64() as u32;
        ships.push(Ship {
            start: 0,
            id,
            arrival,
            cargo,
            operator,
            berth: 0,
            size,
            priority,
        });
    }

    ships.sort_unstable_by_key(|s| s.arrival);

    let mut free: [BinaryHeap<Reverse<usize>>; 3] = [
        BinaryHeap::new(),
        BinaryHeap::new(),
        BinaryHeap::new(),
    ];
    for b in 0..b_count {
        free[(berth_class[b] - 1) as usize].push(Reverse(b));
    }

    let mut last_op = vec![u32::MAX; b_count];
    let mut berth_ships = vec![0u64; b_count];
    let mut berth_busy = vec![0u64; b_count];

    let mut waiting: [BinaryHeap<Reverse<WaitItem>>; 3] = [
        BinaryHeap::new(),
        BinaryHeap::new(),
        BinaryHeap::new(),
    ];
    let mut departures: BinaryHeap<Reverse<(u64, u16)>> = BinaryHeap::new();

    let mut next = 0usize;
    let mut makespan = 0u64;
    let mut total_wait = 0u64;
    let mut max_wait = 0u64;
    let mut max_ship = u32::MAX;

    while next < s_count || !departures.is_empty() {
        let t_arr = if next < s_count {
            ships[next].arrival as u64
        } else {
            u64::MAX
        };
        let t_dep = departures.peek().map_or(u64::MAX, |r| r.0.0);
        let t = t_arr.min(t_dep);
        if t == u64::MAX {
            break;
        }

        while let Some(&Reverse((dt, b))) = departures.peek() {
            if dt != t {
                break;
            }
            departures.pop().unwrap();
            makespan = t;
            let b = b as usize;
            free[(berth_class[b] - 1) as usize].push(Reverse(b));
        }

        while next < s_count && ships[next].arrival as u64 == t {
            let s = &ships[next];
            waiting[(s.size - 1) as usize].push(Reverse(WaitItem {
                priority: s.priority,
                arrival: s.arrival,
                id: s.id,
                pos: next as u32,
            }));
            next += 1;
        }

        for c in 0..3usize {
            loop {
                if free[c].is_empty() {
                    break;
                }

                let mut best: Option<WaitItem> = None;
                let mut best_z = 0usize;

                for z in 0..=c {
                    if let Some(&Reverse(item)) = waiting[z].peek() {
                        if best.map_or(true, |bk| item < bk) {
                            best = Some(item);
                            best_z = z;
                        }
                    }
                }

                let item = match best {
                    Some(it) => it,
                    None => break,
                };

                waiting[best_z].pop().unwrap();
                let b = free[c].pop().unwrap().0;
                let p = item.pos as usize;

                let cargo = ships[p].cargo as u64;
                let arrival = ships[p].arrival as u64;
                let operator = ships[p].operator;
                let id = ships[p].id;
                let rate = berth_rate[b] as u64;
                let setup = if last_op[b] == operator { 1u64 } else { 4u64 };
                let service = (cargo + rate - 1) / rate + setup;

                ships[p].start = t;
                ships[p].berth = b as u16;
                last_op[b] = operator;
                berth_ships[b] += 1;
                berth_busy[b] += service;

                let wait_time = t - arrival;
                total_wait += wait_time;
                if wait_time > max_wait
                    || (wait_time == max_wait && (max_ship == u32::MAX || id < max_ship))
                {
                    max_wait = wait_time;
                    max_ship = id;
                }

                departures.push(Reverse((t + service, b as u16)));
            }
        }
    }

    ships.sort_unstable_by_key(|s| s.id);

    let mut g = 0u64;
    for s in &ships {
        g = (g * 1_000_003 + s.start * 31 + s.berth as u64) % 1_000_000_007;
    }

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "ships {}", s_count).unwrap();
    writeln!(out, "makespan {}", makespan).unwrap();

    if s_count == 0 {
        writeln!(out, "wait total 0 max 0 ship -1").unwrap();
    } else {
        writeln!(
            out,
            "wait total {} max {} ship {}",
            total_wait, max_wait, max_ship
        )
        .unwrap();
    }

    for b in 0..b_count {
        writeln!(
            out,
            "berth {} ships {} busy {}",
            b, berth_ships[b], berth_busy[b]
        )
        .unwrap();
    }

    writeln!(out, "digest {}", g).unwrap();
}
