use std::io::{self, Read, Write};

struct Parser {
    s: Vec<u8>,
    i: usize,
    total: i64,
}

impl Parser {
    fn skip_ws(&mut self) {
        while self.i < self.s.len() {
            match self.s[self.i] {
                b' ' | b'\t' | b'\r' | b'\n' => self.i += 1,
                _ => break,
            }
        }
    }

    fn skip_string(&mut self) {
        self.i += 1;
        while self.i < self.s.len() {
            if self.s[self.i] == b'\\' {
                self.i += 2;
            } else if self.s[self.i] == b'"' {
                self.i += 1;
                return;
            } else {
                self.i += 1;
            }
        }
    }

    fn parse_value(&mut self) {
        self.skip_ws();
        if self.i >= self.s.len() {
            return;
        }
        let c = self.s[self.i];
        if c == b'{' {
            self.i += 1;
            self.skip_ws();
            if self.i < self.s.len() && self.s[self.i] == b'}' {
                self.i += 1;
                return;
            }
            loop {
                self.skip_ws();
                if self.i >= self.s.len() {
                    return;
                }
                self.skip_string();
                self.skip_ws();
                if self.i < self.s.len() && self.s[self.i] == b':' {
                    self.i += 1;
                }
                self.parse_value();
                self.skip_ws();
                if self.i < self.s.len() && self.s[self.i] == b',' {
                    self.i += 1;
                    continue;
                }
                if self.i < self.s.len() && self.s[self.i] == b'}' {
                    self.i += 1;
                }
                return;
            }
        }
        if c == b'[' {
            self.i += 1;
            self.skip_ws();
            if self.i < self.s.len() && self.s[self.i] == b']' {
                self.i += 1;
                return;
            }
            loop {
                self.skip_ws();
                if self.i < self.s.len() && self.s[self.i] == b']' {
                    self.i += 1;
                    return;
                }
                if self.i >= self.s.len() {
                    return;
                }
                self.parse_value();
                self.skip_ws();
                if self.i < self.s.len() && self.s[self.i] == b',' {
                    self.i += 1;
                    continue;
                }
                if self.i < self.s.len() && self.s[self.i] == b']' {
                    self.i += 1;
                }
                return;
            }
        }
        if c == b'"' {
            self.skip_string();
            return;
        }
        if c == b'-' || c.is_ascii_digit() {
            let start = self.i;
            if self.s[self.i] == b'-' {
                self.i += 1;
            }
            while self.i < self.s.len() && self.s[self.i].is_ascii_digit() {
                self.i += 1;
            }
            let text = std::str::from_utf8(&self.s[start..self.i]).unwrap_or("0");
            self.total += text.parse::<i64>().unwrap_or(0);
            return;
        }
        for word in [b"true".as_slice(), b"false".as_slice(), b"null".as_slice()] {
            if self.i + word.len() <= self.s.len() && &self.s[self.i..self.i + word.len()] == word {
                self.i += word.len();
                return;
            }
        }
        self.i += 1;
    }
}

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();
    let mut p = Parser { s: data, i: 0, total: 0 };
    while p.i < p.s.len() {
        p.parse_value();
        p.skip_ws();
        if p.i >= p.s.len() {
            break;
        }
    }
    io::stdout().write_all(format!("{}\n", p.total).as_bytes()).unwrap();
}
