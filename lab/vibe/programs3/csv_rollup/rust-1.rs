use std::collections::HashMap;
use std::io::{self, Read, Write};

fn valid_name(s: &[u8]) -> bool {
    if s.is_empty() || s.len() > 16 {
        return false;
    }
    s.iter().all(|&c| {
        (c >= b'a' && c <= b'z') || (c >= b'0' && c <= b'9') || c == b'_'
    })
}

fn parse_digits(s: &[u8], max: u64) -> Option<u64> {
    if s.is_empty() {
        return None;
    }
    let mut value = 0u64;
    for &c in s {
        if c < b'0' || c > b'9' {
            return None;
        }
        value = value * 10 + (c - b'0') as u64;
        if value > max {
            return None;
        }
    }
    Some(value)
}

fn parse_qty(s: &[u8]) -> Option<i64> {
    let (negative, digits) = if s.first() == Some(&b'-') {
        (true, &s[1..])
    } else {
        (false, s)
    };
    if digits.is_empty() {
        return None;
    }
    let magnitude = parse_digits(digits, 1000)? as i64;
    if negative {
        Some(-magnitude)
    } else {
        Some(magnitude)
    }
}

fn parse_line(line: &[u8]) -> Option<(Vec<u8>, Vec<u8>, i64, i64)> {
    let mut fields = line.split(|&b| b == b',');
    let region = fields.next()?;
    let product = fields.next()?;
    let qty_field = fields.next()?;
    let price_field = fields.next()?;
    if fields.next().is_some() {
        return None;
    }
    if !valid_name(region) || !valid_name(product) {
        return None;
    }
    let qty = parse_qty(qty_field)?;
    let price = parse_digits(price_field, 10_000_000)? as i64;
    Some((region.to_vec(), product.to_vec(), qty, price))
}

fn main() {
    let mut input = Vec::new();
    let _ = io::stdin().read_to_end(&mut input);

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    if input.is_empty() {
        writeln!(out, "rows 0 bad 0 groups 0").unwrap();
        writeln!(out, "total 0").unwrap();
        out.flush().unwrap();
        return;
    }

    let mut lines: Vec<&[u8]> = input.split(|&b| b == b'\n').collect();
    if input.last() == Some(&b'\n') {
        lines.pop();
    }

    let mut groups: HashMap<(Vec<u8>, Vec<u8>), (i64, i64)> = HashMap::new();
    let mut region_revenue: HashMap<Vec<u8>, i64> = HashMap::new();
    let mut good = 0u64;
    let mut bad = 0u64;
    let mut total = 0i64;

    for line in lines.into_iter().skip(1) {
        match parse_line(line) {
            Some((region, product, qty, price)) => {
                good += 1;
                let revenue = qty * price;
                total += revenue;
                *region_revenue.entry(region.clone()).or_insert(0) += revenue;
                let group = groups.entry((region, product)).or_insert((0, 0));
                group.0 += qty;
                group.1 += revenue;
            }
            None => bad += 1,
        }
    }

    let mut ordered_groups: Vec<(&Vec<u8>, &Vec<u8>, i64, i64)> = groups
        .iter()
        .map(|((region, product), &(qty, revenue))| (region, product, qty, revenue))
        .collect();
    ordered_groups.sort_by(|a, b| {
        b.3.cmp(&a.3)
            .then_with(|| a.0.as_slice().cmp(b.0.as_slice()))
            .then_with(|| a.1.as_slice().cmp(b.1.as_slice()))
    });

    let mut regions: Vec<(&Vec<u8>, i64)> = region_revenue
        .iter()
        .map(|(region, &sum)| (region, sum))
        .collect();
    regions.sort_by(|a, b| a.0.as_slice().cmp(b.0.as_slice()));

    writeln!(
        out,
        "rows {} bad {} groups {}",
        good,
        bad,
        groups.len()
    )
    .unwrap();

    for &(region, product, qty_sum, revenue) in ordered_groups.iter().take(10) {
        out.write_all(region).unwrap();
        out.write_all(b" ").unwrap();
        out.write_all(product).unwrap();
        writeln!(out, " {} {}", qty_sum, revenue).unwrap();
    }

    for (region, sum) in regions {
        out.write_all(b"region ").unwrap();
        out.write_all(region).unwrap();
        writeln!(out, " revenue {}", sum).unwrap();
    }

    writeln!(out, "total {}", total).unwrap();
    out.flush().unwrap();
}
