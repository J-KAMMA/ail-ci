use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::{self, BufRead, Write};

#[derive(Clone, Copy)]
struct Ship {
    id: u32,
    arrival: u32,
    cargo: u32,
    operator: u32,
    priority: u8,
    size: u8,
}

struct FastScanner<R: BufRead> {
    reader: R,
    buf: Vec<u8>,
    head: usize,
    tail: usize,
}

impl<R: BufRead> FastScanner<R> {
    fn new(reader: R) -> Self {
        FastScanner {
            reader,
            buf: vec![0u8; 1 << 16],
            head: 0,
            tail: 0,
        }
    }

    #[inline(always)]
    fn read_byte(&mut self) -> Option<u8> {
        if self.head >= self.tail {
            self.tail = self.reader.read(&mut self.buf).ok()?;
            self.head = 0;
            if self.tail == 0 {
                return None;
            }
        }
        let b = self.buf[self.head];
        self.head += 1;
        Some(b)
    }

    #[inline]
    fn next_u64(&mut self) -> Option<u64> {
        let mut c = self.read_byte();
        while let Some(b) = c {
            if b > b' ' {
                break;
            }
            c = self.read_byte();
        }

        let mut b = c?;
        let mut n: u64 = 0;

        loop {
            if b >= b'0' && b <= b'9' {
                n = n * 10 + (b - b'0') as u64;
            } else {
                break;
            }

            match self.read_byte() {
                Some(nb) => b = nb,
                None => break,
            }
        }

        Some(n)
    }
}

#[inline]
fn ship_less(ships: &[Ship], a: u32, b: u32) -> bool {
    let x = &ships[a as usize];
    let y = &ships[b as usize];
    (x.priority, x.arrival, x.id) < (y.priority, y.arrival, y.id)
}

#[inline]
fn heap_push(heap: &mut Vec<u32>, ships: &[Ship], idx: u32) {
    heap.push(idx);
    let mut i = heap.len() - 1;

    while i > 0 {
        let parent = (i - 1) >> 1;
        if ship_less(ships, heap[i], heap[parent]) {
            heap.swap(i, parent);
            i = parent;
        } else {
            break;
        }
    }
}

#[inline]
fn heap_pop(heap: &mut Vec<u32>, ships: &[Ship]) -> u32 {
    let n = heap.len();
    let result = heap[0];
    let last = heap.pop().unwrap();

    if n > 1 {
        heap[0] = last;
        let len = heap.len();
        let mut i = 0;

        loop {
            let left = 2 * i + 1;
            if left >= len {
                break;
            }

            let right = left + 1;
            let mut smallest = left;

            if right < len && ship_less(ships, heap[right], heap[left]) {
                smallest = right;
            }

            if ship_less(ships, heap[smallest], heap[i]) {
                heap.swap(i, smallest);
                i = smallest;
            } else {
                break;
            }
        }
    }

    result
}

