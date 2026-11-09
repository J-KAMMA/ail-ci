use std::io::{self, Read, Write};

struct Tree {
    pool: Vec<u8>,
    name: Vec<(usize, usize)>,
    weight: Vec<u64>,
    ch: Vec<Vec<usize>>,
    root: usize,
}

impl Tree {
    fn nm(&self, u: usize) -> &[u8] {
        let (s, e) = self.name[u];
        &self.pool[s..e]
    }

    fn preorder(&self) -> Vec<(usize, usize)> {
        let mut out = Vec::new();
        let mut st = vec![(self.root, 0usize)];
        while let Some((u, d)) = st.pop() {
            out.push((u, d));
            for &c in self.ch[u].iter().rev() {
                st.push((c, d + 1));
            }
        }
        out
    }

    fn subw(&self, order: &[(usize, usize)]) -> Vec<u64> {
        let mut sub = vec![0u64; self.ch.len()];
        for &(u, _) in order.iter().rev() {
            let mut s = self.weight[u];
            for &c in &self.ch[u] {
                s += sub[c];
            }
            sub[u] = s;
        }
        sub
    }

    fn emit(&self, u: usize, out: &mut Vec<u8>) {
        out.extend_from_slice(self.nm(u));
        out.push(b':');
        write!(out, "{}", self.weight[u]).unwrap();
        let kids = &self.ch[u];
        if !kids.is_empty() {
            out.push(b'[');
            for (i, &c) in kids.iter().enumerate() {
                if i > 0 {
                    out.push(b' ');
                }
                self.emit(c, out);
            }
            out.push(b']');
        }
    }

    fn find_node(&self, q: &[u8]) -> (Option<usize>, Vec<usize>) {
        let mut par = vec![usize::MAX; self.ch.len()];
        let mut st = vec![self.root];
        while let Some(u) = st.pop() {
            if self.nm(u) == q {
                return (Some(u), par);
            }
            for &c in self.ch[u].iter().rev() {
                par[c] = u;
                st.push(c);
            }
        }
        (None, par)
    }

    fn fold(&mut self) {
        let mut heads: Vec<usize> = self.ch[self.root].clone();
        while let Some(h) = heads.pop() {
            let start = self.pool.len();
            let (hs, he) = self.name[h];
            self.pool.extend_from_within(hs..he);
            let mut w = self.weight[h];
            let mut cur = h;
            while self.ch[cur].len() == 1 {
                let c = self.ch[cur][0];
                let (cs, ce) = self.name[c];
                self.pool.push(b'+');
                self.pool.extend_from_within(cs..ce);
                w += self.weight[c];
                cur = c;
            }
            let end = self.pool.len();
            self.name[h] = (start, end);
            self.weight[h] = w;
            let kids = std::mem::take(&mut self.ch[cur]);
            self.ch[h] = kids;
            heads.extend_from_slice(&self.ch[h]);
        }
    }
}

struct Parser<'a> {
    s: &'a [u8],
    p: usize,
    t: Tree,
}

impl<'a> Parser<'a> {
    fn parse_node(&mut self) -> Result<usize, ()> {
        let s = self.s;
        let ns = self.p;
        while self.p < s.len() && s[self.p].is_ascii_lowercase() {
            self.p += 1;
        }
        let ne = self.p;
        if ne - ns == 0 || ne - ns > 16 {
            return Err(());
        }
        if self.p >= s.len() || s[self.p] != b':' {
            return Err(());
        }
        self.p += 1;
        let ws = self.p;
        while self.p < s.len() && s[self.p].is_ascii_digit() {
            self.p += 1;
        }
        let wl = self.p - ws;
        if wl == 0 || wl > 7 || (wl > 1 && s[ws] == b'0') {
            return Err(());
        }
        let mut w: u64 = 0;
        for &c in &s[ws..self.p] {
            w = w * 10 + (c - b'0') as u64;
        }
        if w > 1_000_000 {
            return Err(());
        }
        let t = &mut self.t;
        let id = t.ch.len();
        let pst = t.pool.len();
        t.pool.extend_from_slice(&s[ns..ne]);
        let pend = t.pool.len();
        t.name.push((pst, pend));
        t.weight.push(w);
        t.ch.push(Vec::new());
        if self.p < s.len() && s[self.p] == b'[' {
            self.p += 1;
            loop {
                let c = self.parse_node()?;
                self.t.ch[id].push(c);
                if self.p < s.len() && s[self.p] == b' ' {
                    self.p += 1;
                } else if self.p < s.len() && s[self.p] == b']' {
                    self.p += 1;
                    break;
                } else {
                    return Err(());
                }
            }
        }
        Ok(id)
    }
}

enum Op {
    Total,
    Stats,
    Level(u64),
    Find(Vec<u8>),
    Print,
    Prune(u64),
    Sort,
    Mirror,
    Fold,
    Cut(Vec<u8>),
}

fn parse_num(b: &[u8]) -> Option<u64> {
    if b.is_empty() || b.len() > 16 || !b.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    if b.len() > 1 && b[0] == b'0' {
        return None;
    }
    let mut v: u64 = 0;
    for &c in b {
        v = v * 10 + (c - b'0') as u64;
    }
    if v > 1_000_000_000_000_000 {
        None
    } else {
        Some(v)
    }
}

