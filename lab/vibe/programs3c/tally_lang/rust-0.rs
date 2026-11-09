use std::collections::HashMap;
use std::io::Write;

#[derive(Clone)]
enum Tok {
    Num(u32),
    Word(String),
    Op(&'static str),
}

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
    Rem,
    Rot,
}

enum Ex {
    Num(u32),
    Var(String),
    Neg(Box<Ex>),
    Pop(Box<Ex>),
    Not(Box<Ex>),
    Bin(BinOp, Box<Ex>, Box<Ex>),
}

enum Ins {
    Set { line: usize, name: String, e: Ex },
    Out { line: usize, es: Vec<Ex> },
    Loop { line: usize, e: Ex, end: usize },
    When { line: usize, e: Ex, false_t: usize },
    Jump(usize),
    EndLoop,
    Break,
}

struct Open {
    is_loop: bool,
    line: usize,
    idx: usize,
    has_else: bool,
    else_idx: usize,
}

fn is_kw(w: &str) -> bool {
    matches!(w, "set" | "out" | "loop" | "when" | "else" | "end" | "break")
}

fn lex(s: &[u8]) -> Option<Vec<Tok>> {
    let mut out = Vec::new();
    let mut i = 0;
    let n = s.len();
    while i < n {
        let c = s[i];
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
            continue;
        }
        if c.is_ascii_digit() {
            let mut v: u64 = 0;
            while i < n && s[i].is_ascii_digit() {
                v = (v * 10 + (s[i] - b'0') as u64).min(1u64 << 40);
                i += 1;
            }
            if i < n && (s[i].is_ascii_lowercase() || s[i] == b'_') {
                return None;
            }
            if v > u32::MAX as u64 {
                return None;
            }
            out.push(Tok::Num(v as u32));
            continue;
        }
        if c.is_ascii_lowercase() || c == b'_' {
            let st = i;
            while i < n && (s[i].is_ascii_lowercase() || s[i].is_ascii_digit() || s[i] == b'_') {
                i += 1;
            }
            out.push(Tok::Word(String::from_utf8_lossy(&s[st..i]).into_owned()));
            continue;
        }
        let two = if i + 1 < n {
            match (c, s[i + 1]) {
                (b'<', b'>') => Some("<>"),
                (b'>', b'<') => Some("><"),
                (b'=', b'=') => Some("=="),
                (b'!', b'=') => Some("!="),
                _ => None,
            }
        } else {
            None
        };
        if let Some(t) = two {
            out.push(Tok::Op(t));
            i += 2;
            continue;
        }
        let one = match c {
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
        out.push(Tok::Op(one));
        i += 1;
    }
    Some(out)
}

struct P {
    t: Vec<Tok>,
    p: usize,
    depth: usize,
}

