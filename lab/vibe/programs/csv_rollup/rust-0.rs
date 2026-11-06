use std::collections::{BTreeMap, HashMap};
use std::io::{self, Read, Write};

fn parse_name(s: &[u8]) -> Option<String> {
    if s.is_empty() || s.len() > 16 {
        return None;
    }
    for &c in s {
        let ok = c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_';
        if !ok {
            return None;
        }
    }
    Some(String::from_utf8(s.to_vec()).unwrap())
}

fn parse_unsigned(s: &[u8], cap: i64) -> Option<i64> {
    if s.is_empty() {
        return None;
    }
    let mut v: i64 = 0;
    for &c in s {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (c - b'0') as i64;
        if v > cap + 1 {
            v = cap + 1;
        }
    }
    if v > cap {
        None
    } else {
        Some(v)
    }
}

fn parse_qty(s: &[u8]) -> Option<i64> {
    let (neg, digits) = if !s.is_empty() && s[0] == b'-' {
        (true, &s[1..])
    } else {
        (false, s)
    };
    let v = parse_unsigned(digits, 1000)?;
    let v = if neg { -v } else { v };
    if v < -1000 || v > 1000 {
        return None;
    }
    Some(v)
}

fn parse_price(s: &[u8]) -> Option<i64> {
    parse_unsigned(s, 10_000_000)
}

fn main() {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();

    let mut out = String::new();

    if input.is_empty() {
        out.push_str("rows 0 bad 0 groups 0\n");
        out.push_str("total 0\n");
        let stdout = io::stdout();
        let mut lock = stdout.lock();
        let _ = lock.write_all(out.as_bytes());
        let _ = lock.flush();
        return;
    }

    let mut parts: Vec<&[u8]> = input.split(|&b| b == b'\n').collect();
    if let Some(last) = parts.last() {
        if last.is_empty() {
            parts.pop();
        }
    }

    let mut good: u64 = 0;
    let mut bad: u64 = 0;
    let mut groups: HashMap<(String, String), (i64, i64)> = HashMap::new();

    for line in parts.iter().skip(1) {
        let fields: Vec<&[u8]> = line.split(|&b| b == b',').collect();
        if fields.len() != 4 {
            bad += 1;
            continue;
        }
        let region = match parse_name(fields[0]) {
            Some(r) => r,
            None => {
                bad += 1;
                continue;
            }
        };
        let product = match parse_name(fields[1]) {
            Some(p) => p,
            None => {
                bad += 1;
                continue;
            }
        };
        let qty = match parse_qty(fields[2]) {
            Some(q) => q,
            None => {
                bad += 1;
                continue;
            }
        };
        let price = match parse_price(fields[3]) {
            Some(p) => p,
            None => {
                bad += 1;
                continue;
            }
        };

        good += 1;
        let entry = groups.entry((region, product)).or_insert((0i64, 0i64));
        entry.0 += qty;
        entry.1 += qty * price;
    }

    struct Group {
        region: String,
        product: String,
        qty_sum: i64,
        revenue: i64,
    }

    let mut list: Vec<Group> = groups
        .into_iter()
        .map(|((region, product), (qty_sum, revenue))| Group {
            region,
            product,
            qty_sum,
            revenue,
        })
        .collect();

    list.sort_by(|a, b| {
        b.revenue
            .cmp(&a.revenue)
            .then_with(|| a.region.as_bytes().cmp(b.region.as_bytes()))
            .then_with(|| a.product.as_bytes().cmp(b.product.as_bytes()))
    });

    let mut regions: BTreeMap<String, i64> = BTreeMap::new();
    let mut total: i64 = 0;
    for g in list.iter() {
        *regions.entry(g.region.clone()).or_insert(0) += g.revenue;
        total += g.revenue;
    }

    out.push_str(&format!("rows {} bad {} groups {}\n", good, bad, list.len()));

    for g in list.iter().take(10) {
        out.push_str(&format!(
            "{} {} {} {}\n",
            g.region, g.product, g.qty_sum, g.revenue
        ));
    }

    for (region, sum) in regions.iter() {
        out.push_str(&format!("region {} revenue {}\n", region, sum));
    }

    out.push_str(&format!("total {}\n", total));

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
