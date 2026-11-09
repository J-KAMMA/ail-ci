use std::collections::HashMap;
use std::io::{self, Read, Write};

fn valid_ident(s: &[u8]) -> bool {
    !s.is_empty()
        && s.len() <= 16
        && s
            .iter()
            .all(|&c| (c >= b'a' && c <= b'z') || (c >= b'0' && c <= b'9') || c == b'_')
}

fn parse_signed(s: &[u8], min: i64, max: i64) -> Option<i64> {
    if s.is_empty() {
        return None;
    }
    let (neg, digits) = if s[0] == b'-' { (true, &s[1..]) } else { (false, s) };
    if digits.is_empty() {
        return None;
    }
    let mut val: i64 = 0;
    for &c in digits {
        if !(c >= b'0' && c <= b'9') {
            return None;
        }
        val = val.saturating_mul(10).saturating_add((c - b'0') as i64);
    }
    let v = if neg { -val } else { val };
    if v < min || v > max {
        return None;
    }
    Some(v)
}

fn parse_unsigned(s: &[u8], max: i64) -> Option<i64> {
    if s.is_empty() {
        return None;
    }
    let mut val: i64 = 0;
    for &c in s {
        if !(c >= b'0' && c <= b'9') {
            return None;
        }
        val = val.saturating_mul(10).saturating_add((c - b'0') as i64);
    }
    if val > max {
        return None;
    }
    Some(val)
}

struct Group {
    region: String,
    product: String,
    qty_sum: i64,
    revenue: i64,
}

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();

    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    if data.is_empty() {
        let _ = write!(out, "rows 0 bad 0 groups 0\ntotal 0\n");
        let _ = out.flush();
        return;
    }

    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if data.last() == Some(&b'\n') {
        lines.pop();
    }
    if !lines.is_empty() {
        lines.remove(0);
    }

    let mut good: u64 = 0;
    let mut bad: u64 = 0;
    let mut groups: HashMap<(String, String), (i64, i64)> = HashMap::new();
    let mut regions: HashMap<String, i64> = HashMap::new();

    for line in lines {
        let fields: Vec<&[u8]> = line.split(|&b| b == b',').collect();
        let parsed = if fields.len() == 4
            && valid_ident(fields[0])
            && valid_ident(fields[1])
        {
            match (
                parse_signed(fields[2], -1000, 1000),
                parse_unsigned(fields[3], 10_000_000),
            ) {
                (Some(q), Some(p)) => Some((fields[0], fields[1], q, p)),
                _ => None,
            }
        } else {
            None
        };

        match parsed {
            Some((region, product, q, p)) => {
                good += 1;
                let rev = q * p;
                let region_s = String::from_utf8(region.to_vec()).unwrap();
                let product_s = String::from_utf8(product.to_vec()).unwrap();
                let e = groups.entry((region_s.clone(), product_s)).or_insert((0, 0));
                e.0 += q;
                e.1 += rev;
                *regions.entry(region_s).or_insert(0) += rev;
            }
            None => bad += 1,
        }
    }

    let n = groups.len();

    let mut gs: Vec<Group> = groups
        .into_iter()
        .map(|((region, product), (qty_sum, revenue))| Group {
            region,
            product,
            qty_sum,
            revenue,
        })
        .collect();

    gs.sort_by(|a, b| {
        b.revenue
            .cmp(&a.revenue)
            .then_with(|| a.region.cmp(&b.region))
            .then_with(|| a.product.cmp(&b.product))
    });

    let total: i64 = gs.iter().map(|g| g.revenue).sum();

    let mut rs: Vec<(String, i64)> = regions.into_iter().collect();
    rs.sort_by(|a, b| a.0.cmp(&b.0));

    let _ = writeln!(out, "rows {} bad {} groups {}", good, bad, n);
    for g in gs.iter().take(10) {
        let _ = writeln!(out, "{} {} {} {}", g.region, g.product, g.qty_sum, g.revenue);
    }
    for (region, sum) in rs {
        let _ = writeln!(out, "region {} revenue {}", region, sum);
    }
    let _ = writeln!(out, "total {}", total);
    let _ = out.flush();
}