fn main() {
    let stdin = io::stdin();
    let mut scanner = FastScanner::new(stdin.lock());

    let bcnt = scanner.next_u64().unwrap() as usize;
    let scount = scanner.next_u64().unwrap() as usize;

    let mut classes: Vec<u8> = Vec::with_capacity(bcnt);
    let mut rates: Vec<u32> = Vec::with_capacity(bcnt);

    let mut free: [BinaryHeap<Reverse<u16>>; 3] = [
        BinaryHeap::new(),
        BinaryHeap::new(),
        BinaryHeap::new(),
    ];

    for i in 0..bcnt {
        let class = scanner.next_u64().unwrap() as u8;
        let rate = scanner.next_u64().unwrap() as u32;

        classes.push(class);
        rates.push(rate);
        free[(class - 1) as usize].push(Reverse(i as u16));
    }

    let mut ships: Vec<Ship> = Vec::with_capacity(scount);
    let mut arrivals: Vec<(u32, u32)> = Vec::with_capacity(scount);

    for i in 0..scount {
        let id = scanner.next_u64().unwrap() as u32;
        let arrival = scanner.next_u64().unwrap() as u32;
        let size = scanner.next_u64().unwrap() as u8;
        let cargo = scanner.next_u64().unwrap() as u32;
        let priority = scanner.next_u64().unwrap() as u8;
        let operator = scanner.next_u64().unwrap() as u32;

        ships.push(Ship {
            id,
            arrival,
            cargo,
            operator,
            priority,
            size,
        });

        arrivals.push((arrival, i as u32));
    }

    arrivals.sort_unstable_by_key(|x| x.0);

    let mut start = vec![0u64; scount];
    let mut ship_berth = vec![0u16; scount];

    let mut waiting: [Vec<u32>; 3] = [Vec::new(), Vec::new(), Vec::new()];
    let mut departures: BinaryHeap<Reverse<(u64, u16)>> = BinaryHeap::new();

    let mut prev_operator: Vec<i64> = vec![-1; bcnt];
    let mut berth_ships: Vec<u32> = vec![0; bcnt];
    let mut berth_busy: Vec<u64> = vec![0; bcnt];

    let mut wait_total: u64 = 0;
    let mut max_wait: u64 = 0;
    let mut max_wait_id: u64 = u64::MAX;
    let mut makespan: u64 = 0;

    let mut ap: usize = 0;

    while ap < scount || !departures.is_empty() {
        let next_arrival = if ap < scount {
            arrivals[ap].0 as u64
        } else {
            u64::MAX
        };

        let next_departure = match departures.peek() {
            Some(top) => top.0 .0,
            None => u64::MAX,
        };

        let t = if next_arrival < next_departure {
            next_arrival
        } else {
            next_departure
        };

        loop {
            let dt = match departures.peek() {
                Some(top) => top.0 .0,
                None => break,
            };

            if dt != t {
                break;
            }

            let Reverse((_, b16)) = departures.pop().unwrap();
            let b = b16 as usize;
            free[classes[b] as usize - 1].push(Reverse(b16));
        }

        while ap < scount && arrivals[ap].0 as u64 == t {
            let idx = arrivals[ap].1;
            let size = ships[idx as usize].size as usize;
            heap_push(&mut waiting[size - 1], &ships, idx);
            ap += 1;
        }

        for c in 1..=3usize {
            loop {
                if free[c - 1].is_empty() {
                    break;
                }

                let mut best_size: Option<usize> = None;

                for s in 0..c {
                    if let Some(&idx) = waiting[s].first() {
                        match best_size {
                            None => best_size = Some(s),
                            Some(bs) => {
                                if ship_less(&ships, idx, waiting[bs][0]) {
                                    best_size = Some(s);
                                }
                            }
                        }
                    }
                }

                let s = match best_size {
                    Some(s) => s,
                    None => break,
                };

                let idx = heap_pop(&mut waiting[s], &ships);
                let Reverse(b16) = free[c - 1].pop().unwrap();
                let b = b16 as usize;

                let sh = &ships[idx as usize];

                start[idx as usize] = t;
                ship_berth[idx as usize] = b16;

                let prev = prev_operator[b];
                let setup: u32 = if prev == sh.operator as i64 { 1 } else { 4 };
                prev_operator[b] = sh.operator as i64;

                let service = (sh.cargo + rates[b] - 1) / rates[b] + setup;

                berth_ships[b] += 1;
                berth_busy[b] += service as u64;

                let dep_time = t + service as u64;
                if dep_time > makespan {
                    makespan = dep_time;
                }

                departures.push(Reverse((dep_time, b16)));

                let w = t - sh.arrival as u64;
                wait_total += w;

                if w > max_wait || (w == max_wait && (sh.id as u64) < max_wait_id) {
                    max_wait = w;
                    max_wait_id = sh.id as u64;
                }
            }
        }
    }

    for (i, sh) in ships.iter().enumerate() {
        arrivals[i] = (sh.id, i as u32);
    }
    arrivals.sort_unstable_by_key(|x| x.0);

    let mut digest: u64 = 0;
    for &(_, idx) in arrivals.iter() {
        let i = idx as usize;
        digest = (digest * 1_000_003 + start[i] * 31 + ship_berth[i] as u64) % 1_000_000_007;
    }

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "ships {}", scount).unwrap();
    writeln!(out, "makespan {}", makespan).unwrap();

    if scount == 0 {
        writeln!(out, "wait total 0 max 0 ship -1").unwrap();
    } else {
        writeln!(
            out,
            "wait total {} max {} ship {}",
            wait_total, max_wait, max_wait_id
        )
        .unwrap();
    }

    for b in 0..bcnt {
        writeln!(
            out,
            "berth {} ships {} busy {}",
            b, berth_ships[b], berth_busy[b]
        )
        .unwrap();
    }

    writeln!(out, "digest {}", digest).unwrap();
}