impl P {
    fn op(&self) -> Option<&'static str> {
        match self.t.get(self.p) {
            Some(Tok::Op(o)) => Some(*o),
            _ => None,
        }
    }
    fn eat(&mut self, o: &str) -> Result<(), ()> {
        if self.op() == Some(o) {
            self.p += 1;
            Ok(())
        } else {
            Err(())
        }
    }
    fn fin(&self) -> Result<(), ()> {
        if self.p == self.t.len() {
            Ok(())
        } else {
            Err(())
        }
    }
    fn expr(&mut self) -> Result<Ex, ()> {
        let mut l = self.cmp()?;
        loop {
            let op = match self.op() {
                Some("<>") => BinOp::Max,
                Some("><") => BinOp::Min,
                _ => break,
            };
            self.p += 1;
            let r = self.cmp()?;
            l = Ex::Bin(op, Box::new(l), Box::new(r));
        }
        Ok(l)
    }
    fn cmp(&mut self) -> Result<Ex, ()> {
        let l = self.add()?;
        let op = match self.op() {
            Some("==") => BinOp::Eq,
            Some("!=") => BinOp::Ne,
            Some("<") => BinOp::Lt,
            Some(">") => BinOp::Gt,
            _ => return Ok(l),
        };
        self.p += 1;
        let r = self.add()?;
        Ok(Ex::Bin(op, Box::new(l), Box::new(r)))
    }
    fn add(&mut self) -> Result<Ex, ()> {
        let mut l = self.mul()?;
        loop {
            let op = match self.op() {
                Some("+") => BinOp::Add,
                Some("-") => BinOp::Sub,
                _ => break,
            };
            self.p += 1;
            let r = self.mul()?;
            l = Ex::Bin(op, Box::new(l), Box::new(r));
        }
        Ok(l)
    }
    fn mul(&mut self) -> Result<Ex, ()> {
        let mut l = self.rot()?;
        loop {
            let op = match self.op() {
                Some("*") => BinOp::Mul,
                Some("/") => BinOp::Div,
                Some("%") => BinOp::Rem,
                _ => break,
            };
            self.p += 1;
            let r = self.rot()?;
            l = Ex::Bin(op, Box::new(l), Box::new(r));
        }
        Ok(l)
    }
    fn rot(&mut self) -> Result<Ex, ()> {
        let l = self.unary()?;
        if self.op() == Some("~") {
            self.p += 1;
            let r = self.rot()?;
            return Ok(Ex::Bin(BinOp::Rot, Box::new(l), Box::new(r)));
        }
        Ok(l)
    }
    fn unary(&mut self) -> Result<Ex, ()> {
        match self.op() {
            Some("-") => {
                self.p += 1;
                Ok(Ex::Neg(Box::new(self.unary()?)))
            }
            Some("#") => {
                self.p += 1;
                Ok(Ex::Pop(Box::new(self.unary()?)))
            }
            Some("!") => {
                self.p += 1;
                Ok(Ex::Not(Box::new(self.unary()?)))
            }
            _ => self.atom(),
        }
    }
    fn atom(&mut self) -> Result<Ex, ()> {
        let tok = self.t.get(self.p).cloned().ok_or(())?;
        match tok {
            Tok::Num(v) => {
                self.p += 1;
                Ok(Ex::Num(v))
            }
            Tok::Word(w) => {
                if is_kw(&w) {
                    Err(())
                } else {
                    self.p += 1;
                    Ok(Ex::Var(w))
                }
            }
            Tok::Op("(") => {
                self.depth += 1;
                if self.depth > 32 {
                    return Err(());
                }
                self.p += 1;
                let e = self.expr()?;
                self.eat(")")?;
                self.depth -= 1;
                Ok(e)
            }
            _ => Err(()),
        }
    }
}

fn parse_line(
    raw: &[u8],
    ln: usize,
    prog: &mut Vec<Ins>,
    stack: &mut Vec<Open>,
) -> Result<(), ()> {
    if raw.len() > 1000 {
        return Err(());
    }
    for &b in raw {
        if !(b == b'\t' || b == b'\r' || (0x20..=0x7e).contains(&b)) {
            return Err(());
        }
    }
    let end = raw.iter().position(|&b| b == b';').unwrap_or(raw.len());
    let toks = lex(&raw[..end]).ok_or(())?;
    if toks.is_empty() {
        return Ok(());
    }
    let first = match &toks[0] {
        Tok::Word(w) => w.clone(),
        _ => return Err(()),
    };
    let mut p = P {
        t: toks,
        p: 1,
        depth: 0,
    };
    match first.as_str() {
        "set" => {
            let name = match p.t.get(1) {
                Some(Tok::Word(w)) if !is_kw(w) => w.clone(),
                _ => return Err(()),
            };
            p.p = 2;
            p.eat("=")?;
            let e = p.expr()?;
            p.fin()?;
            prog.push(Ins::Set { line: ln, name, e });
        }
        "out" => {
            let mut es = vec![p.expr()?];
            while p.op() == Some(",") {
                p.p += 1;
                es.push(p.expr()?);
            }
            p.fin()?;
            prog.push(Ins::Out { line: ln, es });
        }
        "loop" => {
            let e = p.expr()?;
            p.fin()?;
            if stack.len() >= 16 {
                return Err(());
            }
            stack.push(Open {
                is_loop: true,
                line: ln,
                idx: prog.len(),
                has_else: false,
                else_idx: 0,
            });
            prog.push(Ins::Loop { line: ln, e, end: 0 });
        }
        "when" => {
            let e = p.expr()?;
            p.fin()?;
            if stack.len() >= 16 {
                return Err(());
            }
            stack.push(Open {
                is_loop: false,
                line: ln,
                idx: prog.len(),
                has_else: false,
                else_idx: 0,
            });
            prog.push(Ins::When {
                line: ln,
                e,
                false_t: 0,
            });
        }
        "else" => {
            p.fin()?;
            let else_idx = prog.len();
            let top = stack.last_mut().ok_or(())?;
            if top.is_loop || top.has_else {
                return Err(());
            }
            top.has_else = true;
            top.else_idx = else_idx;
            let w_idx = top.idx;
            prog.push(Ins::Jump(0));
            if let Ins::When { false_t, .. } = &mut prog[w_idx] {
                *false_t = else_idx + 1;
            }
        }
        "end" => {
            p.fin()?;
            let top = stack.pop().ok_or(())?;
            let z = prog.len();
            if top.is_loop {
                prog.push(Ins::EndLoop);
                if let Ins::Loop { end, .. } = &mut prog[top.idx] {
                    *end = z;
                }
            } else if top.has_else {
                if let Ins::Jump(t) = &mut prog[top.else_idx] {
                    *t = z;
                }
            } else if let Ins::When { false_t, .. } = &mut prog[top.idx] {
                *false_t = z;
            }
        }
        "break" => {
            p.fin()?;
            if !stack.iter().any(|o| o.is_loop) {
                return Err(());
            }
            prog.push(Ins::Break);
        }
        _ => return Err(()),
    }
    Ok(())
}

