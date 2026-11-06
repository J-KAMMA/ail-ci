use std::cmp::Reverse;
use std::collections::{BTreeSet, BinaryHeap};
use std::io::{Read, Write};

#[derive(Clone, Copy)]
struct Ship {
    id: u32,
    arrival: u32,
    cargo: u32,
    operator: u32,
    priority: u8,
    size: u8,
}

struct FastScanner<R: Read> {
    reader: R,
    buf: Vec<u8>,
    pos: usize,
    len: usize,
}

impl<R: Read> FastScanner<R> {
    fn new(reader: R) -> Self {
        Self {
            reader,
            buf: vec![0u8; 1 << 16],
            pos: 0,
            len: 0,
        }
    }

    #[inline]
    fn next_u32(&mut self) -> u32 {
        loop {
            if self.pos == self.len {
                self.len = self.reader.read(&mut self.buf).unwrap_or(0);
                self.pos = 0;
                if self.len == 0 {
                    return 0;
                }
            }
            let c = self.buf[self.pos];
            if c > b' ' {
                break;
            }
            self.pos += 1;
        }

        let mut n = 0u32;
        loop {
            if self.pos == self.len {
                self.len = self.reader.read(&mut self.buf).unwrap_or(0);
                self.pos = 0;
                if self.len == 0 {
                    break;
                }
            }
            let c = self.buf[self.pos];
            if c <= b' ' {
                self.pos += 1;
                break;
            }
            n = n * 10 + (c - b'0') as u32;
            self.pos += 1;
        }
        n
    }
}

fn main() {
    let stdin = std::io::stdin();
    let mut sc = FastScanner::new(stdin.lock());

    let berth_count = sc.next_u32() as usize;
    let ship_count = sc.next_u32() as usize;

    let mut class = vec![0u8; berth_count];
    let mut rate = vec![0u64; berth_count];
    for i in 0..berth_count {
        class[i] = sc.next_u32() as u8;
        rate[i] = sc.next_u32() as u64;
    }

    let mut ships = Vec::with_capacity(ship_count);
    for _ in 0..ship_count {
        let id = sc.next_u32();
        let arrival = sc.next_u32();
        let size = sc.next_u32() as u8;
        let cargo = sc.next_u32();
        let priority = sc.next_u32() as u8;
        let operator = sc.next_u32();
        ships.push(Ship {
            id,
            arrival,
            cargo,
            operator,
            priority,
            size,
        });
    }

    ships.sort_unstable_by_key(|s| s.id);

    let mut order: Vec<u32> = (0..ship_count as u32).collect();
    order.sort_unstable_by_key(|&i| ships[i as usize].arrival);

    let mut free: [BTreeSet<u16>; 3] = [BTreeSet::new(), BTreeSet::new(), BTreeSet::new()];
    for i in 0..berth_count {
        free[(class[i] - 1) as usize].insert(i as u16);
    }

    let mut waiting: [BinaryHeap<Reverse<(u8, u32, u32, u32)>>; 3] =
        [BinaryHeap::new(), BinaryHeap::new(), BinaryHeap::new()];
    let mut departures: BinaryHeap<Reverse<(u64, u16)>> = BinaryHeap::new();

    let mut last_operator: Vec<Option<u32>> = vec![None; berth_count];
    let mut served: Vec<u64> = vec![0; berth_count];
    let mut busy: Vec<u64> = vec![0; berth_count];

    let mut start = vec![0u64; ship_count];
    let mut berth_of = vec![0u16; ship_count];

    let mut next_arrival = 0usize;
    let mut makespan = 0u64;
    let mut total_wait = 0u64;
    let mut max_wait = 0u64;
    let mut max_wait_id = u32::MAX;

    while next_arrival < ship_count || !departures.is_empty() {
        let t = if next_arrival < ship_count {
            let arrival_time = ships[order[next_arrival] as usize].arrival as u64;
            if let Some(&Reverse((dep_time, _))) = departures.peek() {
                if dep_time < arrival_time {
                    dep_time
                } else {
                    arrival_time
                }
            } else {
                arrival_time
            }
        } else {
            match departures.peek() {
                Some(&Reverse((dep_time, _))) => dep_time,
                None => break,
            }
        };

        while let Some(&Reverse((dep_time, berth))) = departures.peek() {
            if dep_time != t {
                break;
            }
            departures.pop();
            free[(class[berth as usize] - 1) as usize].insert(berth);
        }

        while next_arrival < ship_count {
            let idx = order[next_arrival] as usize;
            let ship = &ships[idx];
            if ship.arrival as u64 != t {
                break;
            }
            let item = (ship.priority, ship.arrival, ship.id, idx as u32);
            waiting[(ship.size - 1) as usize].push(Reverse(item));
            next_arrival += 1;
        }

        for c in 1u8..=3 {
            let ci = (c - 1) as usize;
            loop {
                if free[ci].is_empty() {
                    break;
                }

                let mut best: Option<(usize, (u8, u32, u32, u32))> = None;
                for size in 1u8..=c {
                    let si = (size - 1) as usize;
                    if let Some(&Reverse(item)) = waiting[si].peek() {
                        let take = match best {
                            None => true,
                            Some((_, current)) => item < current,
                        };
                        if take {
                            best = Some((si, item));
                        }
                    }
                }

                let (si, item) = match best {
                    Some(value) => value,
                    None => break,
                };

                waiting[si].pop();

                let berth = *free[ci].iter().next().unwrap();
                free[ci].remove(&berth);

                let idx = item.3 as usize;
                let ship = &ships[idx];
                let rate_b = rate[berth as usize];

                let setup = match last_operator[berth as usize] {
                    Some(op) if op == ship.operator => 1,
                    _ => 4,
                };
                let service = (ship.cargo as u64 + rate_b - 1) / rate_b + setup;
                let departure_time = t + service;

                last_operator[berth as usize] = Some(ship.operator);
                served[berth as usize] += 1;
                busy[berth as usize] += service;
                start[idx] = t;
                berth_of[idx] = berth;
                departures.push(Reverse((departure_time, berth)));

                if departure_time > makespan {
                    makespan = departure_time;
                }

                let wait = t - ship.arrival as u64;
                total_wait += wait;
                if wait > max_wait || (wait == max_wait && ship.id < max_wait_id) {
                    max_wait = wait;
                    max_wait_id = ship.id;
                }
            }
        }
    }

    let stdout = std::io::stdout();
    let mut out = std::io::BufWriter::new(stdout.lock());

    writeln!(out, "ships {}", ship_count).unwrap();
    writeln!(out, "makespan {}", makespan).unwrap();
    if ship_count == 0 {
        writeln!(out, "wait total 0 max 0 ship -1").unwrap();
    } else {
        writeln!(
            out,
            "wait total {} max {} ship {}",
            total_wait, max_wait, max_wait_id
        )
        .unwrap();
    }

    for i in 0..berth_count {
        writeln!(out, "berth {} ships {} busy {}", i, served[i], busy[i]).unwrap();
    }

    let mut digest = 0u64;
    for idx in 0..ship_count {
        digest = (digest * 1_000_003 + start[idx] * 31 + berth_of[idx] as u64)
            % 1_000_000_007;
    }
    writeln!(out, "digest {}", digest).unwrap();
}
