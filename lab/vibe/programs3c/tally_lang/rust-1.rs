use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, Write};
use std::process;

#[derive(Clone, Copy)]
enum BinOp {
    Max,
    Min,
    Eq,
    Ne,
    Lt,
    Gt,
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Rot,
}

enum Expr {
    Num(u32),
    Var(String),
    Neg(Box<Expr>),
    Pop(Box<Expr>),
    Not(Box<Expr>),
    Bin(BinOp, Box<Expr>, Box<Expr>),
}

#[derive(Clone)]
enum Tok {
    Num(u32),
    Ident(String),
    Sym(&'static str),
}

const KEYWORDS: [&str; 7] = ["set", "out", "loop", "when", "else", "end", "break"];

fn is_kw(s: &str) -> bool {
    KEYWORDS.contains(&s)
}

fn tokenize(b: &[u8]) -> Option<Vec<Tok>> {
    let mut toks = Vec::new();
    let n = b.len();
    let mut i = 0;
    while i < n {
        let c = b[i];
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
            continue;
        }
        if c.is_ascii_digit() {
            let mut val: u64 = 0;
            while i < n && b[i].is_ascii_digit() {
                val = val * 10 + (b[i] - b'0') as u64;
                if val > u32::MAX as u64 {
                    return None;
                }
                i += 1;
            }
            if i < n && (b[i].is_ascii_lowercase() || b[i] == b'_') {
                return None;
            }
            toks.push(Tok::Num(val as u32));
            continue;
        }
        if c.is_ascii_lowercase() || c == b'_' {
            let start = i;
            i += 1;
            while i < n && (b[i].is_ascii_lowercase() || b[i].is_ascii_digit() || b[i] == b'_') {
                i += 1;
            }
            let s = String::from_utf8(b[start..i].to_vec()).ok()?;
            toks.push(Tok::Ident(s));
            continue;
        }
        if i + 1 < n {
            let two: Option<&'static str> = match (c, b[i + 1]) {
                (b'<', b'>') => Some("<>"),
                (b'>', b'<') => Some("><"),
                (b'=', b'=') => Some("=="),
                (b'!', b'=') => Some("!="),
                _ => None,
            };
            if let Some(s) = two {
                toks.push(Tok::Sym(s));
                i += 2;
                continue;
            }
        }
        let one: Option<&'static str> = match c {
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
        match one {
            Some(s) => {
                toks.push(Tok::Sym(s));
                i += 1;
            }
            None => return None,
        }
    }
    Some(toks)
}

type R<T> = Result<T, ()>;

struct Parser {
    toks: Vec<Tok>,
    pos: usize,
    depth: usize,
}

