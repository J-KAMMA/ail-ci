use std::collections::HashMap;
use std::io::{self, Read, Write};

fn valid_name(b: &[u8]) -> bool {
    if b.is_empty() || b.len() > 16 {
        return false;
    }
    b.iter()
        .all(|&c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
}

fn parse_digits(b: &[u8]) -> Option<u128> {
    if b.is_empty() {
        return None;
    }
    let mut v: u128 = 0;
    for &c in b {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v.checked_mul(10)?.checked_add((c - b'0') as u128)?;
        if v > 1_000_000_000_000_000u128 {
            return None;
        }
    }
    Some(v)
}

fn parse_qty(b: &[u8]) -> Option<i64> {
    let (neg, digits) = if b.first() == Some(&b'-') {
        (true, &b[1..])
    } else {
        (false, b)
    };
    let v = parse_digits(digits)?;
    if v > 1000 {
        return None;
    }
    let val = v as i64;
    Some(if neg { -val } else { val })
}

fn parse_price(b: &[u8]) -> Option<i64> {
    let v = parse_digits(b)?;
    if v > 10_000_000 {
        return None;
    }
    Some(v as i64)
}

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();

    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if data.ends_with(b"\n") {
        lines.pop();
    }
    // If input is non-empty, first line is the header and is dropped.
    // If input is empty, `data.split` yields one empty slice which is also
    // treated as the (nonexistent) header, leaving no data lines.

    let mut groups: HashMap<(String, String), (i64, i64)> = HashMap::new();
    let mut good: u64 = 0;
    let mut bad: u64 = 0;

    for line in lines.iter().skip(1) {
        let fields: Vec<&[u8]> = line.split(|&b| b == b',').collect();
        if fields.len() != 4 {
            bad += 1;
            continue;
        }
        let region_b = fields[0];
        let product_b = fields[1];
        if !valid_name(region_b) || !valid_name(product_b) {
            bad += 1;
            continue;
        }
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
        let region = String::from_utf8(region_b.to_vec()).unwrap();
        let product = String::from_utf8(product_b.to_vec()).unwrap();
        let entry = groups.entry((region, product)).or_insert((0i64, 0i64));
        entry.0 += qty;
        entry.1 += qty * price;
    }

    let mut group_vec: Vec<((String, String), (i64, i64))> = groups.into_iter().collect();
    group_vec.sort_by(|a, b| {
        b.1 .1
            .cmp(&a.1 .1)
            .then_with(|| a.0 .0.cmp(&b.0 .0))
            .then_with(|| a.0 .1.cmp(&b.0 .1))
    });

    let mut region_map: HashMap<String, i64> = HashMap::new();
    for ((region, _product), (_qty_sum, revenue)) in group_vec.iter() {
        *region_map.entry(region.clone()).or_insert(0) += *revenue;
    }
    let mut region_vec: Vec<(String, i64)> = region_map.into_iter().collect();
    region_vec.sort_by(|a, b| a.0.cmp(&b.0));

    let total: i64 = group_vec.iter().map(|g| g.1 .1).sum();
    let n_groups = group_vec.len();

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    writeln!(out, "rows {} bad {} groups {}", good, bad, n_groups).unwrap();

    for ((region, product), (qty_sum, revenue)) in group_vec.iter().take(10) {
        writeln!(out, "{} {} {} {}", region, product, qty_sum, revenue).unwrap();
    }

    for (region, sum) in region_vec.iter() {
        writeln!(out, "region {} revenue {}", region, sum).unwrap();
    }

    writeln!(out, "total {}", total).unwrap();
}
