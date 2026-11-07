use std::collections::HashMap;
use std::ffi::OsString;
use std::io::{self, Write};
use std::process::exit;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Op {
    LtGt, GtLt, EqEq, NotEq, Lt, Gt,
    Plus, Minus, Star, Slash, Percent,
    Tilde, Hash, Bang, LParen, RParen, Comma, Assign,
}

#[derive(Clone)]
enum Tok {
    Num(u32),
    Word(String),
    Op(Op),
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum BinOp { Max, Min, Eq, Ne, Lt, Gt, Add, Sub, Mul, Div, Mod, Rot }

enum Expr {
    Num(u32),
    Var(String),
    Bin(BinOp, Box<Expr>, Box<Expr>),
    Neg(Box<Expr>),
    Bits(Box<Expr>),
    Not(Box<Expr>),
}

enum Line {
    Set(String, Expr),
    Out(Vec<Expr>),
    Loop(Expr),
    When(Expr),
    Else,
    End,
    Break,
}

enum Stmt {
    Set { line: usize, name: String, expr: Expr },
    Out { line: usize, exprs: Vec<Expr> },
    Loop { line: usize, expr: Expr, body: Vec<Stmt> },
    When { line: usize, expr: Expr, then: Vec<Stmt>, els: Vec<Stmt> },
    Break,
}

enum Building {
    Loop { line: usize, expr: Expr, body: Vec<Stmt> },
    When { line: usize, expr: Expr, then: Vec<Stmt>, has_else: bool, els: Vec<Stmt> },
}

enum Flow { Normal, Break }

fn is_keyword(w: &str) -> bool {
    matches!(w, "set" | "out" | "loop" | "when" | "else" | "end" | "break")
}

struct Parser<'a> {
    toks: &'a [Tok],
    pos: usize,
    depth: usize,
}

impl<'a> Parser<'a> {
    fn new(toks: &'a [Tok]) -> Self {
        Parser { toks, pos: 0, depth: 0 }
    }

    fn peek_op(&self) -> Option<Op> {
        match self.toks.get(self.pos) {
            Some(Tok::Op(o)) => Some(*o),
            _ => None,
        }
    }

    fn at_end(&self) -> bool {
        self.pos >= self.toks.len()
    }

    fn parse_expr(&mut self) -> Result<Expr, ()> {
        self.parse_l1()
    }

