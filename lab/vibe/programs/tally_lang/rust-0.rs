use std::collections::HashMap;
use std::io::{self, Write};
use std::process::exit;

#[derive(Clone)]
enum Tok {
    Num(u32),
    Word(String),
    Op(&'static str),
}

fn is_keyword(w: &str) -> bool {
    matches!(w, "set" | "out" | "loop" | "when" | "else" | "end" | "break")
}

fn tokenize(s: &[u8]) -> Result<Vec<Tok>, ()> {
    let n = s.len();
    let mut i = 0usize;
    let mut toks: Vec<Tok> = Vec::new();
    while i < n {
        let c = s[i];
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
            continue;
        }
        if c.is_ascii_digit() {
            let mut val: u64 = 0;
            while i < n && s[i].is_ascii_digit() {
                val = val * 10 + (s[i] - b'0') as u64;
                if val > 4_294_967_295 {
                    return Err(());
                }
                i += 1;
            }
            if i < n {
                let d = s[i];
                if d.is_ascii_lowercase() || d == b'_' {
                    return Err(());
                }
            }
            toks.push(Tok::Num(val as u32));
            continue;
        }
        if c.is_ascii_lowercase() || c == b'_' {
            let start = i;
            i += 1;
            while i < n {
                let d = s[i];
                if d.is_ascii_lowercase() || d.is_ascii_digit() || d == b'_' {
                    i += 1;
                } else {
                    break;
                }
            }
            let w = std::str::from_utf8(&s[start..i]).map_err(|_| ())?.to_string();
            toks.push(Tok::Word(w));
            continue;
        }
        if i + 1 < n {
            let pair = (s[i], s[i + 1]);
            let op: Option<&'static str> = match pair {
                (b'<', b'>') => Some("<>"),
                (b'>', b'<') => Some("><"),
                (b'=', b'=') => Some("=="),
                (b'!', b'=') => Some("!="),
                _ => None,
            };
            if let Some(op) = op {
                toks.push(Tok::Op(op));
                i += 2;
                continue;
            }
        }
        let op: Option<&'static str> = match c {
            b'<' => Some("<"),
            b'>' => Some(">"),
            b'+' => Some("+"),
            b'-' => Some("-"),
            b'*' => Some("*"),
            b'/' => Some("/"),
            b'%' => Some("%"),
            b'~' => Some("~"),
            b'#' => Some("#"),
            b'!' => Some("!"),
            b'(' => Some("("),
            b')' => Some(")"),
            b',' => Some(","),
            b'=' => Some("="),
            _ => None,
        };
        match op {
            Some(op) => {
                toks.push(Tok::Op(op));
                i += 1;
            }
            None => return Err(()),
        }
    }
    Ok(toks)
}

const B_MAX: u8 = 1;
const B_MIN: u8 = 2;
const B_EQ: u8 = 3;
const B_NE: u8 = 4;
const B_LT: u8 = 5;
const B_GT: u8 = 6;
const B_ADD: u8 = 7;
const B_SUB: u8 = 8;
const B_MUL: u8 = 9;
const B_DIV: u8 = 10;
const B_MOD: u8 = 11;
const B_ROT: u8 = 12;
const U_NEG: u8 = 20;
const U_BITS: u8 = 21;
const U_NOT: u8 = 22;

enum Expr {
    Num(u32),
    Var(String),
    Unary(u8, Box<Expr>),
    Bin(u8, Box<Expr>, Box<Expr>),
}

struct P<'a> {
    t: &'a [Tok],
    i: usize,
    depth: usize,
}

