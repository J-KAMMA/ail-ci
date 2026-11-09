use std::collections::BTreeMap;
use std::io::{self, Read, Write};

enum Val {
    Null,
    Bool,
    Int(i64),
    NonInt,
    Str(String),
    Arr,
    Obj(Vec<(String, Val)>),
}

const MAX_DEPTH: usize = 512;

struct Parser<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn peek(&self) -> Option<u8> {
        self.b.get(self.pos).copied()
    }

    fn skip_ws(&mut self) {
        while let Some(c) = self.peek() {
            if c == b' ' || c == b'\t' || c == b'\n' || c == b'\r' {
                self.pos += 1;
            } else {
                break;
            }
        }
    }

    fn literal(&mut self, word: &[u8], v: Val) -> Option<Val> {
        if self.b[self.pos..].starts_with(word) {
            self.pos += word.len();
            Some(v)
        } else {
            None
        }
    }

    fn parse_value(&mut self, depth: usize) -> Option<Val> {
        if depth > MAX_DEPTH {
            return None;
        }
        self.skip_ws();
        match self.peek()? {
            b'{' => self.parse_object(depth + 1),
            b'[' => self.parse_array(depth + 1),
            b'"' => Some(Val::Str(self.parse_string()?)),
            b't' => self.literal(b"true", Val::Bool),
            b'f' => self.literal(b"false", Val::Bool),
            b'n' => self.literal(b"null", Val::Null),
            b'-' | b'0'..=b'9' => self.parse_number(),
            _ => None,
        }
    }

    fn parse_number(&mut self) -> Option<Val> {
        let start = self.pos;
        if self.peek() == Some(b'-') {
            self.pos += 1;
        }
        match self.peek()? {
            b'0' => self.pos += 1,
            b'1'..=b'9' => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.pos += 1;
                }
            }
            _ => return None,
        }
        let mut is_int = true;
        if self.peek() == Some(b'.') {
            is_int = false;
            self.pos += 1;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return None;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            is_int = false;
            self.pos += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.pos += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return None;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        if !is_int {
            return Some(Val::NonInt);
        }
        let s = std::str::from_utf8(&self.b[start..self.pos]).ok()?;
        match s.parse::<i64>() {
            Ok(v) => Some(Val::Int(v)),
            Err(_) => Some(Val::NonInt),
        }
    }

    fn hex4(&mut self) -> Option<u32> {
        let mut v = 0u32;
        for _ in 0..4 {
            let c = self.peek()?;
            self.pos += 1;
            let d = (c as char).to_digit(16)?;
            v = v * 16 + d;
        }
        Some(v)
    }

    fn parse_string(&mut self) -> Option<String> {
        if self.peek()? != b'"' {
            return None;
        }
        self.pos += 1;
        let mut out: Vec<u8> = Vec::new();
        loop {
            let c = self.peek()?;
            self.pos += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let e = self.peek()?;
                    self.pos += 1;
                    match e {
                        b'"' => out.push(b'"'),
                        b'\\' => out.push(b'\\'),
                        b'/' => out.push(b'/'),
                        b'b' => out.push(8),
                        b'f' => out.push(12),
                        b'n' => out.push(b'\n'),
                        b'r' => out.push(b'\r'),
                        b't' => out.push(b'\t'),
                        b'u' => {
                            let hi = self.hex4()?;
                            let cp = if (0xD800..0xDC00).contains(&hi) {
                                if self.b.get(self.pos) != Some(&b'\\')
                                    || self.b.get(self.pos + 1) != Some(&b'u')
                                {
                                    return None;
                                }
                                self.pos += 2;
                                let lo = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&lo) {
                                    return None;
                                }
                                0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                            } else if (0xDC00..0xE000).contains(&hi) {
                                return None;
                            } else {
                                hi
                            };
                            let ch = char::from_u32(cp)?;
                            let mut buf = [0u8; 4];
                            out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
                        }
                        _ => return None,
                    }
                }
                c if c < 0x20 => return None,
                _ => out.push(c),
            }
        }
        String::from_utf8(out).ok()
    }

    fn parse_array(&mut self, depth: usize) -> Option<Val> {
        self.pos += 1; // '['
        self.skip_ws();
        if self.peek()? == b']' {
            self.pos += 1;
            return Some(Val::Arr);
        }
        loop {
            self.parse_value(depth)?;
            self.skip_ws();
            match self.peek()? {
                b',' => self.pos += 1,
                b']' => {
                    self.pos += 1;
                    return Some(Val::Arr);
                }
                _ => return None,
            }
        }
    }

    fn parse_object(&mut self, depth: usize) -> Option<Val> {
        self.pos += 1; // '{'
        let mut fields: Vec<(String, Val)> = Vec::new();
        self.skip_ws();
        if self.peek()? == b'}' {
            self.pos += 1;
            return Some(Val::Obj(fields));
        }
        loop {
            self.skip_ws();
            let k = self.parse_string()?;
            self.skip_ws();
            if self.peek()? != b':' {
                return None;
            }
            self.pos += 1;
            let v = self.parse_value(depth)?;
            fields.push((k, v));
            self.skip_ws();
            match self.peek()? {
                b',' => self.pos += 1,
                b'}' => {
                    self.pos += 1;
                    return Some(Val::Obj(fields));
                }
                _ => return None,
            }
        }
    }
}

fn find<'a>(fields: &'a [(String, Val)], k: &str) -> Option<&'a Val> {
    fields
        .iter()
        .rev()
        .find(|(kk, _)| kk.as_str() == k)
        .map(|(_, v)| v)
}

fn parse_row(line: &[u8]) -> Option<(String, i64, String)> {
    let mut p = Parser { b: line, pos: 0 };
    let v = p.parse_value(0)?;
    p.skip_ws();
    if p.pos != line.len() {
        return None;
    }
    let fields = match v {
        Val::Obj(f) => f,
        _ => return None,
    };
    let user = match find(&fields, "user")? {
        Val::Str(s) => s.clone(),
        _ => return None,
    };
    let amount = match find(&fields, "amount")? {
        Val::Int(i) => *i,
        _ => return None,
    };
    let tag = match find(&fields, "tag") {
        None => String::new(),
        Some(Val::Str(s)) => s.clone(),
        Some(_) => return None,
    };
    Some((user, amount, tag))
}

fn main() {
    let mut input = Vec::new();
    let _ = io::stdin().read_to_end(&mut input);

    let mut bad: u64 = 0;
    let mut tags: BTreeMap<String, (u64, i128)> = BTreeMap::new();
    let mut users: BTreeMap<String, u64> = BTreeMap::new();

    for raw in input.split(|&c| c == b'\n') {
        let line: &[u8] = if raw.last() == Some(&b'\r') {
            &raw[..raw.len() - 1]
        } else {
            raw
        };
        if line.iter().all(|&c| c == b' ' || c == b'\t') {
            continue;
        }
        match parse_row(line) {
            Some((user, amount, tag)) => {
                let e = tags.entry(tag).or_insert((0, 0));
                e.0 += 1;
                e.1 += amount as i128;
                *users.entry(user).or_insert(0) += 1;
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
    let mut ul: Vec<(&String, &u64)> = users.iter().collect();
    ul.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    for (u, c) in ul.iter().take(10) {
        out.push_str(&format!("user {} {}\n", u, c));
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    let _ = lock.flush();
}
