use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::{self, Write};
use std::process;

struct Event {
    venue: String,
    price: u64,
    sold: HashSet<String>,
}

fn status_of(cat: &str) -> i32 {
    match cat {
        "header" => 2,
        "syntax" => 3,
        "value" => 4,
        "reference" => 5,
        "duplicate" => 6,
        "capacity" => 7,
        "summary" => 8,
        _ => 1,
    }
}

fn split_lines(data: &[u8]) -> Vec<&[u8]> {
    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if data.last() == Some(&b'\n') {
        lines.pop();
    }
    lines
}

fn all_digits(s: &[u8]) -> bool {
    s.iter().all(|b| b.is_ascii_digit())
}

fn parse_num(s: &[u8]) -> u64 {
    let mut v = 0u64;
    for &b in s {
        v = v * 10 + (b - b'0') as u64;
    }
    v
}

fn no_leading_zero(s: &[u8]) -> bool {
    if s.len() == 1 {
        return true;
    }
    s[0] != b'0'
}

fn venue_syntax(s: &[u8]) -> bool {
    s.len() == 3 && s.iter().all(|b| b.is_ascii_uppercase())
}

fn name_syntax(s: &[u8]) -> bool {
    if s.is_empty() || s.len() > 40 {
        return false;
    }
    if !s
        .iter()
        .all(|&b| (0x20..=0x7E).contains(&b) && b != b'|')
    {
        return false;
    }
    s[0] != b' ' && s[s.len() - 1] != b' '
}

fn cap_syntax(s: &[u8]) -> bool {
    !s.is_empty() && s.len() <= 6 && all_digits(s)
}

fn cap_value(s: &[u8]) -> bool {
    if s.len() > 1 && s[0] == b'0' {
        return false;
    }
    let v = parse_num(s);
    (1..=100000).contains(&v)
}

fn event_syntax(s: &[u8]) -> bool {
    s.len() == 6 && all_digits(s)
}

fn event_value(s: &[u8]) -> bool {
    let d = |i: usize| (s[i] - b'0') as u32;
    (3 * d(0) + d(1) + 3 * d(2) + d(3) + 3 * d(4) + d(5)) % 10 == 0
}

fn date_syntax(s: &[u8]) -> bool {
    s.len() == 10
        && all_digits(&s[0..4])
        && s[4] == b'-'
        && all_digits(&s[5..7])
        && s[7] == b'-'
        && all_digits(&s[8..10])
}

fn date_value(s: &[u8]) -> bool {
    let y = parse_num(&s[0..4]) as u32;
    let m = parse_num(&s[5..7]) as u32;
    let d = parse_num(&s[8..10]) as u32;
    if !(2000..=2099).contains(&y) {
        return false;
    }
    if !(1..=12).contains(&m) {
        return false;
    }
    let leap = y % 4 == 0;
    let maxd = match m {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if leap {
                29
            } else {
                28
            }
        }
        _ => return false,
    };
    d >= 1 && d <= maxd
}

fn time_syntax(s: &[u8]) -> bool {
    s.len() == 5 && all_digits(&s[0..2]) && s[2] == b':' && all_digits(&s[3..5])
}

fn time_value(s: &[u8]) -> bool {
    let hh = parse_num(&s[0..2]);
    let mm = parse_num(&s[3..5]);
    hh <= 23 && mm <= 59
}

fn price_syntax(s: &[u8]) -> bool {
    let mut dot: Option<usize> = None;
    for (i, &b) in s.iter().enumerate() {
        if b == b'.' {
            if dot.is_some() {
                return false;
            }
            dot = Some(i);
        }
    }
    let i = match dot {
        Some(i) => i,
        None => return false,
    };
    let ip = &s[..i];
    let fp = &s[i + 1..];
    !ip.is_empty() && ip.len() <= 4 && all_digits(ip) && fp.len() == 2 && all_digits(fp)
}

fn price_cents(s: &[u8]) -> Option<u64> {
    let i = s.iter().position(|&b| b == b'.')?;
    let ip = &s[..i];
    let fp = &s[i + 1..];
    if ip.len() > 1 && ip[0] == b'0' {
        return None;
    }
    let intv = parse_num(ip);
    let cents = (fp[0] - b'0') as u64 * 10 + (fp[1] - b'0') as u64;
    let total = intv * 100 + cents;
    if total % 5 != 0 {
        return None;
    }
    Some(total)
}