impl<'a> P<'a> {
    fn op_at(&self, i: usize) -> Option<&'static str> {
        match self.t.get(i) {
            Some(Tok::Op(o)) => Some(*o),
            _ => None,
        }
    }

    fn parse_expr(&mut self) -> Result<Expr, ()> {
        self.parse_l1()
    }

    fn parse_l1(&mut self) -> Result<Expr, ()> {
        let mut e = self.parse_l2()?;
        loop {
            let code = match self.op_at(self.i) {
                Some("<>") => Some(B_MAX),
                Some("><") => Some(B_MIN),
                _ => None,
            };
            match code {
                Some(c) => {
                    self.i += 1;
                    let r = self.parse_l2()?;
                    e = Expr::Bin(c, Box::new(e), Box::new(r));
                }
                None => break,
            }
        }
        Ok(e)
    }

    fn parse_l2(&mut self) -> Result<Expr, ()> {
        let e = self.parse_l3()?;
        let code = match self.op_at(self.i) {
            Some("==") => Some(B_EQ),
            Some("!=") => Some(B_NE),
            Some("<") => Some(B_LT),
            Some(">") => Some(B_GT),
            _ => None,
        };
        if let Some(c) = code {
            self.i += 1;
            let r = self.parse_l3()?;
            Ok(Expr::Bin(c, Box::new(e), Box::new(r)))
        } else {
            Ok(e)
        }
    }

    fn parse_l3(&mut self) -> Result<Expr, ()> {
        let mut e = self.parse_l4()?;
        loop {
            let code = match self.op_at(self.i) {
                Some("+") => Some(B_ADD),
                Some("-") => Some(B_SUB),
                _ => None,
            };
            match code {
                Some(c) => {
                    self.i += 1;
                    let r = self.parse_l4()?;
                    e = Expr::Bin(c, Box::new(e), Box::new(r));
                }
                None => break,
            }
        }
        Ok(e)
    }

    fn parse_l4(&mut self) -> Result<Expr, ()> {
        let mut e = self.parse_l5()?;
        loop {
            let code = match self.op_at(self.i) {
                Some("*") => Some(B_MUL),
                Some("/") => Some(B_DIV),
                Some("%") => Some(B_MOD),
                _ => None,
            };
            match code {
                Some(c) => {
                    self.i += 1;
                    let r = self.parse_l5()?;
                    e = Expr::Bin(c, Box::new(e), Box::new(r));
                }
                None => break,
            }
        }
        Ok(e)
    }

    fn parse_l5(&mut self) -> Result<Expr, ()> {
        let e = self.parse_l6()?;
        if self.op_at(self.i) == Some("~") {
            self.i += 1;
            let r = self.parse_l5()?;
            Ok(Expr::Bin(B_ROT, Box::new(e), Box::new(r)))
        } else {
            Ok(e)
        }
    }

    fn parse_l6(&mut self) -> Result<Expr, ()> {
        let code = match self.op_at(self.i) {
            Some("-") => Some(U_NEG),
            Some("#") => Some(U_BITS),
            Some("!") => Some(U_NOT),
            _ => None,
        };
        if let Some(c) = code {
            self.i += 1;
            let operand = self.parse_l6()?;
            Ok(Expr::Unary(c, Box::new(operand)))
        } else {
            self.parse_l7()
        }
    }

    fn parse_l7(&mut self) -> Result<Expr, ()> {
        if self.op_at(self.i) == Some("(") {
            if self.depth >= 32 {
                return Err(());
            }
            self.depth += 1;
            self.i += 1;
            let e = self.parse_expr()?;
            if self.op_at(self.i) != Some(")") {
                return Err(());
            }
            self.i += 1;
            self.depth -= 1;
            return Ok(e);
        }
        let tok = self.t.get(self.i).cloned();
        match tok {
            Some(Tok::Num(n)) => {
                self.i += 1;
                Ok(Expr::Num(n))
            }
            Some(Tok::Word(w)) => {
                if is_keyword(&w) {
                    return Err(());
                }
                self.i += 1;
                Ok(Expr::Var(w))
            }
            _ => Err(()),
        }
    }
}

enum Line {
    Set(String, Expr),
    Out(Vec<Expr>),
    LoopStart(Expr),
    WhenStart(Expr),
    Else,
    End,
    Break,
}

