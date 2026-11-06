use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, Read, Write};

#[derive(Clone, Copy)]
struct Ship {
    id: u32,
    arrival: u32,
    cargo: u32,
    operator: u32,
    start: u64,
    berth: u16,
    size: u8,
    priority: u8,
}

struct Berth {
    class: u8,
    rate: u32,
    last_op: u32,
    ships: u64,
    busy: u64,
}

struct FastReader<R: Read> {
    inner: R,
    buf: Box<[u8]>,
    pos: usize,
    len: usize,
}

impl<R: Read> FastReader<R> {
    fn new(inner: R) -> Self {
        Self {
            inner,
            buf: vec![0u8; 1 << 16].into_boxed_slice(),
            pos: 0,
            len: 0,
        }
    }

    #[inline]
    fn next_u64(&mut self) -> u64 {
        loop {
            if self.pos == self.len {
                self.len = match self.inner.read(&mut self.buf) {
                    Ok(0) | Err(_) => return 0,
                    Ok(n) => n,
                };
                self.pos = 0;
            }
            if self.buf[self.pos] > b' ' {
                break;
            }
            self.pos += 1;
        }

        let mut num = 0u64;
        loop {
            if self.pos == self.len {
                self.len = match self.inner.read(&mut self.buf) {
                    Ok(0) | Err(_) => return num,
                    Ok(n) => n,
                };
                self.pos = 0;
            }

            let b = self.buf[self.pos];
            if b <= b' ' {
                self.pos += 1;
                return num;
            }

            num = num * 10 + (b - b'0') as u64;
            self.pos += 1;
        }
    }
}

fn main() {
    let stdin = io::stdin();
    let mut input = FastReader::new(stdin.lock());

    let b_count = input.next_u64() as usize;
    let s_count = input.next_u64() as usize;

    let mut berths = Vec::with_capacity(b_count);
    for _ in 0..b_count {
        let class = input.next_u64() as u8;
        let rate = input.next_u64() as u32;
        berths.push(Berth {
            class,
            rate,
            last_op: u32::MAX,
            ships: 0,
            busy: 0,
        });
    }

    let mut ships = Vec::with_capacity(s_count);
    for _ in 0..s_count {
        let id = input.next_u64() as u32;
        let arrival = input.next_u64() as u32;
        let size = input.next_u64() as u8;
        let cargo = input.next_u64() as u32;
        let priority = input.next_u64() as u8;
        let operator = input.next_u64() as u32;

        ships.push(Ship {
            id,
            arrival,
            cargo,
            operator,
            start: 0,
            berth: 0,
            size,
            priority,
        });
    }

    ships.sort_unstable_by_key(|s| s.arrival);

    let mut free: Vec<BinaryHeap<Reverse<u16>>> =
        (0..4).map(|_| BinaryHeap::new()).collect();

    for (i, berth) in berths.iter().enumerate() {
        free[berth.class as usize].push(Reverse(i as u16));
    }

    let mut waiting: Vec<BinaryHeap<Reverse<(u8, u32, u32, u32)>>> =
        (0..3).map(|_| BinaryHeap::new()).collect();

    let mut departures: BinaryHeap<Reverse<(u64, u16)>> = BinaryHeap::new();

    let mut arrival_index = 0usize;
    let mut makespan = 0u64;
    let mut wait_total = 0u64;
    let mut wait_max = 0u64;
    let mut wait_max_id = u32::MAX;

    while arrival_index < s_count || !departures.is_empty() {
        let next_arrival = if arrival_index < s_count {
            ships[arrival_index].arrival as u64
        } else {
            u64::MAX
        };

        let next_departure = departures
            .peek()
            .map(|x| x.0 .0)
            .unwrap_or(u64::MAX);

        let t = next_arrival.min(next_departure);

        while let Some(&Reverse((finish, berth))) = departures.peek() {
            if finish != t {
                break;
            }
            departures.pop();
            let class = berths[berth as usize].class as usize;
            free[class].push(Reverse(berth));
        }

        while arrival_index < s_count && ships[arrival_index].arrival as u64 == t {
            let idx = arrival_index;
            let ship = ships[idx];
            waiting[(ship.size - 1) as usize].push(Reverse((
                ship.priority,
                ship.arrival,
                ship.id,
                idx as u32,
            )));
            arrival_index += 1;
        }

        for class in 1..=3usize {
            loop {
                let berth = match free[class].peek() {
                    Some(&Reverse(b)) => b,
                    None => break,
                };

                let mut best: Option<(u8, u32, u32, u32, usize)> = None;

                for size in 1..=class {
                    if let Some(&Reverse((priority, arrival, id, idx))) =
                        waiting[size - 1].peek()
                    {
                        let better = match best {
                            None => true,
                            Some((bp, ba, bid, _, _)) => {
                                (priority, arrival, id) < (bp, ba, bid)
                            }
                        };

                        if better {
                            best = Some((priority, arrival, id, idx, size));
                        }
                    }
                }

                let (_, _, _, idx, size) = match best {
                    Some(value) => value,
                    None => break,
                };

                waiting[size - 1].pop();
                free[class].pop();

                let berth_index = berth as usize;
                let rate = berths[berth_index].rate as u64;
                let previous_operator = berths[berth_index].last_op;

                let ship = &mut ships[idx as usize];
                let setup = if previous_operator == ship.operator {
                    1u64
                } else {
                    4u64
                };

                let service = (ship.cargo as u64 + rate - 1) / rate + setup;
                let start = t;
                ship.start = start;
                ship.berth = berth;

                let finish = start + service;
                berths[berth_index].last_op = ship.operator;
                berths[berth_index].ships += 1;
                berths[berth_index].busy += service;

                departures.push(Reverse((finish, berth)));

                if finish > makespan {
                    makespan = finish;
                }

                let wait = start - ship.arrival as u64;
                wait_total += wait;

                if wait > wait_max || (wait == wait_max && ship.id < wait_max_id) {
                    wait_max = wait;
                    wait_max_id = ship.id;
                }
            }
        }
    }

    ships.sort_unstable_by_key(|s| s.id);

    const MOD: u64 = 1_000_000_007;
    let mut digest = 0u64;
    for ship in &ships {
        digest = (digest * 1_000_003 + ship.start * 31 + ship.berth as u64) % MOD;
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
            wait_total, wait_max, wait_max_id
        )
        .unwrap();
    }

    for (i, berth) in berths.iter().enumerate() {
        writeln!(
            out,
            "berth {} ships {} busy {}",
            i, berth.ships, berth.busy
        )
        .unwrap();
    }

    writeln!(out, "digest {}", digest).unwrap();
}
