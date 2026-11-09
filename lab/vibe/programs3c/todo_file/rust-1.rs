use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io::{self, Read, Write};

struct Item {
    done: bool,
    text: String,
}

fn parse_id(s: &str) -> Option<u32> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let t = s.trim_start_matches('0');
    if t.is_empty() || t.len() > 10 {
        return None;
    }
    let v: u64 = t.parse().ok()?;
    if (1..=2147483647).contains(&v) {
        Some(v as u32)
    } else {
        None
    }
}

fn exec(line: &str, items: &mut BTreeMap<u32, Item>, errors: usize) -> Result<String, ()> {
    let (cmd, rest) = match line.find(' ') {
        Some(i) => (&line[..i], Some(&line[i + 1..])),
        None => (line, None),
    };
    match cmd {
        "add" => {
            let rest = rest.ok_or(())?;
            let (ids, text) = match rest.find(' ') {
                Some(j) => (&rest[..j], &rest[j + 1..]),
                None => return Err(()),
            };
            if text.is_empty() {
                return Err(());
            }
            let id = parse_id(ids).ok_or(())?;
            if items.contains_key(&id) {
                return Err(());
            }
            items.insert(
                id,
                Item {
                    done: false,
                    text: text.to_string(),
                },
            );
            Ok(format!("added {}\n", id))
        }
        "done" => {
            let id = parse_id(rest.ok_or(())?).ok_or(())?;
            let it = items.get_mut(&id).ok_or(())?;
            if it.done {
                return Err(());
            }
            it.done = true;
            Ok(format!("done {}\n", id))
        }
        "remove" => {
            let id = parse_id(rest.ok_or(())?).ok_or(())?;
            if items.remove(&id).is_none() {
                return Err(());
            }
            Ok(format!("removed {}\n", id))
        }
        "show" => {
            let id = parse_id(rest.ok_or(())?).ok_or(())?;
            let it = items.get(&id).ok_or(())?;
            let st = if it.done { "done" } else { "open" };
            Ok(format!("todo {} {} {}\n", id, st, it.text))
        }
        "list" => {
            if rest.is_some() {
                return Err(());
            }
            let open: Vec<(&u32, &Item)> = items.iter().filter(|(_, it)| !it.done).collect();
            let mut s = format!("list {}\n", open.len());
            for (id, it) in open {
                s.push_str(&format!("todo {} open {}\n", id, it.text));
            }
            Ok(s)
        }
        "stats" => {
            if rest.is_some() {
                return Err(());
            }
            let total = items.len();
            let open = items.values().filter(|it| !it.done).count();
            let done = total - open;
            let chars: usize = items.values().map(|it| it.text.chars().count()).sum();
            Ok(format!(
                "stats total {} open {} done {} chars {} errors {}\n",
                total, open, done, chars, errors
            ))
        }
        _ => Err(()),
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut data: Option<Vec<u8>> = None;
    if args.len() > 1 {
        if let Ok(d) = fs::read(&args[1]) {
            data = Some(d);
        }
    }
    let data = match data {
        Some(d) => d,
        None => {
            let mut buf = Vec::new();
            let _ = io::stdin().read_to_end(&mut buf);
            buf
        }
    };

    let text = String::from_utf8_lossy(&data);
    let mut items: BTreeMap<u32, Item> = BTreeMap::new();
    let mut errors: usize = 0;
    let mut out = String::new();

    for line in text.split('\n') {
        if line.is_empty() {
            continue;
        }
        match exec(line, &mut items, errors) {
            Ok(s) => out.push_str(&s),
            Err(()) => {
                errors += 1;
                let op = line.split(' ').next().unwrap_or("");
                let op = if op.is_empty() { "error" } else { op };
                out.push_str(&format!("error {}\n", op));
            }
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