fn eval(e: &Ex, vars: &HashMap<String, u32>) -> Option<u32> {
    Some(match e {
        Ex::Num(v) => *v,
        Ex::Var(n) => *vars.get(n)?,
        Ex::Neg(x) => eval(x, vars)?.wrapping_neg(),
        Ex::Pop(x) => eval(x, vars)?.count_ones(),
        Ex::Not(x) => (eval(x, vars)? == 0) as u32,
        Ex::Bin(op, a, b) => {
            let x = eval(a, vars)?;
            let y = eval(b, vars)?;
            match op {
                BinOp::Max => x.max(y),
                BinOp::Min => x.min(y),
                BinOp::Eq => (x == y) as u32,
                BinOp::Ne => (x != y) as u32,
                BinOp::Lt => (x < y) as u32,
                BinOp::Gt => (x > y) as u32,
                BinOp::Add => x.wrapping_add(y),
                BinOp::Sub => x.wrapping_sub(y),
                BinOp::Mul => x.wrapping_mul(y),
                BinOp::Div => x.checked_div(y)?,
                BinOp::Rem => x.checked_rem(y)?,
                BinOp::Rot => x.rotate_left(y % 32),
            }
        }
    })
}

fn rt_error(line: usize) -> ! {
    println!("runtime error line {}", line);
    let _ = std::io::stdout().flush();
    std::process::exit(3);
}

fn run(prog: &[Ins]) {
    let mut vars: HashMap<String, u32> = HashMap::new();
    // frames: (remaining iterations, body start, index of EndLoop)
    let mut frames: Vec<(u32, usize, usize)> = Vec::new();
    let mut pc = 0usize;
    while pc < prog.len() {
        match &prog[pc] {
            Ins::Set { line, name, e } => {
                match eval(e, &vars) {
                    Some(v) => {
                        vars.insert(name.clone(), v);
                    }
                    None => rt_error(*line),
                }
                pc += 1;
            }
            Ins::Out { line, es } => {
                let mut vals: Vec<String> = Vec::with_capacity(es.len());
                for e in es {
                    match eval(e, &vars) {
                        Some(v) => vals.push(v.to_string()),
                        None => rt_error(*line),
                    }
                }
                println!("{}", vals.join(" "));
                pc += 1;
            }
            Ins::Loop { line, e, end } => match eval(e, &vars) {
                Some(0) => pc = *end + 1,
                Some(n) => {
                    frames.push((n, pc + 1, *end));
                    pc += 1;
                }
                None => rt_error(*line),
            },
            Ins::When { line, e, false_t } => match eval(e, &vars) {
                Some(v) => {
                    if v != 0 {
                        pc += 1;
                    } else {
                        pc = *false_t;
                    }
                }
                None => rt_error(*line),
            },
            Ins::Jump(t) => pc = *t,
            Ins::EndLoop => {
                let (rem, start) = {
                    let f = frames.last_mut().unwrap();
                    f.0 -= 1;
                    (f.0, f.1)
                };
                if rem > 0 {
                    pc = start;
                } else {
                    frames.pop();
                    pc += 1;
                }
            }
            Ins::Break => {
                let f = frames.pop().unwrap();
                pc = f.2 + 1;
            }
        }
    }
    let _ = std::io::stdout().flush();
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
    if data.last() == Some(&b'\n') {
        lines.pop();
    }
    let mut prog: Vec<Ins> = Vec::new();
    let mut stack: Vec<Open> = Vec::new();
    for (i, raw) in lines.iter().enumerate() {
        let ln = i + 1;
        if parse_line(*raw, ln, &mut prog, &mut stack).is_err() {
            println!("parse error line {}", ln);
            let _ = std::io::stdout().flush();
            std::process::exit(2);
        }
    }
    if let Some(top) = stack.last() {
        println!("parse error line {}", top.line);
        let _ = std::io::stdout().flush();
        std::process::exit(2);
    }
    run(&prog);
    std::process::exit(0);
}
