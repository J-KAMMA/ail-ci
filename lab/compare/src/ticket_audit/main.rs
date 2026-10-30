use std::collections::{BTreeMap, HashSet};
use std::process::exit;

fn fail(n: usize, cat: &str, code: i32) -> ! {
    println!("line {}: {}", n, cat);
    exit(code)
}

fn all_digits(s: &[u8]) -> bool {
    s.iter().all(|c| c.is_ascii_digit())
}

fn dig(s: &[u8], lo: usize, hi: usize) -> bool {
    s.len() >= lo && s.len() <= hi && all_digits(s)
}

fn s_code(s: &[u8]) -> bool {
    s.len() == 3 && s.iter().all(|c| c.is_ascii_uppercase())
}
fn s_name(s: &[u8]) -> bool {
    s.len() >= 1
        && s.len() <= 40
        && s.iter().all(|&c| (0x20..=0x7E).contains(&c) && c != b'|')
        && s[0] != b' '
        && s[s.len() - 1] != b' '
}
fn s_event(s: &[u8]) -> bool {
    s.len() == 6 && all_digits(s)
}
fn s_date(s: &[u8]) -> bool {
    s.len() == 10
        && all_digits(&s[0..4])
        && s[4] == b'-'
        && all_digits(&s[5..7])
        && s[7] == b'-'
        && all_digits(&s[8..10])
}
fn s_time(s: &[u8]) -> bool {
    s.len() == 5 && all_digits(&s[0..2]) && s[2] == b':' && all_digits(&s[3..5])
}
fn s_price(s: &[u8]) -> bool {
    if s.len() < 4 || s.len() > 7 {
        return false;
    }
    let p = s.len() - 3;
    all_digits(&s[..p]) && s[p] == b'.' && all_digits(&s[p + 1..])
}
fn s_seat(s: &[u8]) -> bool {
    s.len() >= 2 && s.len() <= 4 && s[0].is_ascii_uppercase() && all_digits(&s[1..])
}
fn s_buyer(s: &[u8]) -> bool {
    s.len() >= 4
        && s.len() <= 12
        && s[0].is_ascii_lowercase()
        && s.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
}

fn num(s: &[u8]) -> u64 {
    s.iter().fold(0u64, |a, &c| a * 10 + (c - b'0') as u64)
}

