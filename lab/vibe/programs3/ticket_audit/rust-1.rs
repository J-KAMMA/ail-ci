use std::collections::{BTreeMap, HashMap, HashSet};
use std::env;
use std::fs;
use std::process::exit;

struct Event {
    venue: String,
    price: i64,
    sold: HashSet<String>,
}

fn all_digits(s: &[u8]) -> bool {
    s.iter().all(|b| b.is_ascii_digit())
}

fn parse_u64(s: &[u8]) -> u64 {
    let mut v: u64 = 0;
    for &b in s {
        v = v * 10 + (b - b'0') as u64;
    }
    v
}

fn venue_code_syntax(f: &[u8]) -> bool {
    f.len() == 3 && f.iter().all(|&b| b.is_ascii_uppercase())
}

fn name_syntax(f: &[u8]) -> bool {
    if f.is_empty() || f.len() > 40 {
        return false;
    }
    if f[0] == b' ' || f[f.len() - 1] == b' ' {
        return false;
    }
    f.iter().all(|&b| b >= 0x20 && b <= 0x7E && b != b'|')
}

fn capacity_syntax(f: &[u8]) -> bool {
    !f.is_empty() && f.len() <= 6 && all_digits(f)
}

fn event_syntax(f: &[u8]) -> bool {
    f.len() == 6 && all_digits(f)
}

fn date_syntax(f: &[u8]) -> bool {
    f.len() == 10
        && all_digits(&f[0..4])
        && f[4] == b'-'
        && all_digits(&f[5..7])
        && f[7] == b'-'
        && all_digits(&f[8..10])
}

fn time_syntax(f: &[u8]) -> bool {
    f.len() == 5 && all_digits(&f[0..2]) && f[2] == b':' && all_digits(&f[3..5])
}

fn price_syntax(f: &[u8]) -> bool {
    let mut dot: Option<usize> = None;
    for (i, &b) in f.iter().enumerate() {
        if b == b'.' {
            if dot.is_some() {
                return false;
            }
            dot = Some(i);
        }
    }
    let dot = match dot {
        Some(d) => d,
        None => return false,
    };
    if dot < 1 || dot > 4 {
        return false;
    }
    if f.len() != dot + 3 {
        return false;
    }
    all_digits(&f[..dot]) && all_digits(&f[dot + 1..])
}

fn seat_syntax(f: &[u8]) -> bool {
    f.len() >= 2 && f.len() <= 4 && f[0].is_ascii_uppercase() && all_digits(&f[1..])
}

fn buyer_syntax(f: &[u8]) -> bool {
    if f.len() < 4 || f.len() > 12 {
        return false;
    }
    if !f[0].is_ascii_lowercase() {
        return false;
    }
    f.iter()
        .all(|&b| b.is_ascii_lowercase() || b.is_ascii_digit())
}

fn count_syntax(f: &[u8]) -> bool {
    !f.is_empty() && f.len() <= 9 && all_digits(f)
}

fn cents_syntax(f: &[u8]) -> bool {
    !f.is_empty() && f.len() <= 12 && all_digits(f)
}

fn capacity_value(f: &[u8]) -> bool {
    if f.len() > 1 && f[0] == b'0' {
        return false;
    }
    let v = parse_u64(f);
    v >= 1 && v <= 100000
}

fn event_value(f: &[u8]) -> bool {
    let d0 = (f[0] - b'0') as u32;
    let d1 = (f[1] - b'0') as u32;
    let d2 = (f[2] - b'0') as u32;
    let d3 = (f[3] - b'0') as u32;
    let d4 = (f[4] - b'0') as u32;
    let d5 = (f[5] - b'0') as u32;
    (3 * d0 + d1 + 3 * d2 + d3 + 3 * d4 + d5) % 10 == 0
}

fn date_value(f: &[u8]) -> bool {
    let year = parse_u64(&f[0..4]) as u32;
    let month = parse_u64(&f[5..7]) as u32;
    let day = parse_u64(&f[8..10]) as u32;
    if year < 2000 || year > 2099 {
        return false;
    }
    if month < 1 || month > 12 {
        return false;
    }
    let leap = year % 4 == 0;
    let last = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if leap {
                29
            } else {
                28
            }
        }
        _ => 0,
    };
    day >= 1 && day <= last
}

