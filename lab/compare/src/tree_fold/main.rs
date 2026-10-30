use std::io::{Read, Write};

struct Tree {
    names: Vec<u8>,
    nm: Vec<(u32, u32)>,
    w: Vec<u64>,
    ch: Vec<Vec<u32>>,
}

impl Tree {
    fn name(&self, i: u32) -> &[u8] {
        let (s, l) = self.nm[i as usize];
        &self.names[s as usize..(s + l) as usize]
    }
    // preorder: (node, parent position in order or u32::MAX, depth)
    fn pre(&self) -> (Vec<u32>, Vec<u32>, Vec<u32>) {
        let mut ord = Vec::new();
        let mut par = Vec::new();
        let mut dep = Vec::new();
        let mut st: Vec<(u32, u32, u32)> = vec![(0, u32::MAX, 0)];
        while let Some((n, p, d)) = st.pop() {
            let pos = ord.len() as u32;
            ord.push(n);
            par.push(p);
            dep.push(d);
            for &c in self.ch[n as usize].iter().rev() {
                st.push((c, pos, d + 1));
            }
        }
        (ord, par, dep)
    }
    // subtree weights indexed by node id
    fn sub(&self, ord: &[u32], par: &[u32]) -> Vec<u64> {
        let mut s = vec![0u64; self.w.len()];
        let mut acc: Vec<u64> = ord.iter().map(|&n| self.w[n as usize]).collect();
        for i in (0..ord.len()).rev() {
            s[ord[i] as usize] = acc[i];
            if par[i] != u32::MAX {
                acc[par[i] as usize] += acc[i];
            }
        }
        s
    }
}