fn v_cap(s: &[u8]) -> bool {
    if s[0] == b'0' {
        return false;
    }
    let n = num(s);
    n >= 1 && n <= 100000
}
fn v_event(s: &[u8]) -> bool {
    let d: Vec<u64> = s.iter().map(|c| (c - b'0') as u64).collect();
    (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0
}
fn v_date(s: &[u8]) -> bool {
    let y = num(&s[0..4]);
    let m = num(&s[5..7]);
    let d = num(&s[8..10]);
    if y < 2000 || y > 2099 || m < 1 || m > 12 || d < 1 {
        return false;
    }
    let last = match m {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        _ => {
            if y % 4 == 0 {
                29
            } else {
                28
            }
        }
    };
    d <= last
}
fn v_time(s: &[u8]) -> bool {
    num(&s[0..2]) <= 23 && num(&s[3..5]) <= 59
}
fn price_cents(s: &[u8]) -> u64 {
    let p = s.len() - 3;
    num(&s[..p]) * 100 + num(&s[p + 1..])
}
fn v_price(s: &[u8]) -> bool {
    let p = s.len() - 3;
    if p > 1 && s[0] == b'0' {
        return false;
    }
    price_cents(s) % 5 == 0
}
fn v_seat(s: &[u8]) -> bool {
    s[1] != b'0'
}
fn v_nolead(s: &[u8]) -> bool {
    s.len() == 1 || s[0] != b'0'
}

fn money(c: u64) -> String {
    format!("{}.{:02}", c / 100, c % 100)
}

struct Venue {
    cap: u64,
}
struct Event {
    venue: Vec<u8>,
    price: u64,
    sold: HashSet<Vec<u8>>,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };
    let mut lines: Vec<&[u8]> = data.split(|&c| c == b'\n').collect();
    if data.is_empty() || data[data.len() - 1] == b'\n' {
        lines.pop();
    }
    if lines.is_empty() || lines[0] != b"TKT/1" {
        fail(1, "header", 2);
    }
    let mut venues: BTreeMap<Vec<u8>, Venue> = BTreeMap::new();
    let mut events: BTreeMap<Vec<u8>, Event> = BTreeMap::new();
    let (mut ns, mut nr, mut count) = (0u64, 0u64, 0u64);
    let mut revenue: u64 = 0;
    let mut ended = false;
    for (i, line) in lines.iter().enumerate().skip(1) {
        let n = i + 1;
        if ended {
            fail(n, "summary", 8);
        }
        let f: Vec<&[u8]> = line.split(|&c| c == b'|').collect();
        let t = f[0];
        match (t, f.len()) {
            (b"V", 4) => {
                if !(s_code(f[1]) && s_name(f[2]) && dig(f[3], 1, 6)) {
                    fail(n, "syntax", 3);
                }
                if !v_cap(f[3]) {
                    fail(n, "value", 4);
                }
                if venues.contains_key(f[1]) {
                    fail(n, "duplicate", 6);
                }
                venues.insert(f[1].to_vec(), Venue { cap: num(f[3]) });
                count += 1;
            }
            (b"E", 6) => {
                if !(s_event(f[1]) && s_code(f[2]) && s_date(f[3]) && s_time(f[4]) && s_price(f[5])) {
                    fail(n, "syntax", 3);
                }
                if !(v_event(f[1]) && v_date(f[3]) && v_time(f[4]) && v_price(f[5])) {
                    fail(n, "value", 4);
                }
                if !venues.contains_key(f[2]) {
                    fail(n, "reference", 5);
                }
                if events.contains_key(f[1]) {
                    fail(n, "duplicate", 6);
                }
                events.insert(
                    f[1].to_vec(),
                    Event { venue: f[2].to_vec(), price: price_cents(f[5]), sold: HashSet::new() },
                );
                count += 1;
            }
            (b"S", 4) => {
                if !(s_event(f[1]) && s_seat(f[2]) && s_buyer(f[3])) {
                    fail(n, "syntax", 3);
                }
                if !(v_event(f[1]) && v_seat(f[2])) {
                    fail(n, "value", 4);
                }
                let ev = match events.get_mut(f[1]) {
                    Some(e) => e,
                    None => fail(n, "reference", 5),
                };
                if ev.sold.contains(f[2]) {
                    fail(n, "duplicate", 6);
                }
                if ev.sold.len() as u64 >= venues[&ev.venue].cap {
                    fail(n, "capacity", 7);
                }
                ev.sold.insert(f[2].to_vec());
                revenue += ev.price;
                ns += 1;
                count += 1;
            }
            (b"R", 3) => {
                if !(s_event(f[1]) && s_seat(f[2])) {
                    fail(n, "syntax", 3);
                }
                if !(v_event(f[1]) && v_seat(f[2])) {
                    fail(n, "value", 4);
                }
                let ev = match events.get_mut(f[1]) {
                    Some(e) => e,
                    None => fail(n, "reference", 5),
                };
                if !ev.sold.remove(f[2]) {
                    fail(n, "reference", 5);
                }
                revenue -= ev.price;
                nr += 1;
                count += 1;
            }
            (b"END", 3) => {
                if !(dig(f[1], 1, 9) && dig(f[2], 1, 12)) {
                    fail(n, "syntax", 3);
                }
                if !(v_nolead(f[1]) && v_nolead(f[2])) {
                    fail(n, "value", 4);
                }
                if num(f[1]) != count || num(f[2]) != revenue {
                    fail(n, "summary", 8);
                }
                ended = true;
            }
            _ => fail(n, "syntax", 3),
        }
    }
    if !ended {
        fail(lines.len() + 1, "summary", 8);
    }
    let mut out = String::new();
    out += &format!("venues {} events {} sold {} refunds {}\n", venues.len(), events.len(), ns, nr);
    out += &format!("revenue {}\n", money(revenue));
    for (code, _) in &venues {
        let (mut ne, mut t, mut r) = (0u64, 0u64, 0u64);
        for e in events.values() {
            if &e.venue == code {
                ne += 1;
                t += e.sold.len() as u64;
                r += e.sold.len() as u64 * e.price;
            }
        }
        out += &format!("{} events={} tickets={} revenue={}\n", String::from_utf8_lossy(code), ne, t, money(r));
    }
    let mut v: Vec<(&Vec<u8>, usize)> = events.iter().map(|(k, e)| (k, e.sold.len())).collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    for (k, c) in v.iter().take(3) {
        out += &format!("top {} {}\n", String::from_utf8_lossy(k), c);
    }
    print!("{}", out);
}
