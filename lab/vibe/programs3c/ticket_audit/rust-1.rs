use std::collections::{BTreeMap, BTreeSet};
use std::io::{self, Write};
use std::process;

#[derive(Clone, Copy)]
enum Cat {
    Header,
    Syntax,
    Value,
    Reference,
    Duplicate,
    Capacity,
    Summary,
}

impl Cat {
    fn name(self) -> &'static str {
        match self {
            Cat::Header => "header",
            Cat::Syntax => "syntax",
            Cat::Value => "value",
            Cat::Reference => "reference",
            Cat::Duplicate => "duplicate",
            Cat::Capacity => "capacity",
            Cat::Summary => "summary",
        }
    }
    fn code(self) -> i32 {
        match self {
            Cat::Header => 2,
            Cat::Syntax => 3,
            Cat::Value => 4,
            Cat::Reference => 5,
            Cat::Duplicate => 6,
            Cat::Capacity => 7,
            Cat::Summary => 8,
        }
    }
}

fn fail(n: usize, c: Cat) -> ! {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    let _ = writeln!(out, "line {}: {}", n, c.name());
    let _ = out.flush();
    process::exit(c.code());
}

enum Rec {
    Venue { code: [u8; 3], cap: u64 },
    Event { num: [u8; 6], venue: [u8; 3], price: u64 },
    Sale { event: [u8; 6], seat: (u8, u32) },
    Refund { event: [u8; 6], seat: (u8, u32) },
    End { count: u64, cents: u64 },
}

struct Event {
    venue: [u8; 3],
    price: u64,
    sold: BTreeSet<(u8, u32)>,
}

fn arr3(b: &[u8]) -> [u8; 3] {
    [b[0], b[1], b[2]]
}

fn arr6(b: &[u8]) -> [u8; 6] {
    [b[0], b[1], b[2], b[3], b[4], b[5]]
}

fn is_digits(b: &[u8]) -> bool {
    !b.is_empty() && b.iter().all(|c| c.is_ascii_digit())
}

fn num(b: &[u8]) -> u64 {
    b.iter().fold(0u64, |a, &c| a * 10 + (c - b'0') as u64)
}

fn no_lead_zero(b: &[u8]) -> bool {
    !(b.len() > 1 && b[0] == b'0')
}

fn syn_code(b: &[u8]) -> bool {
    b.len() == 3 && b.iter().all(|c| c.is_ascii_uppercase())
}

fn syn_name(b: &[u8]) -> bool {
    if b.is_empty() || b.len() > 40 {
        return false;
    }
    if !b.iter().all(|&c| (0x20..=0x7E).contains(&c) && c != b'|') {
        return false;
    }
    b[0] != b' ' && b[b.len() - 1] != b' '
}

fn syn_digits(b: &[u8], min: usize, max: usize) -> bool {
    b.len() >= min && b.len() <= max && is_digits(b)
}

fn syn_event(b: &[u8]) -> bool {
    syn_digits(b, 6, 6)
}

fn syn_date(b: &[u8]) -> bool {
    b.len() == 10
        && b[4] == b'-'
        && b[7] == b'-'
        && is_digits(&b[0..4])
        && is_digits(&b[5..7])
        && is_digits(&b[8..10])
}

fn syn_time(b: &[u8]) -> bool {
    b.len() == 5 && b[2] == b':' && is_digits(&b[0..2]) && is_digits(&b[3..5])
}

fn split_price(b: &[u8]) -> Option<(&[u8], &[u8])> {
    let p = b.iter().position(|&c| c == b'.')?;
    let ip = &b[..p];
    let fp = &b[p + 1..];
    if ip.is_empty() || ip.len() > 4 || !is_digits(ip) {
        return None;
    }
    if fp.len() != 2 || !is_digits(fp) {
        return None;
    }
    Some((ip, fp))
}

fn syn_seat(b: &[u8]) -> bool {
    b.len() >= 2 && b.len() <= 4 && b[0].is_ascii_uppercase() && is_digits(&b[1..])
}