fn parse_tree(s: &[u8]) -> Option<Tree> {
    let n = s.len();
    let mut t = Tree { names: s.to_vec(), nm: vec![], w: vec![], ch: vec![] };
    let mut pos = 0;
    let mut stack: Vec<u32> = vec![];
    loop {
        let start = pos;
        while pos < n && s[pos].is_ascii_lowercase() {
            pos += 1;
        }
        let len = pos - start;
        if len < 1 || len > 16 {
            return None;
        }
        if pos >= n || s[pos] != b':' {
            return None;
        }
        pos += 1;
        let ds = pos;
        while pos < n && s[pos].is_ascii_digit() {
            pos += 1;
        }
        let dl = pos - ds;
        if dl == 0 || dl > 7 || (s[ds] == b'0' && dl > 1) {
            return None;
        }
        let mut w = 0u64;
        for &c in &s[ds..pos] {
            w = w * 10 + (c - b'0') as u64;
        }
        if w > 1_000_000 {
            return None;
        }
        let id = t.w.len() as u32;
        t.nm.push((start as u32, len as u32));
        t.w.push(w);
        t.ch.push(Vec::new());
        if let Some(&p) = stack.last() {
            t.ch[p as usize].push(id);
        }
        if pos < n && s[pos] == b'[' {
            pos += 1;
            stack.push(id);
            continue;
        }
        loop {
            if stack.is_empty() {
                return if pos == n { Some(t) } else { None };
            }
            if pos >= n {
                return None;
            }
            match s[pos] {
                b' ' => {
                    pos += 1;
                    break;
                }
                b']' => {
                    pos += 1;
                    stack.pop();
                }
                _ => return None,
            }
        }
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

fn num(a: &[u8]) -> Option<u64> {
    if a.is_empty() || a.len() > 16 || (a[0] == b'0' && a.len() > 1) {
        return None;
    }
    let mut v = 0u64;
    for &c in a {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v * 10 + (c - b'0') as u64;
    }
    if v > 1_000_000_000_000_000 {
        None
    } else {
        Some(v)
    }
}

fn nameok(a: &[u8]) -> bool {
    !a.is_empty() && a.iter().all(|&c| c.is_ascii_lowercase() || c == b'+')
}

fn parse_op(l: &[u8]) -> Option<Op> {
    match l {
        b"total" => return Some(Op::Total),
        b"stats" => return Some(Op::Stats),
        b"print" => return Some(Op::Print),
        b"sort" => return Some(Op::Sort),
        b"mirror" => return Some(Op::Mirror),
        b"fold" => return Some(Op::Fold),
        _ => {}
    }
    let sp = l.iter().position(|&c| c == b' ')?;
    let (k, a) = (&l[..sp], &l[sp + 1..]);
    match k {
        b"level" => Some(Op::Level(num(a)?)),
        b"prune" => Some(Op::Prune(num(a)?)),
        b"find" if nameok(a) => Some(Op::Find(a.to_vec())),
        b"cut" if nameok(a) => Some(Op::Cut(a.to_vec())),
        _ => None,
    }
}

fn main() {
    let mut inp = Vec::new();
    std::io::stdin().read_to_end(&mut inp).ok();
    let fail = || -> ! { std::process::exit(1) };
    let body: &[u8] = if inp.last() == Some(&b'\n') { &inp[..inp.len() - 1] } else { &inp[..] };
    let mut lines = body.split(|&c| c == b'\n');
    let first = lines.next().unwrap();
    let mut t = match parse_tree(first) {
        Some(t) => t,
        None => fail(),
    };
    let mut ops = Vec::new();
    for l in lines {
        match parse_op(l) {
            Some(o) => ops.push(o),
            None => fail(),
        }
    }
    let so = std::io::stdout();
    let mut out = std::io::BufWriter::with_capacity(1 << 16, so.lock());
    for op in ops {
        match op {
            Op::Total => {
                let (ord, _, _) = t.pre();
                let s: u64 = ord.iter().map(|&n| t.w[n as usize]).sum();
                writeln!(out, "{}", s).unwrap();
            }
            Op::Stats => {
                let (ord, _, dep) = t.pre();
                let mut leaves = 0;
                let mut widest = 0;
                for &n in &ord {
                    let c = t.ch[n as usize].len();
                    if c == 0 {
                        leaves += 1;
                    }
                    if c > widest {
                        widest = c;
                    }
                }
                let h = dep.iter().copied().max().unwrap_or(0);
                writeln!(out, "nodes={} leaves={} height={} widest={}", ord.len(), leaves, h, widest).unwrap();
            }
            Op::Level(d) => {
                let (ord, _, dep) = t.pre();
                let (mut c, mut s) = (0u64, 0u64);
                for i in 0..ord.len() {
                    if dep[i] as u64 == d {
                        c += 1;
                        s += t.w[ord[i] as usize];
                    }
                }
                writeln!(out, "{} {}", c, s).unwrap();
            }
            Op::Find(nm) => {
                let (ord, par, _) = t.pre();
                match ord.iter().position(|&n| t.name(n) == &nm[..]) {
                    None => writeln!(out, "none").unwrap(),
                    Some(mut i) => {
                        let mut path = vec![];
                        loop {
                            path.push(ord[i]);
                            if par[i] == u32::MAX {
                                break;
                            }
                            i = par[i] as usize;
                        }
                        let mut line = Vec::new();
                        for (k, &n) in path.iter().rev().enumerate() {
                            if k > 0 {
                                line.push(b'/');
                            }
                            line.extend_from_slice(t.name(n));
                        }
                        line.push(b'\n');
                        out.write_all(&line).unwrap();
                    }
                }
            }
            Op::Print => {
                let mut buf: Vec<u8> = Vec::new();
                let mut st: Vec<(u32, usize)> = vec![(0, 0)];
                buf.extend_from_slice(t.name(0));
                buf.push(b':');
                buf.extend_from_slice(t.w[0].to_string().as_bytes());
                if !t.ch[0].is_empty() {
                    buf.push(b'[');
                }
                while let Some(top) = st.last_mut() {
                    let (n, i) = *top;
                    let cs = &t.ch[n as usize];
                    if i >= cs.len() {
                        if !cs.is_empty() {
                            buf.push(b']');
                        }
                        st.pop();
                        continue;
                    }
                    top.1 += 1;
                    if i > 0 {
                        buf.push(b' ');
                    }
                    let c = cs[i];
                    buf.extend_from_slice(t.name(c));
                    buf.push(b':');
                    buf.extend_from_slice(t.w[c as usize].to_string().as_bytes());
                    if !t.ch[c as usize].is_empty() {
                        buf.push(b'[');
                    }
                    st.push((c, 0));
                }
                buf.push(b'\n');
                out.write_all(&buf).unwrap();
            }
            Op::Prune(w) => {
                let (ord, par, _) = t.pre();
                let sub = t.sub(&ord, &par);
                for &n in &ord {
                    let mut v = std::mem::take(&mut t.ch[n as usize]);
                    v.retain(|&c| sub[c as usize] >= w);
                    t.ch[n as usize] = v;
                }
            }
            Op::Sort => {
                let (ord, par, _) = t.pre();
                let sub = t.sub(&ord, &par);
                for &n in &ord {
                    if t.ch[n as usize].len() > 1 {
                        let mut v = std::mem::take(&mut t.ch[n as usize]);
                        v.sort_by(|&a, &b| {
                            sub[b as usize].cmp(&sub[a as usize]).then_with(|| t.name(a).cmp(t.name(b)))
                        });
                        t.ch[n as usize] = v;
                    }
                }
            }
            Op::Mirror => {
                let (ord, _, _) = t.pre();
                for &n in &ord {
                    t.ch[n as usize].reverse();
                }
            }
            Op::Fold => {
                let mut st: Vec<(u32, bool)> = vec![(0, true)];
                while let Some((u, head)) = st.pop() {
                    if u != 0 && head && t.ch[u as usize].len() == 1 {
                        let (s0, l0) = t.nm[u as usize];
                        let start = t.names.len();
                        t.names.extend_from_within(s0 as usize..(s0 + l0) as usize);
                        let mut wsum = t.w[u as usize];
                        let mut cur = t.ch[u as usize][0];
                        loop {
                            let (s, l) = t.nm[cur as usize];
                            t.names.push(b'+');
                            t.names.extend_from_within(s as usize..(s + l) as usize);
                            wsum += t.w[cur as usize];
                            if t.ch[cur as usize].len() == 1 {
                                cur = t.ch[cur as usize][0];
                            } else {
                                break;
                            }
                        }
                        let kids = std::mem::take(&mut t.ch[cur as usize]);
                        t.ch[u as usize] = kids;
                        t.nm[u as usize] = (start as u32, (t.names.len() - start) as u32);
                        t.w[u as usize] = wsum;
                    }
                    let h = u == 0 || t.ch[u as usize].len() != 1;
                    for &c in t.ch[u as usize].iter() {
                        st.push((c, h));
                    }
                }
            }
            Op::Cut(nm) => {
                let (ord, par, _) = t.pre();
                if let Some(i) = ord.iter().position(|&n| t.name(n) == &nm[..]) {
                    if i != 0 {
                        let n = ord[i];
                        let p = ord[par[i] as usize];
                        let kids = std::mem::take(&mut t.ch[n as usize]);
                        let pc = &mut t.ch[p as usize];
                        let at = pc.iter().position(|&c| c == n).unwrap();
                        pc.splice(at..at + 1, kids);
                    }
                }
            }
        }
    }
    out.flush().unwrap();
}
