use std::collections::BTreeMap;
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
    let mut v: u64 = 0;
    for b in s.bytes() {
        v = v * 10 + (b - b'0') as u64;
        if v > 2147483647 {
            return None;
        }
    }
    if v == 0 {
        None
    } else {
        Some(v as u32)
    }
}

fn reject(cmd: &str, errors: &mut u64, out: &mut String) {
    *errors += 1;
    let op = if cmd.is_empty() { "error" } else { cmd };
    out.push_str("error ");
    out.push_str(op);
    out.push('\n');
}

fn process(line: &str, items: &mut BTreeMap<u32, Item>, errors: &mut u64, out: &mut String) {
    let (cmd, rest_opt): (&str, Option<&str>) = match line.find(' ') {
        Some(i) => (&line[..i], Some(&line[i + 1..])),
        None => (line, None),
    };

    match cmd {
        "add" => {
            let rest = match rest_opt {
                Some(r) => r,
                None => return reject(cmd, errors, out),
            };
            let (idtok, text) = match rest.find(' ') {
                Some(j) => (&rest[..j], &rest[j + 1..]),
                None => return reject(cmd, errors, out),
            };
            if text.is_empty() {
                return reject(cmd, errors, out);
            }
            let id = match parse_id(idtok) {
                Some(v) => v,
                None => return reject(cmd, errors, out),
            };
            if items.contains_key(&id) {
                return reject(cmd, errors, out);
            }
            items.insert(
                id,
                Item {
                    done: false,
                    text: text.to_string(),
                },
            );
            out.push_str(&format!("added {}\n", id));
        }
        "done" | "remove" | "show" => {
            let rest = match rest_opt {
                Some(r) if !r.contains(' ') => r,
                _ => return reject(cmd, errors, out),
            };
            let id = match parse_id(rest) {
                Some(v) => v,
                None => return reject(cmd, errors, out),
            };
            match cmd {
                "done" => {
                    match items.get_mut(&id) {
                        Some(it) if !it.done => {
                            it.done = true;
                            out.push_str(&format!("done {}\n", id));
                        }
                        _ => reject(cmd, errors, out),
                    }
                }
                "remove" => {
                    if items.remove(&id).is_some() {
                        out.push_str(&format!("removed {}\n", id));
                    } else {
                        reject(cmd, errors, out);
                    }
                }
                _ => {
                    match items.get(&id) {
                        Some(it) => {
                            let st = if it.done { "done" } else { "open" };
                            out.push_str(&format!("todo {} {} {}\n", id, st, it.text));
                        }
                        None => reject(cmd, errors, out),
                    }
                }
            }
        }
        "list" => {
            if rest_opt.is_some() {
                return reject(cmd, errors, out);
            }
            let open: Vec<(&u32, &Item)> = items.iter().filter(|(_, it)| !it.done).collect();
            out.push_str(&format!("list {}\n", open.len()));
            for (id, it) in open {
                out.push_str(&format!("todo {} open {}\n", id, it.text));
            }
        }
        "stats" => {
            if rest_opt.is_some() {
                return reject(cmd, errors, out);
            }
            let total = items.len();
            let done = items.values().filter(|it| it.done).count();
            let open = total - done;
            let chars: usize = items.values().map(|it| it.text.chars().count()).sum();
            out.push_str(&format!(
                "stats total {} open {} done {} chars {} errors {}\n",
                total, open, done, chars, *errors
            ));
        }
        _ => reject(cmd, errors, out),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mut data: Vec<u8> = Vec::new();
    let mut loaded = false;
    if let Some(path) = args.get(1) {
        if let Ok(bytes) = fs::read(path) {
            data = bytes;
            loaded = true;
        }
    }
    if !loaded {
        let _ = io::stdin().read_to_end(&mut data);
    }

    let text = String::from_utf8_lossy(&data).into_owned();

    let mut items: BTreeMap<u32, Item> = BTreeMap::new();
    let mut errors: u64 = 0;
    let mut out = String::new();

    for line in text.split('\n') {
        if line.trim().is_empty() {
            continue;
        }
        process(line, &mut items, &mut errors, &mut out);
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