fn parse_statement(toks: &[Tok]) -> Result<Line, ()> {
    let first: &str = match toks.get(0) {
        Some(Tok::Word(w)) => w.as_str(),
        _ => return Err(()),
    };
    match first {
        "set" => {
            let name = match toks.get(1) {
                Some(Tok::Word(w)) if !is_keyword(w) => w.clone(),
                _ => return Err(()),
            };
            let mut p = P { t: toks, i: 2, depth: 0 };
            if p.op_at(p.i) != Some("=") {
                return Err(());
            }
            p.i += 1;
            let e = p.parse_expr()?;
            if p.i != toks.len() {
                return Err(());
            }
            Ok(Line::Set(name, e))
        }
        "out" => {
            let mut p = P { t: toks, i: 1, depth: 0 };
            let mut es = vec![p.parse_expr()?];
            while p.op_at(p.i) == Some(",") {
                p.i += 1;
                es.push(p.parse_expr()?);
            }
            if p.i != toks.len() {
                return Err(());
            }
            Ok(Line::Out(es))
        }
        "loop" => {
            let mut p = P { t: toks, i: 1, depth: 0 };
            let e = p.parse_expr()?;
            if p.i != toks.len() {
                return Err(());
            }
            Ok(Line::LoopStart(e))
        }
        "when" => {
            let mut p = P { t: toks, i: 1, depth: 0 };
            let e = p.parse_expr()?;
            if p.i != toks.len() {
                return Err(());
            }
            Ok(Line::WhenStart(e))
        }
        "else" => {
            if toks.len() == 1 { Ok(Line::Else) } else { Err(()) }
        }
        "end" => {
            if toks.len() == 1 { Ok(Line::End) } else { Err(()) }
        }
        "break" => {
            if toks.len() == 1 { Ok(Line::Break) } else { Err(()) }
        }
        _ => Err(()),
    }
}

enum Stmt {
    Set(String, Expr, usize),
    Out(Vec<Expr>, usize),
    Loop(Expr, Vec<Stmt>, usize),
    When(Expr, Vec<Stmt>, Option<Vec<Stmt>>, usize),
    Break,
}

enum Frame {
    Loop {
        expr: Expr,
        line: usize,
        body: Vec<Stmt>,
    },
    When {
        expr: Expr,
        line: usize,
        then_body: Vec<Stmt>,
        else_body: Option<Vec<Stmt>>,
    },
}

fn push_stmt(frames: &mut Vec<Frame>, top: &mut Vec<Stmt>, s: Stmt) {
    match frames.last_mut() {
        None => top.push(s),
        Some(Frame::Loop { body, .. }) => body.push(s),
        Some(Frame::When {
            then_body,
            else_body,
            ..
        }) => match else_body {
            Some(b) => b.push(s),
            None => then_body.push(s),
        },
    }
}

fn parse_err(line: usize) -> ! {
    println!("parse error line {}", line);
    let _ = io::stdout().flush();
    exit(2);
}

enum Flow {
    Normal,
    Break,
}

fn eval(e: &Expr, vars: &HashMap<String, u32>) -> Result<u32, ()> {
    match e {
        Expr::Num(n) => Ok(*n),
        Expr::Var(name) => vars.get(name).copied().ok_or(()),
        Expr::Unary(op, x) => {
            let v = eval(x, vars)?;
            match *op {
                U_NEG => Ok(v.wrapping_neg()),
                U_BITS => Ok(v.count_ones()),
                U_NOT => Ok(if v == 0 { 1 } else { 0 }),
                _ => Err(()),
            }
        }
        Expr::Bin(op, a, b) => {
            let l = eval(a, vars)?;
            let r = eval(b, vars)?;
            match *op {
                B_MAX => Ok(if l > r { l } else { r }),
                B_MIN => Ok(if l < r { l } else { r }),
                B_EQ => Ok(if l == r { 1 } else { 0 }),
                B_NE => Ok(if l != r { 1 } else { 0 }),
                B_LT => Ok(if l < r { 1 } else { 0 }),
                B_GT => Ok(if l > r { 1 } else { 0 }),
                B_ADD => Ok(l.wrapping_add(r)),
                B_SUB => Ok(l.wrapping_sub(r)),
                B_MUL => Ok(l.wrapping_mul(r)),
                B_DIV => {
                    if r == 0 {
                        Err(())
                    } else {
                        Ok(l / r)
                    }
                }
                B_MOD => {
                    if r == 0 {
                        Err(())
                    } else {
                        Ok(l % r)
                    }
                }
                B_ROT => Ok(l.rotate_left(r % 32)),
                _ => Err(()),
            }
        }
    }
}

