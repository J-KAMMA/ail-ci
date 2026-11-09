use std::collections::{BTreeMap, HashMap, HashSet};
use std::env;
use std::fs;
use std::io::{self, Write};
use std::process;

struct Event {
    venue: [u8; 3],
    price: u64,
    sold: HashSet<u64>,
}

fn fail(line: usize, cat: &str) -> ! {
    println!("line {}: {}", line, cat);
    let _ = io::stdout().flush();
    let code = match cat {
        "header" => 2,
        "syntax" => 3,
        "value" => 4,
        "reference" => 5,
        "duplicate" => 6,
        "capacity" => 7,
        _ => 8,
    };
    process::exit(code);
}

fn digits(b: &[u8]) -> bool {
    !b.is_empty() && b.iter().all(|c| c.is_ascii_digit())
}

fn digits_val(b: &[u8]) -> Option<u64> {
    if !digits(b) {
        return None;
    }
    Some(b.iter().fold(0u64, |a, &c| a * 10 + (c - b'0') as u64))
}

// digits, length in range, no leading zero at all
fn plain_num(b: &[u8], min: usize, max: usize) -> Option<u64> {
    if b.len() < min || b.len() > max || !digits(b) || b[0] == b'0' {
        return None;
    }
    digits_val(b)
}

// digits, length in range, no leading zero unless exactly "0"
fn count_num(b: &[u8], min: usize, max: usize) -> Option<u64> {
    if b.len() < min || b.len() > max || !digits(b) {
        return None;
    }
    if b.len() > 1 && b[0] == b'0' {
        return None;
    }
    digits_val(b)
}

fn code_of(b: &[u8]) -> Option<[u8; 3]> {
    if b.len() == 3 && b.iter().all(|c| c.is_ascii_uppercase()) {
        Some([b[0], b[1], b[2]])
    } else {
        None
    }
}

fn name_ok(b: &[u8]) -> bool {
    if b.is_empty() || b.len() > 40 {
        return false;
    }
    if !b.iter().all(|&c| (0x20..=0x7E).contains(&c) && c != b'|') {
        return false;
    }
    b[0] != b' ' && b[b.len() - 1] != b' '
}

fn buyer_ok(b: &[u8]) -> bool {
    b.len() >= 4
        && b.len() <= 12
        && b[0].is_ascii_lowercase()
        && b.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
}

fn parse_event(b: &[u8]) -> Option<u64> {
    if b.len() != 6 {
        return None;
    }
    digits_val(b)
}