impl Parser {
    fn sym(&self) -> Option<&'static str> {
        match self.toks.get(self.pos) {
            Some(Tok::Sym(s)) => Some(*s),
            _ => None,
        }
    }

    fn at_end(&self) -> bool {
        self.pos >= self.toks.len()
    }

    fn expect_sym(&mut self, s: &str) -> R<()> {
        if self.sym() == Some(s) {
            self.pos += 1;
            Ok(())
        } else {
            Err(())
        }
    }

    fn expr(&mut self) -> R<Expr> {
        self.l1()
    }

    fn l1(&mut self) -> R<Expr> {
        let mut lhs = self.l2()?;
        loop {
            let op = match self.sym() {
                Some("<>") => BinOp::Max,
                Some("><") => BinOp::Min,
                _ => break,
            };
            self.pos += 1;
            let rhs = self.l2()?;
            lhs = Expr::Bin(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn l2(&mut self) -> R<Expr> {
        let lhs = self.l3()?;
        let op = match self.sym() {
            Some("==") => BinOp::Eq,
            Some("!=") => BinOp::Ne,
            Some("<") => BinOp::Lt,
            Some(">") => BinOp::Gt,
            _ => return Ok(lhs),
        };
        self.pos += 1;
        let rhs = self.l3()?;
        Ok(Expr::Bin(op, Box::new(lhs), Box::new(rhs)))
    }

    fn l3(&mut self) -> R<Expr> {
        let mut lhs = self.l4()?;
        loop {
            let op = match self.sym() {
                Some("+") => BinOp::Add,
                Some("-") => BinOp::Sub,
                _ => break,
            };
            self.pos += 1;
            let rhs = self.l4()?;
            lhs = Expr::Bin(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn l4(&mut self) -> R<Expr> {
        let mut lhs = self.l5()?;
        loop {
            let op = match self.sym() {
                Some("*") => BinOp::Mul,
                Some("/") => BinOp::Div,
                Some("%") => BinOp::Mod,
                _ => break,
            };
            self.pos += 1;
            let rhs = self.l5()?;
            lhs = Expr::Bin(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn l5(&mut self) -> R<Expr> {
        let lhs = self.l6()?;
        if self.sym() == Some("~") {
            self.pos += 1;
            let rhs = self.l5()?;
            Ok(Expr::Bin(BinOp::Rot, Box::new(lhs), Box::new(rhs)))
        } else {
            Ok(lhs)
        }
    }

    fn l6(&mut self) -> R<Expr> {
        match self.sym() {
            Some("-") => {
                self.pos += 1;
                let x = self.l6()?;
                Ok(Expr::Neg(Box::new(x)))
            }
            Some("#") => {
                self.pos += 1;
                let x = self.l6()?;
                Ok(Expr::Pop(Box::new(x)))
            }
            Some("!") => {
                self.pos += 1;
                let x = self.l6()?;
                Ok(Expr::Not(Box::new(x)))
            }
            _ => self.atom(),
        }
    }

    fn atom(&mut self) -> R<Expr> {
        match self.toks.get(self.pos).cloned() {
            Some(Tok::Num(v)) => {
                self.pos += 1;
                Ok(Expr::Num(v))
            }
            Some(Tok::Ident(s)) => {
                if is_kw(&s) {
                    return Err(());
                }
                self.pos += 1;
                Ok(Expr::Var(s))
            }
            Some(Tok::Sym("(")) => {
                self.depth += 1;
                if self.depth > 32 {
                    return Err(());
                }
                self.pos += 1;
                let e = self.expr()?;
                self.expect_sym(")")?;
                self.depth -= 1;
                Ok(e)
            }
            _ => Err(()),
        }
    }

    fn finish(&self) -> R<()> {
        if self.at_end() {
            Ok(())
        } else {
            Err(())
        }
    }
}

enum Stmt {
    Set(String, Expr),
    Out(Vec<Expr>),
    Loop(Expr),
    When(Expr),
    Else,
    End,
    Break,
}

fn parse_stmt(toks: Vec<Tok>) -> R<Stmt> {
    let first = match toks.first() {
        Some(Tok::Ident(s)) => s.clone(),
        _ => return Err(()),
    };
    let mut p = Parser {
        toks,
        pos: 1,
        depth: 0,
    };
    let st = match first.as_str() {
        "set" => {
            let name = match p.toks.get(p.pos) {
                Some(Tok::Ident(n)) if !is_kw(n) => n.clone(),
                _ => return Err(()),
            };
            p.pos += 1;
            p.expect_sym("=")?;
            let e = p.expr()?;
            Stmt::Set(name, e)
        }
        "out" => {
            let mut es = vec![p.expr()?];
            while p.sym() == Some(",") {
                p.pos += 1;
                es.push(p.expr()?);
            }
            Stmt::Out(es)
        }
        "loop" => Stmt::Loop(p.expr()?),
        "when" => Stmt::When(p.expr()?),
        "else" => Stmt::Else,
        "end" => Stmt::End,
        "break" => Stmt::Break,
        _ => return Err(()),
    };
    p.finish()?;
    Ok(st)
}

enum Instr {
    Set { name: String, e: Expr, line: usize },
    Out { es: Vec<Expr>, line: usize },
    Loop { e: Expr, line: usize, end: usize },
    EndLoop { start: usize },
    When { e: Expr, line: usize, false_target: usize },
    Else { end: usize },
    EndWhen,
    Break,
}

struct Open {
    kind: u8, // 0 = loop, 1 = when
    pc: usize,
    line: usize,
    else_pc: Option<usize>,
}

fn parse_line(
    raw: &[u8],
    line: usize,
    instrs: &mut Vec<Instr>,
    open: &mut Vec<Open>,
) -> R<()> {
    if raw.len() > 1000 {
        return Err(());
    }
    for &b in raw.iter() {
        if !(b == b'\t' || b == b'\r' || (0x20..=0x7E).contains(&b)) {
            return Err(());
        }
    }
    let body: &[u8] = match raw.iter().position(|&b| b == b';') {
        Some(p) => &raw[..p],
        None => raw,
    };
    let toks = tokenize(body).ok_or(())?;
    if toks.is_empty() {
        return Ok(());
    }
    let st = parse_stmt(toks)?;
    match st {
        Stmt::Set(name, e) => instrs.push(Instr::Set { name, e, line }),
        Stmt::Out(es) => instrs.push(Instr::Out { es, line }),
        Stmt::Loop(e) => {
            if open.len() >= 16 {
                return Err(());
            }
            let pc = instrs.len();
            instrs.push(Instr::Loop { e, line, end: 0 });
            open.push(Open {
                kind: 0,
                pc,
                line,
                else_pc: None,
            });
        }
        Stmt::When(e) => {
            if open.len() >= 16 {
                return Err(());
            }
            let pc = instrs.len();
            instrs.push(Instr::When {
                e,
                line,
                false_target: 0,
            });
            open.push(Open {
                kind: 1,
                pc,
                line,
                else_pc: None,
            });
        }
        Stmt::Else => {
            let top = open.last_mut().ok_or(())?;
            if top.kind != 1 || top.else_pc.is_some() {
                return Err(());
            }
            let x = instrs.len();
            top.else_pc = Some(x);
            let wpc = top.pc;
            instrs.push(Instr::Else { end: 0 });
            if let Instr::When { false_target, .. } = &mut instrs[wpc] {
                *false_target = x + 1;
            }
        }
        Stmt::End => {
            let top = open.pop().ok_or(())?;
            let e = instrs.len();
            if top.kind == 0 {
                instrs.push(Instr::EndLoop { start: top.pc });
                if let Instr::Loop { end, .. } = &mut instrs[top.pc] {
                    *end = e;
                }
            } else {
                instrs.push(Instr::EndWhen);
                match top.else_pc {
                    Some(x) => {
                        if let Instr::Else { end } = &mut instrs[x] {
                            *end = e;
                        }
                    }
                    None => {
                        if let Instr::When { false_target, .. } = &mut instrs[top.pc] {
                            *false_target = e + 1;
                        }
                    }
                }
            }
        }
        Stmt::Break => {
            if !open.iter().any(|o| o.kind == 0) {
                return Err(());
            }
            instrs.push(Instr::Break);
        }
    }
    let _ = line;
    Ok(())
}

fn parse_program(data: &[u8]) -> Result<Vec<Instr>, usize> {
    let mut pieces: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if pieces.last().map_or(false, |l| l.is_empty()) {
        pieces.pop();
    }
    let mut instrs: Vec<Instr> = Vec::new();
    let mut open: Vec<Open> = Vec::new();
    for (idx, raw) in pieces.iter().enumerate() {
        let line = idx + 1;
        if parse_line(raw, line, &mut instrs, &mut open).is_err() {
            return Err(line);
        }
    }
    if let Some(top) = open.last() {
        return Err(top.line);
    }
    Ok(instrs)
}

fn eval(e: &Expr, vars: &HashMap<String, u32>) -> Result<u32, ()> {
    Ok(match e {
        Expr::Num(v) => *v,
        Expr::Var(n) => *vars.get(n).ok_or(())?,
        Expr::Neg(x) => eval(x, vars)?.wrapping_neg(),
        Expr::Pop(x) => eval(x, vars)?.count_ones(),
        Expr::Not(x) => {
            if eval(x, vars)? == 0 {
                1
            } else {
                0
            }
        }
        Expr::Bin(op, a, b) => {
            let l = eval(a, vars)?;
            let r = eval(b, vars)?;
            match op {
                BinOp::Max => l.max(r),
                BinOp::Min => l.min(r),
                BinOp::Eq => (l == r) as u32,
                BinOp::Ne => (l != r) as u32,
                BinOp::Lt => (l < r) as u32,
                BinOp::Gt => (l > r) as u32,
                BinOp::Add => l.wrapping_add(r),
                BinOp::Sub => l.wrapping_sub(r),
                BinOp::Mul => l.wrapping_mul(r),
                BinOp::Div => {
                    if r == 0 {
                        return Err(());
                    }
                    l / r
                }
                BinOp::Mod => {
                    if r == 0 {
                        return Err(());
                    }
                    l % r
                }
                BinOp::Rot => l.rotate_left(r % 32),
            }
        }
    })
}

fn run(instrs: &[Instr], out: &mut String) -> Result<(), usize> {
    let mut vars: HashMap<String, u32> = HashMap::new();
    // (end pc of loop, remaining iterations)
    let mut frames: Vec<(usize, u32)> = Vec::new();
    let mut pc: usize = 0;
    while pc < instrs.len() {
        match &instrs[pc] {
            Instr::Set { name, e, line } => {
                let v = eval(e, &vars).map_err(|_| *line)?;
                vars.insert(name.clone(), v);
                pc += 1;
            }
            Instr::Out { es, line } => {
                let mut vals: Vec<u32> = Vec::with_capacity(es.len());
                for e in es.iter() {
                    vals.push(eval(e, &vars).map_err(|_| *line)?);
                }
                let s: Vec<String> = vals.iter().map(|v| v.to_string()).collect();
                out.push_str(&s.join(" "));
                out.push('\n');
                pc += 1;
            }
            Instr::Loop { e, line, end } => {
                let n = eval(e, &vars).map_err(|_| *line)?;
                if n == 0 {
                    pc = *end + 1;
                } else {
                    frames.push((*end, n));
                    pc += 1;
                }
            }
            Instr::EndLoop { start } => {
                let again = match frames.last_mut() {
                    Some(f) => {
                        f.1 -= 1;
                        f.1 > 0
                    }
                    None => false,
                };
                if again {
                    pc = *start + 1;
                } else {
                    let _ = frames.pop();
                    pc += 1;
                }
            }
            Instr::When {
                e,
                line,
                false_target,
            } => {
                let v = eval(e, &vars).map_err(|_| *line)?;
                if v != 0 {
                    pc += 1;
                } else {
                    pc = *false_target;
                }
            }
            Instr::Else { end } => {
                pc = *end + 1;
            }
            Instr::EndWhen => {
                pc += 1;
            }
            Instr::Break => {
                if let Some((end, _)) = frames.pop() {
                    pc = end + 1;
                } else {
                    pc += 1;
                }
            }
        }
    }
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        process::exit(1);
    }
    let data = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(_) => process::exit(1),
    };
    let instrs = match parse_program(&data) {
        Ok(i) => i,
        Err(line) => {
            let stdout = io::stdout();
            let mut lock = stdout.lock();
            let _ = writeln!(lock, "parse error line {}", line);
            let _ = lock.flush();
            drop(lock);
            process::exit(2);
        }
    };
    let mut out = String::new();
    let res = run(&instrs, &mut out);
    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(out.as_bytes());
    match res {
        Ok(()) => {
            let _ = lock.flush();
            drop(lock);
            process::exit(0);
        }
        Err(line) => {
            let _ = writeln!(lock, "runtime error line {}", line);
            let _ = lock.flush();
            drop(lock);
            process::exit(3);
        }
    }
}