fn seat_syntax(s: &[u8]) -> bool {
    s.len() >= 2 && s.len() <= 4 && s[0].is_ascii_uppercase() && all_digits(&s[1..])
}

fn seat_value(s: &[u8]) -> bool {
    let d = &s[1..];
    if d.len() > 1 && d[0] == b'0' {
        return false;
    }
    let v = parse_num(d);
    (1..=999).contains(&v)
}

fn buyer_syntax(s: &[u8]) -> bool {
    s.len() >= 4
        && s.len() <= 12
        && s[0].is_ascii_lowercase()
        && s[1..]
            .iter()
            .all(|&b| b.is_ascii_lowercase() || b.is_ascii_digit())
}

fn count_syntax(s: &[u8]) -> bool {
    !s.is_empty() && s.len() <= 9 && all_digits(s)
}

fn cents_syntax(s: &[u8]) -> bool {
    !s.is_empty() && s.len() <= 12 && all_digits(s)
}

fn money(cents: u64) -> String {
    format!("{}.{:02}", cents / 100, cents % 100)
}

fn build_success(
    venues: &HashMap<String, u64>,
    events: &HashMap<String, Event>,
    sold_records: u64,
    refund_records: u64,
    revenue: u64,
) -> String {
    let mut out = String::new();
    out.push_str(&format!(
        "venues {} events {} sold {} refunds {}\n",
        venues.len(),
        events.len(),
        sold_records,
        refund_records
    ));
    out.push_str(&format!("revenue {}\n", money(revenue)));

    let mut codes: Vec<&String> = venues.keys().collect();
    codes.sort();
    for code in codes {
        let mut n = 0u64;
        let mut t = 0u64;
        let mut rev = 0u64;
        for ev in events.values() {
            if &ev.venue == code {
                n += 1;
                let c = ev.sold.len() as u64;
                t += c;
                rev += ev.price * c;
            }
        }
        out.push_str(&format!(
            "{} events={} tickets={} revenue={}\n",
            code,
            n,
            t,
            money(rev)
        ));
    }

    let mut list: Vec<(&String, usize)> =
        events.iter().map(|(k, v)| (k, v.sold.len())).collect();
    list.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    for (k, t) in list.into_iter().take(3) {
        out.push_str(&format!("top {} {}\n", k, t));
    }
    out
}