fn time_value(f: &[u8]) -> bool {
    let hh = parse_u64(&f[0..2]);
    let mm = parse_u64(&f[3..5]);
    hh <= 23 && mm <= 59
}

fn price_value(f: &[u8]) -> bool {
    let dot = match f.iter().position(|&b| b == b'.') {
        Some(d) => d,
        None => return false,
    };
    let intpart = &f[..dot];
    if intpart.len() > 1 && intpart[0] == b'0' {
        return false;
    }
    let amount = parse_u64(intpart) * 100 + parse_u64(&f[dot + 1..]);
    amount % 5 == 0
}

fn price_cents(f: &[u8]) -> i64 {
    let dot = f.iter().position(|&b| b == b'.').unwrap();
    (parse_u64(&f[..dot]) * 100 + parse_u64(&f[dot + 1..])) as i64
}

fn seat_value(f: &[u8]) -> bool {
    let digits = &f[1..];
    if digits.len() > 1 && digits[0] == b'0' {
        return false;
    }
    let n = parse_u64(digits);
    n >= 1 && n <= 999
}

fn no_leading_zero(f: &[u8]) -> bool {
    !(f.len() > 1 && f[0] == b'0')
}

fn money(cents: i64) -> String {
    format!("{}.{:02}", cents / 100, cents % 100)
}