    fn parse_l1(&mut self) -> Result<Expr, ()> {
        let mut left = self.parse_l2()?;
        loop {
            let op = match self.peek_op() {
                Some(Op::LtGt) => BinOp::Max,
                Some(Op::GtLt) => BinOp::Min,
                _ => break,
            };
            self.pos += 1;
            let right = self.parse_l2()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn parse_l2(&mut self) -> Result<Expr, ()> {
        let left = self.parse_l3()?;
        let op = match self.peek_op() {
            Some(Op::EqEq) => Some(BinOp::Eq),
            Some(Op::NotEq) => Some(BinOp::Ne),
            Some(Op::Lt) => Some(BinOp::Lt),
            Some(Op::Gt) => Some(BinOp::Gt),
            _ => None,
        };
        match op {
            None => Ok(left),
            Some(op) => {
                self.pos += 1;
                let right = self.parse_l3()?;
                match self.peek_op() {
                    Some(Op::EqEq) | Some(Op::NotEq) | Some(Op::Lt) | Some(Op::Gt) => Err(()),
                    _ => Ok(Expr::Bin(op, Box::new(left), Box::new(right))),
                }
            }
        }
    }

    fn parse_l3(&mut self) -> Result<Expr, ()> {
        let mut left = self.parse_l4()?;
        loop {
            let op = match self.peek_op() {
                Some(Op::Plus) => BinOp::Add,
                Some(Op::Minus) => BinOp::Sub,
                _ => break,
            };
            self.pos += 1;
            let right = self.parse_l4()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn parse_l4(&mut self) -> Result<Expr, ()> {
        let mut left = self.parse_l5()?;
        loop {
            let op = match self.peek_op() {
                Some(Op::Star) => BinOp::Mul,
                Some(Op::Slash) => BinOp::Div,
                Some(Op::Percent) => BinOp::Mod,
                _ => break,
            };
            self.pos += 1;
            let right = self.parse_l5()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn parse_l5(&mut self) -> Result<Expr, ()> {
        let left = self.parse_l6()?;
        if self.peek_op() == Some(Op::Tilde) {
            self.pos += 1;
            let right = self.parse_l5()?;
            Ok(Expr::Bin(BinOp::Rot, Box::new(left), Box::new(right)))
        } else {
            Ok(left)
        }
    }

    fn parse_l6(&mut self) -> Result<Expr, ()> {
        let mut prefixes: Vec<u8> = Vec::new();
        loop {
            match self.peek_op() {
                Some(Op::Minus) => { prefixes.push(b'-'); self.pos += 1; }
                Some(Op::Hash) => { prefixes.push(b'#'); self.pos += 1; }
                Some(Op::Bang) => { prefixes.push(b'!'); self.pos += 1; }
                _ => break,
            }
        }
        let mut e = self.parse_l7()?;
        for &p in prefixes.iter().rev() {
            e = match p {
                b'-' => Expr::Neg(Box::new(e)),
                b'#' => Expr::Bits(Box::new(e)),
                _ => Expr::Not(Box::new(e)),
            };
        }
        Ok(e)
    }

    fn parse_l7(&mut self) -> Result<Expr, ()> {
        match self.toks.get(self.pos) {
            Some(Tok::Num(n)) => {
                let v = *n;
                self.pos += 1;
                Ok(Expr::Num(v))
            }
            Some(Tok::Word(w)) => {
                if is_keyword(w) {
                    return Err(());
                }
                let v = w.clone();
                self.pos += 1;
                Ok(Expr::Var(v))
            }
            Some(Tok::Op(Op::LParen)) => {
                self.depth += 1;
                if self.depth > 32 {
                    return Err(());
                }
                self.pos += 1;
                let e = self.parse_l1()?;
                if self.peek_op() != Some(Op::RParen) {
                    return Err(());
                }
                self.pos += 1;
                self.depth -= 1;
                Ok(e)
            }
            _ => Err(()),
        }
    }
}

fn tokenize(line: &[u8]) -> Result<Vec<Tok>, ()> {
    let mut toks = Vec::new();
    let mut i = 0usize;
    while i < line.len() {
        let c = line[i];
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
            continue;
        }
        if c.is_ascii_digit() {
            let start = i;
            while i < line.len() && line[i].is_ascii_digit() {
                i += 1;
            }
            let mut val: u64 = 0;
            for &d in &line[start..i] {
                val = val * 10 + (d - b'0') as u64;
                if val > 4294967295 {
                    return Err(());
                }
            }
            if i < line.len() && (line[i].is_ascii_lowercase() || line[i] == b'_') {
                return Err(());
            }
            toks.push(Tok::Num(val as u32));
            continue;
        }
        if c.is_ascii_lowercase() || c == b'_' {
            let start = i;
            i += 1;
            while i < line.len()
                && (line[i].is_ascii_lowercase() || line[i].is_ascii_digit() || line[i] == b'_')
            {
                i += 1;
            }
            let s = std::str::from_utf8(&line[start..i]).unwrap().to_string();
            toks.push(Tok::Word(s));
            continue;
        }
        if i + 1 < line.len() {
            let two = &line[i..i + 2];
            let op = match two {
                b"<>" => Some(Op::LtGt),
                b"><" => Some(Op::GtLt),
                b"==" => Some(Op::EqEq),
                b"!=" => Some(Op::NotEq),
                _ => None,
            };
            if let Some(o) = op {
                toks.push(Tok::Op(o));
                i += 2;
                continue;
            }
        }
        let op = match c {
            b'<' => Op::Lt,
            b'>' => Op::Gt,
            b'+' => Op::Plus,
            b'-' => Op::Minus,
            b'*' => Op::Star,
            b'/' => Op::Slash,
            b'%' => Op::Percent,
            b'~' => Op::Tilde,
            b'#' => Op::Hash,
            b'!' => Op::Bang,
            b'(' => Op::LParen,
            b')' => Op::RParen,
            b',' => Op::Comma,
            b'=' => Op::Assign,
            _ => return Err(()),
        };
        toks.push(Tok::Op(op));
        i += 1;
    }
    Ok(toks)
}

fn parse_line(toks: &[Tok]) -> Result<Option<Line>, ()> {
    if toks.is_empty() {
        return Ok(None);
    }
    let kw = match &toks[0] {
        Tok::Word(w) => w.as_str(),
        _ => return Err(()),
    };
    let mut p = Parser::new(toks);
    p.pos = 1;
    let line = match kw {
        "set" => {
            let name = match toks.get(1) {
                Some(Tok::Word(w)) if !is_keyword(w) => w.clone(),
                _ => return Err(()),
            };
            p.pos = 2;
            if p.peek_op() != Some(Op::Assign) {
                return Err(());
            }
            p.pos += 1;
            let e = p.parse_expr()?;
            if !p.at_end() {
                return Err(());
            }
            Line::Set(name, e)
        }
        "out" => {
            let mut exprs = Vec::new();
            exprs.push(p.parse_expr()?);
            while p.peek_op() == Some(Op::Comma) {
                p.pos += 1;
                exprs.push(p.parse_expr()?);
            }
            if !p.at_end() {
                return Err(());
            }
            Line::Out(exprs)
        }
        "loop" => {
            let e = p.parse_expr()?;
            if !p.at_end() {
                return Err(());
            }
            Line::Loop(e)
        }
        "when" => {
            let e = p.parse_expr()?;
            if !p.at_end() {
                return Err(());
            }
            Line::When(e)
        }
        "else" => {
            if !p.at_end() {
                return Err(());
            }
            Line::Else
        }
        "end" => {
            if !p.at_end() {
                return Err(());
            }
            Line::End
        }
        "break" => {
            if !p.at_end() {
                return Err(());
            }
            Line::Break
        }
        _ => return Err(()),
    };
    Ok(Some(line))
}

fn push_stmt(stack: &mut Vec<Building>, top: &mut Vec<Stmt>, s: Stmt) {
    match stack.last_mut() {
        None => top.push(s),
        Some(Building::Loop { body, .. }) => body.push(s),
        Some(Building::When { then, has_else, els, .. }) => {
            if *has_else {
                els.push(s);
            } else {
                then.push(s);
            }
        }
    }
}

fn parse_script(data: &[u8]) -> Result<Vec<Stmt>, usize> {
    let mut lines: Vec<&[u8]> = Vec::new();
    let mut start = 0usize;
    for i in 0..data.len() {
        if data[i] == b'\n' {
            lines.push(&data[start..i]);
            start = i + 1;
        }
    }
    if start < data.len() {
        lines.push(&data[start..]);
    }

    let mut stack: Vec<Building> = Vec::new();
    let mut top: Vec<Stmt> = Vec::new();

    for (idx, raw) in lines.iter().enumerate() {
        let lineno = idx + 1;
        if raw.len() > 1000 {
            return Err(lineno);
        }
        for &b in raw.iter() {
            if !(b == b'\t' || b == b'\r' || (0x20..=0x7E).contains(&b)) {
                return Err(lineno);
            }
        }
        let mut end = raw.len();
        for (i, &b) in raw.iter().enumerate() {
            if b == b';' {
                end = i;
                break;
            }
        }
        let text = &raw[..end];
        let toks = match tokenize(text) {
            Ok(t) => t,
            Err(_) => return Err(lineno),
        };
        if toks.is_empty() {
            continue;
        }
        let parsed = match parse_line(&toks) {
            Ok(Some(l)) => l,
            _ => return Err(lineno),
        };
        match parsed {
            Line::Set(n, e) => {
                push_stmt(&mut stack, &mut top, Stmt::Set { line: lineno, name: n, expr: e });
            }
            Line::Out(es) => {
                push_stmt(&mut stack, &mut top, Stmt::Out { line: lineno, exprs: es });
            }
            Line::Break => {
                let inside_loop = stack.iter().any(|b| matches!(b, Building::Loop { .. }));
                if !inside_loop {
                    return Err(lineno);
                }
                push_stmt(&mut stack, &mut top, Stmt::Break);
            }
            Line::Loop(e) => {
                if stack.len() >= 16 {
                    return Err(lineno);
                }
                stack.push(Building::Loop { line: lineno, expr: e, body: Vec::new() });
            }
            Line::When(e) => {
                if stack.len() >= 16 {
                    return Err(lineno);
                }
                stack.push(Building::When {
                    line: lineno,
                    expr: e,
                    then: Vec::new(),
                    has_else: false,
                    els: Vec::new(),
                });
            }
            Line::Else => match stack.last_mut() {
                Some(Building::When { has_else, .. }) if !*has_else => {
                    *has_else = true;
                }
                _ => return Err(lineno),
            },
            Line::End => match stack.pop() {
                None => return Err(lineno),
                Some(Building::Loop { line, expr, body }) => {
                    push_stmt(&mut stack, &mut top, Stmt::Loop { line, expr, body });
                }
                Some(Building::When { line, expr, then, els, .. }) => {
                    push_stmt(&mut stack, &mut top, Stmt::When { line, expr, then, els });
                }
            },
        }
    }

    if let Some(b) = stack.last() {
        let l = match b {
            Building::Loop { line, .. } => *line,
            Building::When { line, .. } => *line,
        };
        return Err(l);
    }

    Ok(top)
}

fn eval(e: &Expr, vars: &HashMap<String, u32>) -> Result<u32, ()> {
    match e {
        Expr::Num(n) => Ok(*n),
        Expr::Var(name) => vars.get(name).copied().ok_or(()),
        Expr::Neg(a) => {
            let v = eval(a, vars)?;
            Ok(0u32.wrapping_sub(v))
        }
        Expr::Bits(a) => {
            let v = eval(a, vars)?;
            Ok(v.count_ones())
        }
        Expr::Not(a) => {
            let v = eval(a, vars)?;
            Ok(if v == 0 { 1 } else { 0 })
        }
        Expr::Bin(op, a, b) => {
            let x = eval(a, vars)?;
            let y = eval(b, vars)?;
            match op {
                BinOp::Max => Ok(x.max(y)),
                BinOp::Min => Ok(x.min(y)),
                BinOp::Eq => Ok((x == y) as u32),
                BinOp::Ne => Ok((x != y) as u32),
                BinOp::Lt => Ok((x < y) as u32),
                BinOp::Gt => Ok((x > y) as u32),
                BinOp::Add => Ok(x.wrapping_add(y)),
                BinOp::Sub => Ok(x.wrapping_sub(y)),
                BinOp::Mul => Ok(x.wrapping_mul(y)),
                BinOp::Div => {
                    if y == 0 { Err(()) } else { Ok(x / y) }
                }
                BinOp::Mod => {
                    if y == 0 { Err(()) } else { Ok(x % y) }
                }
                BinOp::Rot => Ok(x.rotate_left(y % 32)),
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
            Stmt::Set { line, name, expr } => {
                let v = eval(expr, vars).map_err(|_| *line)?;
                vars.insert(name.clone(), v);
            }
            Stmt::Out { line, exprs } => {
                let mut vals = Vec::with_capacity(exprs.len());
                for e in exprs {
                    vals.push(eval(e, vars).map_err(|_| *line)?);
                }
                let mut buf = String::new();
                for (i, v) in vals.iter().enumerate() {
                    if i > 0 {
                        buf.push(' ');
                    }
                    buf.push_str(&v.to_string());
                }
                buf.push('\n');
                let _ = out.write_all(buf.as_bytes());
            }
            Stmt::Loop { line, expr, body } => {
                let n = eval(expr, vars).map_err(|_| *line)?;
                if !body.is_empty() {
                    for _ in 0..n {
                        if let Flow::Break = exec(body, vars, &mut *out)? {
                            break;
                        }
                    }
                }
            }
            Stmt::When { line, expr, then, els } => {
                let c = eval(expr, vars).map_err(|_| *line)?;
                let body = if c != 0 { then } else { els };
                if let Flow::Break = exec(body, vars, &mut *out)? {
                    return Ok(Flow::Break);
                }
            }
            Stmt::Break => return Ok(Flow::Break),
        }
    }
    Ok(Flow::Normal)
}

fn main() {
    let args: Vec<OsString> = std::env::args_os().collect();
    if args.len() != 2 {
        exit(1);
    }
    let data = match std::fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => exit(1),
    };
    let stmts = match parse_script(&data) {
        Ok(s) => s,
        Err(n) => {
            println!("parse error line {}", n);
            let _ = io::stdout().flush();
            exit(2);
        }
    };

    let mut vars: HashMap<String, u32> = HashMap::new();
    let result;
    {
        let stdout = io::stdout();
        let mut out = io::BufWriter::new(stdout.lock());
        result = exec(&stmts, &mut vars, &mut out);
        let _ = out.flush();
    }
    if let Err(n) = result {
        println!("runtime error line {}", n);
        let _ = io::stdout().flush();
        exit(3);
    }
}
