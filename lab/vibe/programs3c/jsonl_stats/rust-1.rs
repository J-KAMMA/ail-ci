use std::collections::{BTreeMap, HashMap};
use std::io::{self, Read, Write};

enum Val {
    Null,
    Bool,
    Num { int: bool, text: String },
    Str(String),
    Arr,
    Obj(Vec<(String, Val)>),
}

struct P<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn value(&mut self) -> Option<Val> {
        self.ws();
        match self.peek()? {
            b'{' => self.object(),
            b'[' => self.array(),
            b'"' => Some(Val::Str(self.string()?)),
            b't' => self.lit(b"true", Val::Bool),
            b'f' => self.lit(b"false", Val::Bool),
            b'n' => self.lit(b"null", Val::Null),
            b'-' | b'0'..=b'9' => self.number(),
            _ => None,
        }
    }

    fn lit(&mut self, s: &[u8], v: Val) -> Option<Val> {
        if self.b[self.i..].starts_with(s) {
            self.i += s.len();
            Some(v)
        } else {
            None
        }
    }

    fn number(&mut self) -> Option<Val> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        match self.peek()? {
            b'0' => self.i += 1,
            b'1'..=b'9' => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.i += 1;
                }
            }
            _ => return None,
        }
        let mut int = true;
        if self.peek() == Some(b'.') {
            int = false;
            self.i += 1;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return None;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            int = false;
            self.i += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.i += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return None;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        let text = String::from_utf8(self.b[start..self.i].to_vec()).ok()?;
        Some(Val::Num { int, text })
    }

    fn hex4(&mut self) -> Option<u32> {
        if self.i + 4 > self.b.len() {
            return None;
        }
        let mut v = 0u32;
        for k in 0..4 {
            let c = self.b[self.i + k];
            let d = (c as char).to_digit(16)?;
            v = v * 16 + d;
        }
        self.i += 4;
        Some(v)
    }

    fn string(&mut self) -> Option<String> {
        // assumes current byte is '"'
        self.i += 1;
        let mut out: Vec<u8> = Vec::new();
        loop {
            let c = self.peek()?;
            self.i += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let e = self.peek()?;
                    self.i += 1;
                    let ch: char = match e {
                        b'"' => '"',
                        b'\\' => '\\',
                        b'/' => '/',
                        b'b' => '\u{8}',
                        b'f' => '\u{c}',
                        b'n' => '\n',
                        b'r' => '\r',
                        b't' => '\t',
                        b'u' => {
                            let u = self.hex4()?;
                            if (0xD800..0xDC00).contains(&u) {
                                if self.b.get(self.i) == Some(&b'\\')
                                    && self.b.get(self.i + 1) == Some(&b'u')
                                {
                                    self.i += 2;
                                    let lo = self.hex4()?;
                                    if !(0xDC00..0xE000).contains(&lo) {
                                        return None;
                                    }
                                    char::from_u32(0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00))?
                                } else {
                                    return None;
                                }
                            } else if (0xDC00..0xE000).contains(&u) {
                                return None;
                            } else {
                                char::from_u32(u)?
                            }
                        }
                        _ => return None,
                    };
                    let mut buf = [0u8; 4];
                    out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
                }
                0..=0x1f => return None,
                _ => out.push(c),
            }
        }
        String::from_utf8(out).ok()
    }

    fn array(&mut self) -> Option<Val> {
        self.i += 1;
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Some(Val::Arr);
        }
        loop {
            self.value()?;
            self.ws();
            match self.peek()? {
                b',' => self.i += 1,
                b']' => {
                    self.i += 1;
                    return Some(Val::Arr);
                }
                _ => return None,
            }
        }
    }

    fn object(&mut self) -> Option<Val> {
        self.i += 1;
        self.ws();
        let mut fields: Vec<(String, Val)> = Vec::new();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Some(Val::Obj(fields));
        }
        loop {
            self.ws();
            if self.peek()? != b'"' {
                return None;
            }
            let k = self.string()?;
            self.ws();
            if self.peek()? != b':' {
                return None;
            }
            self.i += 1;
            let v = self.value()?;
            fields.push((k, v));
            self.ws();
            match self.peek()? {
                b',' => self.i += 1,
                b'}' => {
                    self.i += 1;
                    return Some(Val::Obj(fields));
                }
                _ => return None,
            }
        }
    }
}

fn parse_line(line: &[u8]) -> Option<Val> {
    let mut p = P { b: line, i: 0 };
    let v = p.value()?;
    p.ws();
    if p.i != line.len() {
        return None;
    }
    Some(v)
}

fn get<'a>(fields: &'a [(String, Val)], key: &str) -> Option<&'a Val> {
    fields.iter().rev().find(|(k, _)| k == key).map(|(_, v)| v)
}

fn extract(v: Option<Val>) -> Option<(String, String, i64)> {
    let fields = match v? {
        Val::Obj(f) => f,
        _ => return None,
    };
    let user = match get(&fields, "user") {
        Some(Val::Str(s)) => s.clone(),
        _ => return None,
    };
    let amount = match get(&fields, "amount") {
        Some(Val::Num { int: true, text }) => text.parse::<i64>().ok()?,
        _ => return None,
    };
    let tag = match get(&fields, "tag") {
        None => String::new(),
        Some(Val::Str(s)) => s.clone(),
        _ => return None,
    };
    let _ = (Val::Null, Val::Bool, Val::Arr);
    Some((user, tag, amount))
}

fn run() {
    let mut data = Vec::new();
    let _ = io::stdin().read_to_end(&mut data);

    let mut bad: u64 = 0;
    let mut tags: BTreeMap<String, (u64, i128)> = BTreeMap::new();
    let mut users: HashMap<String, u64> = HashMap::new();

    for raw in data.split(|&b| b == b'\n') {
        let line = if raw.last() == Some(&b'\r') {
            &raw[..raw.len() - 1]
        } else {
            raw
        };
        if line.iter().all(|&b| b == b' ' || b == b'\t') {
            continue;
        }
        match extract(parse_line(line)) {
            Some((u, t, a)) => {
                let e = tags.entry(t).or_insert((0, 0));
                e.0 += 1;
                e.1 += a as i128;
                *users.entry(u).or_insert(0) += 1;
            }
            None => bad += 1,
        }
    }

    let mut out = String::new();
    out.push_str(&format!(
        "bad {} tags {} users {}\n",
        bad,
        tags.len(),
        users.len()
    ));
    for (t, (c, s)) in &tags {
        out.push_str(&format!("tag {} count {} total {}\n", t, c, s));
    }
    let mut uv: Vec<(&String, &u64)> = users.iter().collect();
    uv.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    for (u, c) in uv.into_iter().take(10) {
        out.push_str(&format!("user {} {}\n", u, c));
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}

fn main() {
    let child = std::thread::Builder::new()
        .stack_size(256 << 20)
        .spawn(run)
        .unwrap();
    let _ = child.join();
}