fn parse_op(line: &[u8]) -> Option<Op> {
    let toks: Vec<&[u8]> = line.split(|&c| c == b' ').collect();
    let kw = toks[0];
    let argc = toks.len() - 1;
    let is = |s: &str| kw == s.as_bytes();
    if is("total") || is("stats") || is("print") || is("sort") || is("mirror") || is("fold") {
        if argc != 0 {
            return None;
        }
        return Some(if is("total") {
            Op::Total
        } else if is("stats") {
            Op::Stats
        } else if is("print") {
            Op::Print
        } else if is("sort") {
            Op::Sort
        } else if is("mirror") {
            Op::Mirror
        } else {
            Op::Fold
        });
    }
    if is("level") || is("prune") {
        if argc != 1 {
            return None;
        }
        let v = parse_num(toks[1])?;
        return Some(if is("level") {
            Op::Level(v)
        } else {
            Op::Prune(v)
        });
    }
    if is("find") || is("cut") {
        if argc != 1 {
            return None;
        }
        let n = toks[1];
        if n.is_empty() || !n.iter().all(|&c| c.is_ascii_lowercase() || c == b'+') {
            return None;
        }
        return Some(if is("find") {
            Op::Find(n.to_vec())
        } else {
            Op::Cut(n.to_vec())
        });
    }
    None
}

fn run() -> i32 {
    let mut data = Vec::new();
    if io::stdin().read_to_end(&mut data).is_err() {
        return 1;
    }
    if data.contains(&b'\r') {
        return 1;
    }
    let mut lines: Vec<&[u8]> = data.split(|&c| c == b'\n').collect();
    if data.last() == Some(&b'\n') {
        lines.pop();
    }
    if lines.is_empty() || lines.iter().any(|l| l.is_empty()) {
        return 1;
    }
    let mut ops = Vec::with_capacity(lines.len());
    for l in &lines[1..] {
        match parse_op(l) {
            Some(o) => ops.push(o),
            None => return 1,
        }
    }
    let mut ps = Parser {
        s: lines[0],
        p: 0,
        t: Tree {
            pool: Vec::new(),
            name: Vec::new(),
            weight: Vec::new(),
            ch: Vec::new(),
            root: 0,
        },
    };
    let root = match ps.parse_node() {
        Ok(r) => r,
        Err(_) => return 1,
    };
    if ps.p != lines[0].len() {
        return 1;
    }
    let mut t = ps.t;
    t.root = root;

    let mut out: Vec<u8> = Vec::new();
    for op in ops {
        match op {
            Op::Total => {
                let order = t.preorder();
                let s: u64 = order.iter().map(|&(u, _)| t.weight[u]).sum();
                writeln!(out, "{}", s).unwrap();
            }
            Op::Stats => {
                let order = t.preorder();
                let nodes = order.len();
                let leaves = order.iter().filter(|&&(u, _)| t.ch[u].is_empty()).count();
                let height = order.iter().map(|&(_, d)| d).max().unwrap_or(0);
                let widest = order.iter().map(|&(u, _)| t.ch[u].len()).max().unwrap_or(0);
                writeln!(
                    out,
                    "nodes={} leaves={} height={} widest={}",
                    nodes, leaves, height, widest
                )
                .unwrap();
            }
            Op::Level(d) => {
                let order = t.preorder();
                let mut cnt: u64 = 0;
                let mut sum: u64 = 0;
                for &(u, dep) in &order {
                    if dep as u64 == d {
                        cnt += 1;
                        sum += t.weight[u];
                    }
                }
                writeln!(out, "{} {}", cnt, sum).unwrap();
            }
            Op::Find(q) => {
                let (found, par) = t.find_node(&q);
                match found {
                    None => {
                        out.extend_from_slice(b"none\n");
                    }
                    Some(x) => {
                        let mut parts: Vec<usize> = Vec::new();
                        let mut u = x;
                        loop {
                            parts.push(u);
                            if u == t.root {
                                break;
                            }
                            u = par[u];
                        }
                        for (i, &v) in parts.iter().rev().enumerate() {
                            if i > 0 {
                                out.push(b'/');
                            }
                            out.extend_from_slice(t.nm(v));
                        }
                        out.push(b'\n');
                    }
                }
            }
            Op::Print => {
                let root = t.root;
                t.emit(root, &mut out);
                out.push(b'\n');
            }
            Op::Prune(w) => {
                let order = t.preorder();
                let sub = t.subw(&order);
                for &(u, _) in &order {
                    t.ch[u].retain(|&c| sub[c] >= w);
                }
            }
            Op::Sort => {
                let order = t.preorder();
                let sub = t.subw(&order);
                let pool = &t.pool;
                let names = &t.name;
                for &(u, _) in &order {
                    let mut kids = std::mem::take(&mut t.ch[u]);
                    kids.sort_by(|&a, &b| {
                        sub[b].cmp(&sub[a]).then_with(|| {
                            let (as_, ae) = names[a];
                            let (bs, be) = names[b];
                            pool[as_..ae].cmp(&pool[bs..be])
                        })
                    });
                    t.ch[u] = kids;
                }
            }
            Op::Mirror => {
                let order = t.preorder();
                for &(u, _) in &order {
                    t.ch[u].reverse();
                }
            }
            Op::Fold => {
                t.fold();
            }
            Op::Cut(q) => {
                let (found, par) = t.find_node(&q);
                if let Some(x) = found {
                    if x != t.root {
                        let p = par[x];
                        let idx = t.ch[p].iter().position(|&c| c == x).unwrap();
                        let kids = t.ch[x].clone();
                        t.ch[p].splice(idx..idx + 1, kids);
                    }
                }
            }
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    lock.write_all(&out).ok();
    lock.flush().ok();
    0
}

fn main() {
    let child = std::thread::Builder::new()
        .stack_size(256 << 20)
        .spawn(run)
        .unwrap();
    let code = child.join().unwrap_or(1);
    std::process::exit(code);
}