fn run(data: &[u8]) -> Result<String, (usize, &'static str)> {
    let lines = split_lines(data);
    if lines.is_empty() || lines[0] != &b"TKT/1"[..] {
        return Err((1, "header"));
    }

    let mut venues: HashMap<String, u64> = HashMap::new();
    let mut events: HashMap<String, Event> = HashMap::new();
    let mut revenue: u64 = 0;
    let mut sold_records: u64 = 0;
    let mut refund_records: u64 = 0;
    let mut records: u64 = 0;

    let mut i = 1usize;
    while i < lines.len() {
        let lineno = i + 1;
        let fields: Vec<&[u8]> = lines[i].split(|&b| b == b'|').collect();

        match fields[0] {
            b"V" => {
                if fields.len() != 4 {
                    return Err((lineno, "syntax"));
                }
                if !venue_syntax(fields[1]) || !name_syntax(fields[2]) || !cap_syntax(fields[3]) {
                    return Err((lineno, "syntax"));
                }
                if !cap_value(fields[3]) {
                    return Err((lineno, "value"));
                }
                let code = String::from_utf8(fields[1].to_vec()).unwrap();
                if venues.contains_key(&code) {
                    return Err((lineno, "duplicate"));
                }
                let cap = parse_num(fields[3]);
                venues.insert(code, cap);
                records += 1;
            }
            b"E" => {
                if fields.len() != 6 {
                    return Err((lineno, "syntax"));
                }
                if !event_syntax(fields[1])
                    || !venue_syntax(fields[2])
                    || !date_syntax(fields[3])
                    || !time_syntax(fields[4])
                    || !price_syntax(fields[5])
                {
                    return Err((lineno, "syntax"));
                }
                if !event_value(fields[1]) || !date_value(fields[3]) || !time_value(fields[4]) {
                    return Err((lineno, "value"));
                }
                let price = match price_cents(fields[5]) {
                    Some(p) => p,
                    None => return Err((lineno, "value")),
                };
                let ev = String::from_utf8(fields[1].to_vec()).unwrap();
                let vc = String::from_utf8(fields[2].to_vec()).unwrap();
                if !venues.contains_key(&vc) {
                    return Err((lineno, "reference"));
                }
                if events.contains_key(&ev) {
                    return Err((lineno, "duplicate"));
                }
                events.insert(
                    ev,
                    Event {
                        venue: vc,
                        price,
                        sold: HashSet::new(),
                    },
                );
                records += 1;
            }
            b"S" => {
                if fields.len() != 4 {
                    return Err((lineno, "syntax"));
                }
                if !event_syntax(fields[1])
                    || !seat_syntax(fields[2])
                    || !buyer_syntax(fields[3])
                {
                    return Err((lineno, "syntax"));
                }
                if !event_value(fields[1]) || !seat_value(fields[2]) {
                    return Err((lineno, "value"));
                }
                let ev = String::from_utf8(fields[1].to_vec()).unwrap();
                let seat = String::from_utf8(fields[2].to_vec()).unwrap();
                {
                    let event = match events.get(&ev) {
                        Some(e) => e,
                        None => return Err((lineno, "reference")),
                    };
                    if event.sold.contains(&seat) {
                        return Err((lineno, "duplicate"));
                    }
                    let cap = *venues.get(&event.venue).unwrap();
                    if event.sold.len() as u64 >= cap {
                        return Err((lineno, "capacity"));
                    }
                }
                let event = events.get_mut(&ev).unwrap();
                event.sold.insert(seat);
                revenue += event.price;
                sold_records += 1;
                records += 1;
            }
            b"R" => {
                if fields.len() != 3 {
                    return Err((lineno, "syntax"));
                }
                if !event_syntax(fields[1]) || !seat_syntax(fields[2]) {
                    return Err((lineno, "syntax"));
                }
                if !event_value(fields[1]) || !seat_value(fields[2]) {
                    return Err((lineno, "value"));
                }
                let ev = String::from_utf8(fields[1].to_vec()).unwrap();
                let seat = String::from_utf8(fields[2].to_vec()).unwrap();
                let event = match events.get_mut(&ev) {
                    Some(e) => e,
                    None => return Err((lineno, "reference")),
                };
                if !event.sold.remove(&seat) {
                    return Err((lineno, "reference"));
                }
                revenue -= event.price;
                refund_records += 1;
                records += 1;
            }
            b"END" => {
                if fields.len() != 3 {
                    return Err((lineno, "syntax"));
                }
                if !count_syntax(fields[1]) || !cents_syntax(fields[2]) {
                    return Err((lineno, "syntax"));
                }
                if !no_leading_zero(fields[1]) || !no_leading_zero(fields[2]) {
                    return Err((lineno, "value"));
                }
                let c = parse_num(fields[1]);
                let ce = parse_num(fields[2]);
                if c != records || ce != revenue {
                    return Err((lineno, "summary"));
                }
                if i + 1 < lines.len() {
                    return Err((i + 2, "summary"));
                }
                return Ok(build_success(
                    &venues,
                    &events,
                    sold_records,
                    refund_records,
                    revenue,
                ));
            }
            _ => return Err((lineno, "syntax")),
        }

        i += 1;
    }

    Err((lines.len() + 1, "summary"))
}

fn main() {
    let args: Vec<std::ffi::OsString> = env::args_os().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let data = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => process::exit(1),
    };

    match run(&data) {
        Ok(out) => {
            let stdout = io::stdout();
            let mut handle = stdout.lock();
            let _ = handle.write_all(out.as_bytes());
            let _ = handle.flush();
        }
        Err((line, cat)) => {
            let msg = format!("line {}: {}\n", line, cat);
            let stdout = io::stdout();
            let mut handle = stdout.lock();
            let _ = handle.write_all(msg.as_bytes());
            let _ = handle.flush();
            process::exit(status_of(cat));
        }
    }
}
