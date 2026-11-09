use std::collections::{BTreeMap, HashSet};
use std::io::{self, BufRead, Write};

const MAX_AMOUNT: u128 = 1_000_000_000_000;

fn parse_amount(token: &str) -> Option<u128> {
    if token.is_empty() || !token.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }

    let value = token.parse::<u128>().ok()?;
    if value <= MAX_AMOUNT {
        Some(value)
    } else {
        None
    }
}

fn main() {
    let stdin = io::stdin();
    let mut balances: BTreeMap<String, i128> = BTreeMap::new();
    let mut bad: usize = 0;

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(line) => line,
            Err(_) => break,
        };

        let mut tokens = line.split_whitespace();
        let payer = match tokens.next() {
            Some(payer) => payer,
            None => continue,
        };

        let amount_token = match tokens.next() {
            Some(token) => token,
            None => {
                bad += 1;
                continue;
            }
        };

        let participants: Vec<&str> = tokens.collect();

        if participants.is_empty() {
            bad += 1;
            continue;
        }

        let amount = match parse_amount(amount_token) {
            Some(amount) => amount,
            None => {
                bad += 1;
                continue;
            }
        };

        let mut seen = HashSet::with_capacity(participants.len());
        let mut duplicate = false;

        for &participant in &participants {
            if !seen.insert(participant) {
                duplicate = true;
                break;
            }
        }

        if duplicate {
            bad += 1;
            continue;
        }

        *balances.entry(payer.to_string()).or_insert(0) += amount as i128;

        let k = participants.len() as u128;
        let q = amount / k;
        let r = amount % k;

        for (i, &participant) in participants.iter().enumerate() {
            let owes = if (i as u128) < r { q + 1 } else { q };
            *balances.entry(participant.to_string()).or_insert(0) -= owes as i128;
        }
    }

    let total: i128 = balances.values().copied().sum();

    let mut output = String::new();
    output.push_str(&format!("bad {}\n", bad));

    for (name, net) in &balances {
        output.push_str(&format!("balance {} {}\n", name, net));
    }

    output.push_str(&format!("total {}\n", total));

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    let _ = handle.write_all(output.as_bytes());
}
