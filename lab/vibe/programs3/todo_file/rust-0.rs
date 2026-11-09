use std::collections::BTreeMap;
use std::env;
use std::fs;

struct Item {
    done: bool,
    text: String,
}

fn parse_id(s: &str) -> Option<u32> {
    if s.is_empty() {
        return None;
    }
    let mut v: u64 = 0;
    for b in s.bytes() {
        if !b.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (b - b'0') as u64;
        if v > 2_147_483_647 {
            return None;
        }
    }
    if v == 0 {
        None
    } else {
        Some(v as u32)
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut out = String::new();

    if args.len() >= 2 {
        if let Ok(content) = fs::read_to_string(&args[1]) {
            let mut items: BTreeMap<u32, Item> = BTreeMap::new();
            let mut errors: u64 = 0;

            for line in content.lines() {
                if line.is_empty() {
                    continue;
                }

                let parts: Vec<&str> = line.splitn(3, ' ').collect();
                let cmd = parts[0];

                if cmd.is_empty() {
                    errors += 1;
                    out.push_str("error\n");
                    continue;
                }

                match cmd {
                    "add" => {
                        if parts.len() < 3 {
                            errors += 1;
                            out.push_str("error add\n");
                            continue;
                        }
                        let text = parts[2];
                        match parse_id(parts[1]) {
                            Some(id) if !text.is_empty() => {
                                if items.contains_key(&id) {
                                    errors += 1;
                                    out.push_str("error add\n");
                                } else {
                                    items.insert(
                                        id,
                                        Item {
                                            done: false,
                                            text: text.to_string(),
                                        },
                                    );
                                    out.push_str(&format!("added {}\n", id));
                                }
                            }
                            _ => {
                                errors += 1;
                                out.push_str("error add\n");
                            }
                        }
                    }
                    "done" => {
                        let mut ok = false;
                        if parts.len() == 2 {
                            if let Some(id) = parse_id(parts[1]) {
                                if let Some(item) = items.get_mut(&id) {
                                    if !item.done {
                                        item.done = true;
                                        out.push_str(&format!("done {}\n", id));
                                        ok = true;
                                    }
                                }
                            }
                        }
                        if !ok {
                            errors += 1;
                            out.push_str("error done\n");
                        }
                    }
                    "remove" => {
                        let mut ok = false;
                        if parts.len() == 2 {
                            if let Some(id) = parse_id(parts[1]) {
                                if items.remove(&id).is_some() {
                                    out.push_str(&format!("removed {}\n", id));
                                    ok = true;
                                }
                            }
                        }
                        if !ok {
                            errors += 1;
                            out.push_str("error remove\n");
                        }
                    }
                    "show" => {
                        let mut ok = false;
                        if parts.len() == 2 {
                            if let Some(id) = parse_id(parts[1]) {
                                if let Some(item) = items.get(&id) {
                                    let status = if item.done { "done" } else { "open" };
                                    out.push_str(&format!(
                                        "todo {} {} {}\n",
                                        id, status, item.text
                                    ));
                                    ok = true;
                                }
                            }
                        }
                        if !ok {
                            errors += 1;
                            out.push_str("error show\n");
                        }
                    }
                    "list" => {
                        if parts.len() != 1 {
                            errors += 1;
                            out.push_str("error list\n");
                        } else {
                            let open: Vec<(&u32, &Item)> =
                                items.iter().filter(|(_, it)| !it.done).collect();
                            out.push_str(&format!("list {}\n", open.len()));
                            for (id, item) in open {
                                out.push_str(&format!("todo {} open {}\n", id, item.text));
                            }
                        }
                    }
                    "stats" => {
                        if parts.len() != 1 {
                            errors += 1;
                            out.push_str("error stats\n");
                        } else {
                            let total = items.len();
                            let done = items.values().filter(|it| it.done).count();
                            let open = total - done;
                            let chars: usize = items
                                .values()
                                .map(|it| it.text.chars().count())
                                .sum();
                            out.push_str(&format!(
                                "stats total {} open {} done {} chars {} errors {}\n",
                                total, open, done, chars, errors
                            ));
                        }
                    }
                    _ => {
                        errors += 1;
                        out.push_str(&format!("error {}\n", cmd));
                    }
                }
            }
        }
    }

    print!("{}", out);
}