fn syn_buyer(b: &[u8]) -> bool {
    let n = b.len();
    (4..=12).contains(&n)
        && b[0].is_ascii_lowercase()
        && b.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
}

fn event_ok(b: &[u8]) -> bool {
    let d: Vec<u32> = b.iter().map(|&c| (c - b'0') as u32).collect();
    (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0
}

fn date_ok(y: u64, m: u64, d: u64) -> bool {
    if !(2000..=2099).contains(&y) {
        return false;
    }
    if !(1..=12).contains(&m) {
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

fn parse_record(f: &[&[u8]]) -> Result<Rec, Cat> {
    let kind = std::str::from_utf8(f[0]).unwrap_or("");
    let want = match kind {
        "V" => 4,
        "E" => 6,
        "S" => 4,
        "R" => 3,
        "END" => 3,
        _ => return Err(Cat::Syntax),
    };
    if f.len() != want {
        return Err(Cat::Syntax);
    }
    match kind {
        "V" => {
            let (code, name, cap) = (f[1], f[2], f[3]);
            if !(syn_code(code) && syn_name(name) && syn_digits(cap, 1, 6)) {
                return Err(Cat::Syntax);
            }
            if !no_lead_zero(cap) {
                return Err(Cat::Value);
            }
            let c = num(cap);
            if c < 1 || c > 100000 {
                return Err(Cat::Value);
            }
            Ok(Rec::Venue { code: arr3(code), cap: c })
        }
        "E" => {
            let (ev, vn, date, time, price) = (f[1], f[2], f[3], f[4], f[5]);
            let pr = split_price(price);
            if !(syn_event(ev) && syn_code(vn) && syn_date(date) && syn_time(time)) || pr.is_none()
            {
                return Err(Cat::Syntax);
            }
            let (ip, fp) = pr.unwrap();
            if !event_ok(ev) {
                return Err(Cat::Value);
            }
            let (y, m, d) = (num(&date[0..4]), num(&date[5..7]), num(&date[8..10]));
            if !date_ok(y, m, d) {
                return Err(Cat::Value);
            }
            if num(&time[0..2]) > 23 || num(&time[3..5]) > 59 {
                return Err(Cat::Value);
            }
            if !no_lead_zero(ip) {
                return Err(Cat::Value);
            }
            let cents = num(ip) * 100 + num(fp);
            if cents % 5 != 0 {
                return Err(Cat::Value);
            }
            Ok(Rec::Event {
                num: arr6(ev),
                venue: arr3(vn),
                price: cents,
            })
        }
        "S" => {
            let (ev, seat, buyer) = (f[1], f[2], f[3]);
            if !(syn_event(ev) && syn_seat(seat) && syn_buyer(buyer)) {
                return Err(Cat::Syntax);
            }
            if !event_ok(ev) {
                return Err(Cat::Value);
            }
            if seat[1] == b'0' {
                return Err(Cat::Value);
            }
            Ok(Rec::Sale {
                event: arr6(ev),
                seat: (seat[0], num(&seat[1..]) as u32),
            })
        }
        "R" => {
            let (ev, seat) = (f[1], f[2]);
            if !(syn_event(ev) && syn_seat(seat)) {
                return Err(Cat::Syntax);
            }
            if !event_ok(ev) {
                return Err(Cat::Value);
            }
            if seat[1] == b'0' {
                return Err(Cat::Value);
            }
            Ok(Rec::Refund {
                event: arr6(ev),
                seat: (seat[0], num(&seat[1..]) as u32),
            })
        }
        "END" => {
            let (cn, ce) = (f[1], f[2]);
            if !(syn_digits(cn, 1, 9) && syn_digits(ce, 1, 12)) {
                return Err(Cat::Syntax);
            }
            if !no_lead_zero(cn) || !no_lead_zero(ce) {
                return Err(Cat::Value);
            }
            Ok(Rec::End {
                count: num(cn),
                cents: num(ce),
            })
        }
        _ => Err(Cat::Syntax),
    }
}

fn money(c: u64) -> String {
    format!("{}.{:02}", c / 100, c % 100)
}

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => process::exit(1),
    };

    let mut lines: Vec<&[u8]> = data.split(|&c| c == b'\n').collect();
    if data.last() == Some(&b'\n') {
        lines.pop();
    }

    if lines.is_empty() || lines[0] != &b"TKT/1"[..] {
        fail(1, Cat::Header);
    }

    let mut venues: BTreeMap<[u8; 3], u64> = BTreeMap::new();
    let mut events: BTreeMap<[u8; 6], Event> = BTreeMap::new();
    let mut sales: u64 = 0;
    let mut refunds: u64 = 0;
    let mut revenue: u64 = 0;
    let mut records: u64 = 0;
    let mut ended = false;

    for (i, line) in lines.iter().enumerate().skip(1) {
        let n = i + 1;
        if ended {
            fail(n, Cat::Summary);
        }
        let fields: Vec<&[u8]> = line.split(|&c| c == b'|').collect();
        let rec = match parse_record(&fields) {
            Ok(r) => r,
            Err(c) => fail(n, c),
        };
        match rec {
            Rec::Venue { code, cap } => {
                if venues.contains_key(&code) {
                    fail(n, Cat::Duplicate);
                }
                venues.insert(code, cap);
                records += 1;
            }
            Rec::Event { num, venue, price } => {
                if !venues.contains_key(&venue) {
                    fail(n, Cat::Reference);
                }
                if events.contains_key(&num) {
                    fail(n, Cat::Duplicate);
                }
                events.insert(
                    num,
                    Event {
                        venue,
                        price,
                        sold: BTreeSet::new(),
                    },
                );
                records += 1;
            }
            Rec::Sale { event, seat } => {
                let (venue, price) = match events.get(&event) {
                    Some(e) => (e.venue, e.price),
                    None => fail(n, Cat::Reference),
                };
                let cap = venues[&venue];
                let ev = events.get_mut(&event).unwrap();
                if ev.sold.contains(&seat) {
                    fail(n, Cat::Duplicate);
                }
                if ev.sold.len() as u64 >= cap {
                    fail(n, Cat::Capacity);
                }
                ev.sold.insert(seat);
                revenue += price;
                sales += 1;
                records += 1;
            }
            Rec::Refund { event, seat } => {
                match events.get_mut(&event) {
                    None => fail(n, Cat::Reference),
                    Some(ev) => {
                        if !ev.sold.remove(&seat) {
                            fail(n, Cat::Reference);
                        }
                        revenue -= ev.price;
                    }
                }
                refunds += 1;
                records += 1;
            }
            Rec::End { count, cents } => {
                if count != records || cents != revenue {
                    fail(n, Cat::Summary);
                }
                ended = true;
            }
        }
    }

    if !ended {
        fail(lines.len() + 1, Cat::Summary);
    }

    let stdout = io::stdout();
    let mut out = stdout.lock();
    let _ = writeln!(
        out,
        "venues {} events {} sold {} refunds {}",
        venues.len(),
        events.len(),
        sales,
        refunds
    );
    let _ = writeln!(out, "revenue {}", money(revenue));
    for code in venues.keys() {
        let mut n: u64 = 0;
        let mut t: u64 = 0;
        let mut rv: u64 = 0;
        for ev in events.values() {
            if ev.venue == *code {
                n += 1;
                t += ev.sold.len() as u64;
                rv += ev.sold.len() as u64 * ev.price;
            }
        }
        let cs = std::str::from_utf8(&code[..]).unwrap_or("");
        let _ = writeln!(
            out,
            "{} events={} tickets={} revenue={}",
            cs,
            n,
            t,
            money(rv)
        );
    }
    let mut list: Vec<(u64, [u8; 6])> = events
        .iter()
        .map(|(k, e)| (e.sold.len() as u64, *k))
        .collect();
    list.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    for (t, k) in list.iter().take(3) {
        let ks = std::str::from_utf8(&k[..]).unwrap_or("");
        let _ = writeln!(out, "top {} {}", ks, t);
    }
    let _ = out.flush();
}