fn exec(
    stmts: &[Stmt],
    vars: &mut HashMap<String, u32>,
    out: &mut dyn Write,
) -> Result<Flow, usize> {
    for s in stmts {
        match s {
            Stmt::Set(name, e, line) => {
                let v = eval(e, vars).map_err(|_| *line)?;
                vars.insert(name.clone(), v);
            }
            Stmt::Out(es, line) => {
                let mut vals = Vec::with_capacity(es.len());
                for e in es {
                    vals.push(eval(e, vars).map_err(|_| *line)?);
                }
                for (k, v) in vals.iter().enumerate() {
                    if k > 0 {
                        write!(out, " ").unwrap();
                    }
                    write!(out, "{}", v).unwrap();
                }
                writeln!(out).unwrap();
            }
            Stmt::Loop(e, body, line) => {
                let n = eval(e, vars).map_err(|_| *line)?;
                for _ in 0..n {
                    if let Flow::Break = exec(body, vars, out)? {
                        break;
                    }
                }
            }
            Stmt::When(e, then_body, else_body, line) => {
                let c = eval(e, vars).map_err(|_| *line)?;
                let flow = if c != 0 {
                    exec(then_body, vars, out)?
                } else if let Some(eb) = else_body {
                    exec(eb, vars, out)?
                } else {
                    Flow::Normal
                };
                if let Flow::Break = flow {
                    return Ok(Flow::Break);
                }
            }
            Stmt::Break => return Ok(Flow::Break),
        }
    }
    Ok(Flow::Normal)
}

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    if args.len() != 2 {
        exit(1);
    }
    let content = match std::fs::read(&args[1]) {
        Ok(c) => c,
        Err(_) => exit(1),
    };

    let mut lines: Vec<&[u8]> = content.split(|&b| b == b'\n').collect();
    if content.last() == Some(&b'\n') {
        lines.pop();
    }

    let mut top: Vec<Stmt> = Vec::new();
    let mut frames: Vec<Frame> = Vec::new();

    for (idx, raw) in lines.iter().enumerate() {
        let ln = idx + 1;
        if raw.len() > 1000 {
            parse_err(ln);
        }
        for &b in raw.iter() {
            if !(b == b'\t' || b == b'\r' || (b >= 0x20 && b <= 0x7E)) {
                parse_err(ln);
            }
        }
        let mut cut = raw.len();
        for (j, &b) in raw.iter().enumerate() {
            if b == b';' {
                cut = j;
                break;
            }
        }
        let body = &raw[..cut];
        let toks = match tokenize(body) {
            Ok(t) => t,
            Err(_) => parse_err(ln),
        };
        if toks.is_empty() {
            continue;
        }
        let action = match parse_statement(&toks) {
            Ok(a) => a,
            Err(_) => parse_err(ln),
        };
        match action {
            Line::Set(name, e) => push_stmt(&mut frames, &mut top, Stmt::Set(name, e, ln)),
            Line::Out(es) => push_stmt(&mut frames, &mut top, Stmt::Out(es, ln)),
            Line::LoopStart(e) => {
                if frames.len() >= 16 {
                    parse_err(ln);
                }
                frames.push(Frame::Loop {
                    expr: e,
                    line: ln,
                    body: Vec::new(),
                });
            }
            Line::WhenStart(e) => {
                if frames.len() >= 16 {
                    parse_err(ln);
                }
                frames.push(Frame::When {
                    expr: e,
                    line: ln,
                    then_body: Vec::new(),
                    else_body: None,
                });
            }
            Line::Else => match frames.last_mut() {
                Some(Frame::When { else_body, .. }) => {
                    if else_body.is_some() {
                        parse_err(ln);
                    }
                    *else_body = Some(Vec::new());
                }
                _ => parse_err(ln),
            },
            Line::End => match frames.pop() {
                None => parse_err(ln),
                Some(f) => {
                    let s = match f {
                        Frame::Loop { expr, line, body } => Stmt::Loop(expr, body, line),
                        Frame::When {
                            expr,
                            line,
                            then_body,
                            else_body,
                        } => Stmt::When(expr, then_body, else_body, line),
                    };
                    push_stmt(&mut frames, &mut top, s);
                }
            },
            Line::Break => {
                if !frames.iter().any(|f| matches!(f, Frame::Loop { .. })) {
                    parse_err(ln);
                }
                push_stmt(&mut frames, &mut top, Stmt::Break);
            }
        }
    }

    if let Some(f) = frames.last() {
        let ln = match f {
            Frame::Loop { line, .. } => *line,
            Frame::When { line, .. } => *line,
        };
        parse_err(ln);
    }

    let stdout = io::stdout();
    let mut w = io::BufWriter::new(stdout.lock());
    let mut vars: HashMap<String, u32> = HashMap::new();
    match exec(&top, &mut vars, &mut w) {
        Ok(_) => {
            let _ = w.flush();
        }
        Err(line) => {
            let _ = writeln!(w, "runtime error line {}", line);
            let _ = w.flush();
            exit(3);
        }
    }
}
