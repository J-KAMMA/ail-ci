use std::collections::HashMap;
use std::io::Write;

#[derive(Clone, Debug, PartialEq)]
enum Tok {
    Num(u32),
    Word(String),
    Sym(&'static str),
}

enum Expr {
    Num(u32),
    Var(usize),
    Bin(&'static str, Box<Expr>, Box<Expr>),
    Un(u8, Box<Expr>),
}

fn tokenize(s: &[u8]) -> Option<Vec<Tok>> {
    let mut v = Vec::new();
    let mut i = 0;
    while i < s.len() {
        let c = s[i];
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
        } else if c.is_ascii_digit() {
            let mut val: u64 = 0;
            while i < s.len() && s[i].is_ascii_digit() {
                val = val * 10 + (s[i] - b'0') as u64;
                if val > 4294967295 {
                    return None;
                }
                i += 1;
            }
            if i < s.len() && (s[i].is_ascii_lowercase() || s[i] == b'_') {
                return None;
            }
            v.push(Tok::Num(val as u32));
        } else if c.is_ascii_lowercase() || c == b'_' {
            let st = i;
            while i < s.len() && (s[i].is_ascii_lowercase() || s[i].is_ascii_digit() || s[i] == b'_') {
                i += 1;
            }
            v.push(Tok::Word(String::from_utf8_lossy(&s[st..i]).into_owned()));
        } else {
            let two = if i + 1 < s.len() { Some(&s[i..i + 2]) } else { None };
            if let Some(t) = two {
                let sym = match t {
                    b"<>" => Some("<>"),
                    b"><" => Some("><"),
                    b"==" => Some("=="),
                    b"!=" => Some("!="),
                    _ => None,
                };
                if let Some(sy) = sym {
                    v.push(Tok::Sym(sy));
                    i += 2;
                    continue;
                }
            }
            let sym = match c {
                b'<' => "<",
                b'>' => ">",
                b'+' => "+",
                b'-' => "-",
                b'*' => "*",
                b'/' => "/",
                b'%' => "%",
                b'~' => "~",
                b'#' => "#",
                b'!' => "!",
                b'(' => "(",
                b')' => ")",
                b',' => ",",
                b'=' => "=",
                _ => return None,
            };
            v.push(Tok::Sym(sym));
            i += 1;
        }
    }
    Some(v)
}

const KW: [&str; 7] = ["set", "out", "loop", "when", "else", "end", "break"];

struct P<'a> {
    t: &'a [Tok],
    pos: usize,
    depth: u32,
    vars: &'a mut HashMap<String, usize>,
}

impl<'a> P<'a> {
    fn peek(&self) -> Option<&Tok> {
        self.t.get(self.pos)
    }
    fn sym(&self) -> Option<&'static str> {
        match self.t.get(self.pos) {
            Some(Tok::Sym(s)) => Some(s),
            _ => None,
        }
    }
    fn expr(&mut self) -> Option<Expr> {
        let mut l = self.cmp()?;
        while let Some(s) = self.sym() {
            if s == "<>" || s == "><" {
                self.pos += 1;
                let r = self.cmp()?;
                l = Expr::Bin(s, Box::new(l), Box::new(r));
            } else {
                break;
            }
        }
        Some(l)
    }
    fn cmp(&mut self) -> Option<Expr> {
        let l = self.add()?;
        if let Some(s) = self.sym() {
            if s == "==" || s == "!=" || s == "<" || s == ">" {
                self.pos += 1;
                let r = self.add()?;
                return Some(Expr::Bin(s, Box::new(l), Box::new(r)));
            }
        }
        Some(l)
    }
    fn add(&mut self) -> Option<Expr> {
        let mut l = self.mul()?;
        while let Some(s) = self.sym() {
            if s == "+" || s == "-" {
                self.pos += 1;
                let r = self.mul()?;
                l = Expr::Bin(s, Box::new(l), Box::new(r));
            } else {
                break;
            }
        }
        Some(l)
    }
    fn mul(&mut self) -> Option<Expr> {
        let mut l = self.rot()?;
        while let Some(s) = self.sym() {
            if s == "*" || s == "/" || s == "%" {
                self.pos += 1;
                let r = self.rot()?;
                l = Expr::Bin(s, Box::new(l), Box::new(r));
            } else {
                break;
            }
        }
        Some(l)
    }
    fn rot(&mut self) -> Option<Expr> {
        let l = self.unary()?;
        if self.sym() == Some("~") {
            self.pos += 1;
            let r = self.rot()?;
            return Some(Expr::Bin("~", Box::new(l), Box::new(r)));
        }
        Some(l)
    }
    fn unary(&mut self) -> Option<Expr> {
        match self.peek()?.clone() {
            Tok::Sym(s) if s == "-" || s == "#" || s == "!" => {
                self.pos += 1;
                let e = self.unary()?;
                Some(Expr::Un(s.as_bytes()[0], Box::new(e)))
            }
            Tok::Sym("(") => {
                self.pos += 1;
                self.depth += 1;
                if self.depth > 32 {
                    return None;
                }
                let e = self.expr()?;
                if self.sym() != Some(")") {
                    return None;
                }
                self.pos += 1;
                self.depth -= 1;
                Some(e)
            }
            Tok::Num(n) => {
                self.pos += 1;
                Some(Expr::Num(n))
            }
            Tok::Word(w) => {
                if KW.contains(&w.as_str()) {
                    return None;
                }
                self.pos += 1;
                let n = self.vars.len();
                let id = *self.vars.entry(w).or_insert(n);
                Some(Expr::Var(id))
            }
            _ => None,
        }
    }
}