fn main() {
    let args: Vec<_> = env::args_os().collect();
    if args.len() != 2 {
        exit(1);
    }
    let data = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };

    let mut lines: Vec<&[u8]> = Vec::new();
    let mut start = 0usize;
    for i in 0..data.len() {
        if data[i] == b'\n' {
            lines.push(&data[start..i]);
            start = i + 1;
        }
    }
    if start < data.len() {
        lines.push(&data[start..]);
    }

    if lines.is_empty() || lines[0] != b"TKT/1" {
        println!("line 1: header");
        exit(2);
    }

    let mut venues: BTreeMap<String, u64> = BTreeMap::new();
    let mut events: HashMap<String, Event> = HashMap::new();
    let mut records: u64 = 0;
    let mut s_count: u64 = 0;
    let mut r_count: u64 = 0;
    let mut revenue: i64 = 0;
    let mut saw_end = false;

    for idx in 1..lines.len() {
        let line = lines[idx];
        let lineno = idx + 1;
        let fields: Vec<&[u8]> = line.split(|&b| b == b'|').collect();
        let t = fields[0];

        let expected: usize = if t == b"V" {
            4
        } else if t == b"E" {
            6
        } else if t == b"S" {
            4
        } else if t == b"R" {
            3
        } else if t == b"END" {
            3
        } else {
            0
        };

        if expected == 0 || fields.len() != expected {
            println!("line {}: syntax", lineno);
            exit(3);
        }

        if t == b"V" {
            let code = fields[1];
            let name = fields[2];
            let cap = fields[3];
            if !venue_code_syntax(code) || !name_syntax(name) || !capacity_syntax(cap) {
                println!("line {}: syntax", lineno);
                exit(3);
            }
            if !capacity_value(cap) {
                println!("line {}: value", lineno);
                exit(4);
            }
            let code_str = String::from_utf8(code.to_vec()).unwrap();
            if venues.contains_key(&code_str) {
                println!("line {}: duplicate", lineno);
                exit(6);
            }
            venues.insert(code_str, parse_u64(cap));
            records += 1;
        } else if t == b"E" {
            let ev = fields[1];
            let vcode = fields[2];
            let date = fields[3];
            let time = fields[4];
            let price = fields[5];
            if !event_syntax(ev)
                || !venue_code_syntax(vcode)
                || !date_syntax(date)
                || !time_syntax(time)
                || !price_syntax(price)
            {
                println!("line {}: syntax", lineno);
                exit(3);
            }
            if !event_value(ev) || !date_value(date) || !time_value(time) || !price_value(price) {
                println!("line {}: value", lineno);
                exit(4);
            }
            let ev_str = String::from_utf8(ev.to_vec()).unwrap();
            let vcode_str = String::from_utf8(vcode.to_vec()).unwrap();
            if !venues.contains_key(&vcode_str) {
                println!("line {}: reference", lineno);
                exit(5);
            }
            if events.contains_key(&ev_str) {
                println!("line {}: duplicate", lineno);
                exit(6);
            }
            events.insert(
                ev_str,
                Event {
                    venue: vcode_str,
                    price: price_cents(price),
                    sold: HashSet::new(),
                },
            );
            records += 1;
        } else if t == b"S" {
            let ev = fields[1];
            let seat = fields[2];
            let buyer = fields[3];
            if !event_syntax(ev) || !seat_syntax(seat) || !buyer_syntax(buyer) {
                println!("line {}: syntax", lineno);
                exit(3);
            }
            if !event_value(ev) || !seat_value(seat) {
                println!("line {}: value", lineno);
                exit(4);
            }
            let ev_str = String::from_utf8(ev.to_vec()).unwrap();
            let seat_str = String::from_utf8(seat.to_vec()).unwrap();
            let event = match events.get_mut(&ev_str) {
                Some(e) => e,
                None => {
                    println!("line {}: reference", lineno);
                    exit(5);
                }
            };
            if event.sold.contains(&seat_str) {
                println!("line {}: duplicate", lineno);
                exit(6);
            }
            let cap = venues[&event.venue];
            if event.sold.len() as u64 >= cap {
                println!("line {}: capacity", lineno);
                exit(7);
            }
            event.sold.insert(seat_str);
            revenue += event.price;
            s_count += 1;
            records += 1;
        } else if t == b"R" {
            let ev = fields[1];
            let seat = fields[2];
            if !event_syntax(ev) || !seat_syntax(seat) {
                println!("line {}: syntax", lineno);
                exit(3);
            }
            if !event_value(ev) || !seat_value(seat) {
                println!("line {}: value", lineno);
                exit(4);
            }
            let ev_str = String::from_utf8(ev.to_vec()).unwrap();
            let seat_str = String::from_utf8(seat.to_vec()).unwrap();
            let event = match events.get_mut(&ev_str) {
                Some(e) => e,
                None => {
                    println!("line {}: reference", lineno);
                    exit(5);
                }
            };
            if !event.sold.remove(&seat_str) {
                println!("line {}: reference", lineno);
                exit(5);
            }
            revenue -= event.price;
            r_count += 1;
            records += 1;
        } else {
            let cnt = fields[1];
            let cents = fields[2];
            if !count_syntax(cnt) || !cents_syntax(cents) {
                println!("line {}: syntax", lineno);
                exit(3);
            }
            if !no_leading_zero(cnt) || !no_leading_zero(cents) {
                println!("line {}: value", lineno);
                exit(4);
            }
            let c = parse_u64(cnt);
            let ce = parse_u64(cents);
            if c != records || ce as i64 != revenue {
                println!("line {}: summary", lineno);
                exit(8);
            }
            if idx + 1 < lines.len() {
                println!("line {}: summary", lineno + 1);
                exit(8);
            }
            saw_end = true;
            break;
        }
    }

    if !saw_end {
        println!("line {}: summary", lines.len() + 1);
        exit(8);
    }

    let mut vstats: BTreeMap<String, (u64, u64, i64)> = BTreeMap::new();
    for code in venues.keys() {
        vstats.insert(code.clone(), (0, 0, 0));
    }
    for e in events.values() {
        if let Some(st) = vstats.get_mut(&e.venue) {
            st.0 += 1;
            st.1 += e.sold.len() as u64;
            st.2 += e.price * e.sold.len() as i64;
        }
    }

    println!(
        "venues {} events {} sold {} refunds {}",
        venues.len(),
        events.len(),
        s_count,
        r_count
    );
    println!("revenue {}", money(revenue));
    for (code, stat) in &vstats {
        let (n, t, rev) = *stat;
        println!("{} events={} tickets={} revenue={}", code, n, t, money(rev));
    }

    let mut top: Vec<(&String, usize)> = events.iter().map(|(k, v)| (k, v.sold.len())).collect();
    top.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    for (ev, sold) in top.iter().take(3) {
        println!("top {} {}", ev, sold);
    }
}