fn event_ok(n: u64) -> bool {
    let d = [
        n / 100000,
        n / 10000 % 10,
        n / 1000 % 10,
        n / 100 % 10,
        n / 10 % 10,
        n % 10,
    ];
    (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0
}

fn parse_date(b: &[u8]) -> Option<(u64, u64, u64)> {
    if b.len() != 10 || b[4] != b'-' || b[7] != b'-' {
        return None;
    }
    let y = digits_val(&b[0..4])?;
    let m = digits_val(&b[5..7])?;
    let d = digits_val(&b[8..10])?;
    Some((y, m, d))
}

fn date_ok(date: (u64, u64, u64)) -> bool {
    let (y, m, d) = date;
    if !(2000..=2099).contains(&y) || !(1..=12).contains(&m) {
        return false;
    }
    let dim = match m {
        2 => {
            if y % 4 == 0 {
                29
            } else {
                28
            }
        }
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    };
    d >= 1 && d <= dim
}

fn parse_time(b: &[u8]) -> Option<(u64, u64)> {
    if b.len() != 5 || b[2] != b':' {
        return None;
    }
    let h = digits_val(&b[0..2])?;
    let m = digits_val(&b[3..5])?;
    Some((h, m))
}

fn time_ok(t: (u64, u64)) -> bool {
    t.0 <= 23 && t.1 <= 59
}

fn parse_price(b: &[u8]) -> Option<u64> {
    let dot = b.iter().position(|&c| c == b'.')?;
    let ip = &b[..dot];
    let fp = &b[dot + 1..];
    if ip.is_empty() || ip.len() > 4 || !digits(ip) {
        return None;
    }
    if ip.len() > 1 && ip[0] == b'0' {
        return None;
    }
    if fp.len() != 2 || !digits(fp) {
        return None;
    }
    let w = digits_val(ip)?;
    let f = digits_val(fp)?;
    Some(w * 100 + f)
}

fn parse_seat(b: &[u8]) -> Option<u64> {
    if b.len() < 2 || b.len() > 4 || !b[0].is_ascii_uppercase() {
        return None;
    }
    let n = plain_num(&b[1..], 1, 3)?;
    Some((b[0] - b'A') as u64 * 1000 + n)
}

fn money(x: u64) -> String {
    format!("{}.{:02}", x / 100, x % 100)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let data = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => process::exit(1),
    };

    let lines: Vec<&[u8]> = if data.is_empty() {
        Vec::new()
    } else {
        let mut v: Vec<&[u8]> = data.split(|&c| c == b'\n').collect();
        if data[data.len() - 1] == b'\n' {
            v.pop();
        }
        v
    };

    if lines.is_empty() || lines[0] != &b"TKT/1"[..] {
        fail(1, "header");
    }

    let mut venues: BTreeMap<[u8; 3], u64> = BTreeMap::new();
    let mut events: HashMap<u64, Event> = HashMap::new();
    let mut revenue: u64 = 0;
    let mut recs: u64 = 0;
    let mut sold_n: u64 = 0;
    let mut refund_n: u64 = 0;
    let mut ended = false;

    for idx in 1..lines.len() {
        let ln = idx + 1;
        let line = lines[idx];
        if ended {
            fail(ln, "summary");
        }
        let f: Vec<&[u8]> = line.split(|&c| c == b'|').collect();
        let t = std::str::from_utf8(f[0]).unwrap_or("");
        match (t, f.len()) {
            ("V", 4) => {
                let code = code_of(f[1]);
                let cap = plain_num(f[3], 1, 6);
                let name_good = name_ok(f[2]);
                let (code, cap) = match (code, cap) {
                    (Some(c), Some(p)) if name_good => (c, p),
                    _ => fail(ln, "syntax"),
                };
                if cap < 1 || cap > 100000 {
                    fail(ln, "value");
                }
                if venues.contains_key(&code) {
                    fail(ln, "duplicate");
                }
                venues.insert(code, cap);
                recs += 1;
            }
            ("E", 6) => {
                let ev = parse_event(f[1]);
                let vc = code_of(f[2]);
                let date = parse_date(f[3]);
                let time = parse_time(f[4]);
                let price = parse_price(f[5]);
                let (ev, vc, date, time, price) = match (ev, vc, date, time, price) {
                    (Some(a), Some(b), Some(c), Some(d), Some(e)) => (a, b, c, d, e),
                    _ => fail(ln, "syntax"),
                };
                if !event_ok(ev) || !date_ok(date) || !time_ok(time) || price % 5 != 0 {
                    fail(ln, "value");
                }
                if !venues.contains_key(&vc) {
                    fail(ln, "reference");
                }
                if events.contains_key(&ev) {
                    fail(ln, "duplicate");
                }
                events.insert(
                    ev,
                    Event {
                        venue: vc,
                        price,
                        sold: HashSet::new(),
                    },
                );
                recs += 1;
            }
            ("S", 4) => {
                let ev = parse_event(f[1]);
                let seat = parse_seat(f[2]);
                let buyer = buyer_ok(f[3]);
                let (ev, seat) = match (ev, seat) {
                    (Some(a), Some(b)) if buyer => (a, b),
                    _ => fail(ln, "syntax"),
                };
                if !event_ok(ev) {
                    fail(ln, "value");
                }
                let e = match events.get_mut(&ev) {
                    Some(e) => e,
                    None => fail(ln, "reference"),
                };
                if e.sold.contains(&seat) {
                    fail(ln, "duplicate");
                }
                let cap = venues[&e.venue];
                if e.sold.len() as u64 >= cap {
                    fail(ln, "capacity");
                }
                e.sold.insert(seat);
                revenue += e.price;
                sold_n += 1;
                recs += 1;
            }
            ("R", 3) => {
                let ev = parse_event(f[1]);
                let seat = parse_seat(f[2]);
                let (ev, seat) = match (ev, seat) {
                    (Some(a), Some(b)) => (a, b),
                    _ => fail(ln, "syntax"),
                };
                if !event_ok(ev) {
                    fail(ln, "value");
                }
                let e = match events.get_mut(&ev) {
                    Some(e) => e,
                    None => fail(ln, "reference"),
                };
                if !e.sold.remove(&seat) {
                    fail(ln, "reference");
                }
                revenue -= e.price;
                refund_n += 1;
                recs += 1;
            }
            ("END", 3) => {
                let count = count_num(f[1], 1, 9);
                let cents = count_num(f[2], 1, 12);
                let (count, cents) = match (count, cents) {
                    (Some(a), Some(b)) => (a, b),
                    _ => fail(ln, "syntax"),
                };
                if count != recs || cents != revenue {
                    fail(ln, "summary");
                }
                ended = true;
            }
            _ => fail(ln, "syntax"),
        }
    }

    if !ended {
        fail(lines.len() + 1, "summary");
    }

    let mut out = String::new();
    out.push_str(&format!(
        "venues {} events {} sold {} refunds {}\n",
        venues.len(),
        events.len(),
        sold_n,
        refund_n
    ));
    out.push_str(&format!("revenue {}\n", money(revenue)));

    for (code, _) in &venues {
        let mut n: u64 = 0;
        let mut t: u64 = 0;
        let mut rev: u64 = 0;
        for e in events.values() {
            if e.venue == *code {
                let k = e.sold.len() as u64;
                n += 1;
                t += k;
                rev += k * e.price;
            }
        }
        let name: String = code.iter().map(|&c| c as char).collect();
        out.push_str(&format!(
            "{} events={} tickets={} revenue={}\n",
            name,
            n,
            t,
            money(rev)
        ));
    }

    let mut top: Vec<(u64, u64)> = events
        .iter()
        .map(|(&num, e)| (e.sold.len() as u64, num))
        .collect();
    top.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    for (t, num) in top.iter().take(3) {
        out.push_str(&format!("top {:06} {}\n", num, t));
    }

    print!("{}", out);
    let _ = io::stdout().flush();
}