enum Op {
    Set(usize, Expr),
    Out(Vec<Expr>),
    Loop(Expr, usize),
    When(Expr, usize),
    Else(usize),
    EndLoop(usize),
    EndWhen,
    Break(usize),
}

struct Blk {
    is_loop: bool,
    line: usize,
    start: usize,
    else_idx: Option<usize>,
}

fn parse_err(n: usize) -> ! {
    println!("parse error line {}", n);
    std::process::exit(2);
}

fn eval(e: &Expr, vals: &[u32], set: &[bool]) -> Result<u32, ()> {
    Ok(match e {
        Expr::Num(n) => *n,
        Expr::Var(i) => {
            if !set[*i] {
                return Err(());
            }
            vals[*i]
        }
        Expr::Un(c, x) => {
            let v = eval(x, vals, set)?;
            match c {
                b'-' => v.wrapping_neg(),
                b'#' => v.count_ones(),
                _ => (v == 0) as u32,
            }
        }
        Expr::Bin(op, a, b) => {
            let x = eval(a, vals, set)?;
            let y = eval(b, vals, set)?;
            match *op {
                "<>" => x.max(y),
                "><" => x.min(y),
                "==" => (x == y) as u32,
                "!=" => (x != y) as u32,
                "<" => (x < y) as u32,
                ">" => (x > y) as u32,
                "+" => x.wrapping_add(y),
                "-" => x.wrapping_sub(y),
                "*" => x.wrapping_mul(y),
                "/" => {
                    if y == 0 {
                        return Err(());
                    }
                    x / y
                }
                "%" => {
                    if y == 0 {
                        return Err(());
                    }
                    x % y
                }
                _ => x.rotate_left(y % 32),
            }
        }
    })
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        std::process::exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => std::process::exit(1),
    };
    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if let Some(l) = lines.last() {
        if l.is_empty() {
            lines.pop();
        }
    }
    let mut vars: HashMap<String, usize> = HashMap::new();
    let mut ops: Vec<Op> = Vec::new();
    let mut op_line: Vec<usize> = Vec::new();
    let mut stack: Vec<Blk> = Vec::new();
    // break patch lists per loop in stack
    let mut breaks: Vec<Vec<usize>> = Vec::new();
    for (li, raw) in lines.iter().enumerate() {
        let ln = li + 1;
        if raw.len() > 1000 {
            parse_err(ln);
        }
        if raw.iter().any(|&b| !(b == 9 || b == 13 || (0x20..=0x7e).contains(&b))) {
            parse_err(ln);
        }
        let body = match raw.iter().position(|&b| b == b';') {
            Some(p) => &raw[..p],
            None => raw,
        };
        let toks = match tokenize(body) {
            Some(t) => t,
            None => parse_err(ln),
        };
        if toks.is_empty() {
            continue;
        }
        let kw = match &toks[0] {
            Tok::Word(w) if KW.contains(&w.as_str()) => w.clone(),
            _ => parse_err(ln),
        };
        let rest = &toks[1..];
        let idx = ops.len();
        match kw.as_str() {
            "set" => {
                let name = match rest.get(0) {
                    Some(Tok::Word(w)) if !KW.contains(&w.as_str()) => w.clone(),
                    _ => parse_err(ln),
                };
                if rest.get(1) != Some(&Tok::Sym("=")) {
                    parse_err(ln);
                }
                let mut p = P { t: &rest[2..], pos: 0, depth: 0, vars: &mut vars };
                let e = match p.expr() {
                    Some(e) => e,
                    None => parse_err(ln),
                };
                if p.pos != p.t.len() {
                    parse_err(ln);
                }
                let n = vars.len();
                let id = *vars.entry(name).or_insert(n);
                ops.push(Op::Set(id, e));
            }
            "out" => {
                let mut p = P { t: rest, pos: 0, depth: 0, vars: &mut vars };
                let mut es = Vec::new();
                loop {
                    match p.expr() {
                        Some(e) => es.push(e),
                        None => parse_err(ln),
                    }
                    if p.sym() == Some(",") {
                        p.pos += 1;
                    } else {
                        break;
                    }
                }
                if p.pos != p.t.len() {
                    parse_err(ln);
                }
                ops.push(Op::Out(es));
            }
            "loop" | "when" => {
                let is_loop = kw == "loop";
                let mut p = P { t: rest, pos: 0, depth: 0, vars: &mut vars };
                let e = match p.expr() {
                    Some(e) => e,
                    None => parse_err(ln),
                };
                if p.pos != p.t.len() {
                    parse_err(ln);
                }
                if stack.len() >= 16 {
                    parse_err(ln);
                }
                stack.push(Blk { is_loop, line: ln, start: idx, else_idx: None });
                breaks.push(Vec::new());
                ops.push(if is_loop { Op::Loop(e, 0) } else { Op::When(e, 0) });
            }
            "else" => {
                if !rest.is_empty() {
                    parse_err(ln);
                }
                match stack.last_mut() {
                    Some(b) if !b.is_loop && b.else_idx.is_none() => {
                        b.else_idx = Some(idx);
                    }
                    _ => parse_err(ln),
                }
                ops.push(Op::Else(0));
            }
            "end" => {
                if !rest.is_empty() {
                    parse_err(ln);
                }
                let b = match stack.pop() {
                    Some(b) => b,
                    None => parse_err(ln),
                };
                let brk = breaks.pop().unwrap();
                if b.is_loop {
                    if let Op::Loop(_, ref mut t) = ops[b.start] {
                        *t = idx;
                    }
                    for bi in brk {
                        if let Op::Break(ref mut t) = ops[bi] {
                            *t = idx + 1;
                        }
                    }
                    ops.push(Op::EndLoop(b.start));
                } else {
                    // propagate breaks to enclosing loop list
                    if let Some(parent) = breaks.last_mut() {
                        parent.extend(brk);
                    }
                    if let Some(ei) = b.else_idx {
                        if let Op::When(_, ref mut t) = ops[b.start] {
                            *t = ei + 1;
                        }
                        if let Op::Else(ref mut t) = ops[ei] {
                            *t = idx;
                        }
                    } else if let Op::When(_, ref mut t) = ops[b.start] {
                        *t = idx;
                    }
                    ops.push(Op::EndWhen);
                }
            }
            _ => {
                // break
                if !rest.is_empty() {
                    parse_err(ln);
                }
                if !stack.iter().any(|b| b.is_loop) {
                    parse_err(ln);
                }
                // attach to the innermost loop: put in current list; when ends propagate up
                breaks.last_mut().unwrap().push(idx);
                ops.push(Op::Break(0));
            }
        }
        op_line.push(ln);
    }
    // note: breaks inside when propagate; a loop's list collects them at its end.
    if let Some(b) = stack.last() {
        parse_err(b.line);
    }

    let nv = vars.len();
    let mut vals = vec![0u32; nv];
    let mut isset = vec![false; nv];
    let mut counters: Vec<u32> = Vec::new();
    let mut out: Vec<u8> = Vec::new();
    let stdout = std::io::stdout();
    let mut pc = 0;
    let mut rt_err: Option<usize> = None;
    while pc < ops.len() {
        match &ops[pc] {
            Op::Set(id, e) => match eval(e, &vals, &isset) {
                Ok(v) => {
                    vals[*id] = v;
                    isset[*id] = true;
                    pc += 1;
                }
                Err(_) => {
                    rt_err = Some(op_line[pc]);
                    break;
                }
            },
            Op::Out(es) => {
                let mut tmp = Vec::with_capacity(es.len());
                let mut bad = false;
                for e in es {
                    match eval(e, &vals, &isset) {
                        Ok(v) => tmp.push(v),
                        Err(_) => {
                            bad = true;
                            break;
                        }
                    }
                }
                if bad {
                    rt_err = Some(op_line[pc]);
                    break;
                }
                let s: Vec<String> = tmp.iter().map(|v| v.to_string()).collect();
                out.extend_from_slice(s.join(" ").as_bytes());
                out.push(b'\n');
                if out.len() > 1 << 16 {
                    let _ = stdout.lock().write_all(&out);
                    out.clear();
                }
                pc += 1;
            }
            Op::Loop(e, end) => match eval(e, &vals, &isset) {
                Ok(0) => pc = end + 1,
                Ok(n) => {
                    counters.push(n);
                    pc += 1;
                }
                Err(_) => {
                    rt_err = Some(op_line[pc]);
                    break;
                }
            },
            Op::When(e, t) => match eval(e, &vals, &isset) {
                Ok(0) => pc = *t,
                Ok(_) => pc += 1,
                Err(_) => {
                    rt_err = Some(op_line[pc]);
                    break;
                }
            },
            Op::Else(t) => pc = *t,
            Op::EndWhen => pc += 1,
            Op::EndLoop(start) => {
                let c = counters.last_mut().unwrap();
                *c -= 1;
                if *c > 0 {
                    pc = start + 1;
                } else {
                    counters.pop();
                    pc += 1;
                }
            }
            Op::Break(t) => {
                counters.pop();
                pc = *t;
            }
        }
    }
    let mut so = stdout.lock();
    let _ = so.write_all(&out);
    if let Some(l) = rt_err {
        let _ = writeln!(so, "runtime error line {}", l);
        let _ = so.flush();
        std::process::exit(3);
    }
    let _ = so.flush();
}
