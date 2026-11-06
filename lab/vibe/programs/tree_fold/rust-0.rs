use std::io::{self, Read, Write, BufWriter};

struct Node {
    ns: usize,
    nl: usize,
    w: u64,
    ch: Vec<usize>,
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

struct Tree {
    names: Vec<u8>,
    nodes: Vec<Node>,
    root: usize,
    par: Vec<usize>,
    sub: Vec<u64>,
    order: Vec<usize>,
    depth: Vec<usize>,
}

impl Tree {
    fn name(&self, v: usize) -> &[u8] {
        let nd = &self.nodes[v];
        &self.names[nd.ns..nd.ns + nd.nl]
    }

    fn ensure(&mut self) {
        let n = self.nodes.len();
        if self.par.len() < n {
            self.par.resize(n, 0);
        }
        if self.sub.len() < n {
            self.sub.resize(n, 0);
        }
        if self.depth.len() < n {
            self.depth.resize(n, 0);
        }
    }

    fn build_order(&mut self) {
        self.ensure();
        let Tree { nodes, par, order, root, .. } = self;
        let root = *root;
        order.clear();
        order.push(root);
        par[root] = usize::MAX;
        let mut i = 0;
        while i < order.len() {
            let v = order[i];
            i += 1;
            let len = nodes[v].ch.len();
            for k in 0..len {
                let c = nodes[v].ch[k];
                par[c] = v;
                order.push(c);
            }
        }
    }

    fn prepare_order_depth(&mut self) {
        self.ensure();
        let Tree { nodes, par, order, depth, root, .. } = self;
        let root = *root;
        order.clear();
        order.push(root);
        par[root] = usize::MAX;
        depth[root] = 0;
        let mut i = 0;
        while i < order.len() {
            let v = order[i];
            i += 1;
            let d = depth[v];
            let len = nodes[v].ch.len();
            for k in 0..len {
                let c = nodes[v].ch[k];
                par[c] = v;
                depth[c] = d + 1;
                order.push(c);
            }
        }
    }

    fn compute_sub(&mut self) {
        self.build_order();
        let Tree { nodes, sub, order, par, .. } = self;
        for &v in order.iter() {
            sub[v] = nodes[v].w;
        }
        let mut i = order.len();
        while i > 1 {
            i -= 1;
            let v = order[i];
            let p = par[v];
            sub[p] += sub[v];
        }
    }

    fn find_node(&mut self, name: &[u8]) -> Option<usize> {
        self.ensure();
        let Tree { names, nodes, par, root, .. } = self;
        let root = *root;
        let mut stack: Vec<usize> = vec![root];
        par[root] = usize::MAX;
        while let Some(v) = stack.pop() {
            let nd = &nodes[v];
            if &names[nd.ns..nd.ns + nd.nl] == name {
                return Some(v);
            }
            let len = nd.ch.len();
            for k in (0..len).rev() {
                let c = nd.ch[k];
                par[c] = v;
                stack.push(c);
            }
        }
        None
    }

    fn path_of(&self, mut v: usize) -> Vec<u8> {
        let mut parts: Vec<&[u8]> = Vec::new();
        loop {
            parts.push(self.name(v));
            if self.par[v] == usize::MAX {
                break;
            }
            v = self.par[v];
        }
        parts.reverse();
        let mut out = Vec::new();
        for (i, p) in parts.iter().enumerate() {
            if i > 0 {
                out.push(b'/');
            }
            out.extend_from_slice(p);
        }
        out
    }

    fn emit_header(&self, v: usize, buf: &mut Vec<u8>) {
        let nd = &self.nodes[v];
        buf.extend_from_slice(&self.names[nd.ns..nd.ns + nd.nl]);
        buf.push(b':');
        push_num(buf, nd.w);
    }

    fn op_total<W: Write>(&mut self, out: &mut W) -> io::Result<()> {
        self.build_order();
        let mut s: u64 = 0;
        let n = self.order.len();
        for idx in 0..n {
            let v = self.order[idx];
            s += self.nodes[v].w;
        }
        writeln!(out, "{}", s)
    }

    fn op_stats<W: Write>(&mut self, out: &mut W) -> io::Result<()> {
        self.prepare_order_depth();
        let n = self.order.len();
        let mut leaves = 0usize;
        let mut height = 0usize;
        let mut widest = 0usize;
        for idx in 0..n {
            let v = self.order[idx];
            let cl = self.nodes[v].ch.len();
            if cl == 0 {
                leaves += 1;
            }
            if cl > widest {
                widest = cl;
            }
            let d = self.depth[v];
            if d > height {
                height = d;
            }
        }
        writeln!(
            out,
            "nodes={} leaves={} height={} widest={}",
            n, leaves, height, widest
        )
    }

    fn op_level<W: Write>(&mut self, d: u64, out: &mut W) -> io::Result<()> {
        self.prepare_order_depth();
        let n = self.order.len();
        let mut cnt: u64 = 0;
        let mut sum: u64 = 0;
        for idx in 0..n {
            let v = self.order[idx];
            if (self.depth[v] as u64) == d {
                cnt += 1;
                sum += self.nodes[v].w;
            }
        }
        writeln!(out, "{} {}", cnt, sum)
    }

    fn op_find<W: Write>(&mut self, name: &[u8], out: &mut W) -> io::Result<()> {
        match self.find_node(name) {
            Some(v) => {
                let path = self.path_of(v);
                out.write_all(&path)?;
                out.write_all(b"\n")
            }
            None => out.write_all(b"none\n"),
        }
    }

    fn op_print<W: Write>(&mut self, out: &mut W) -> io::Result<()> {
        let mut buf: Vec<u8> = Vec::new();
        self.emit_header(self.root, &mut buf);
        if !self.nodes[self.root].ch.is_empty() {
            buf.push(b'[');
        }
        let mut stack: Vec<(usize, usize)> = vec![(self.root, 0)];
        loop {
            let (v, ci) = match stack.last() {
                Some(&(a, b)) => (a, b),
                None => break,
            };
            if ci < self.nodes[v].ch.len() {
                stack.last_mut().unwrap().1 = ci + 1;
                let c = self.nodes[v].ch[ci];
                if ci > 0 {
                    buf.push(b' ');
                }
                self.emit_header(c, &mut buf);
                if !self.nodes[c].ch.is_empty() {
                    buf.push(b'[');
                    stack.push((c, 0));
                }
            } else {
                if !self.nodes[v].ch.is_empty() {
                    buf.push(b']');
                }
                stack.pop();
            }
        }
        buf.push(b'\n');
        out.write_all(&buf)
    }

    fn op_prune(&mut self, w: u64) {
        self.compute_sub();
        let n = self.order.len();
        let Tree { nodes, sub, order, .. } = self;
        for idx in 0..n {
            let v = order[idx];
            nodes[v].ch.retain(|&c| sub[c] >= w);
        }
    }

    fn op_sort(&mut self) {
        self.compute_sub();
        let n = self.order.len();
        let Tree { names, nodes, sub, order, .. } = self;
        for idx in 0..n {
            let v = order[idx];
            let mut ch = std::mem::take(&mut nodes[v].ch);
            ch.sort_by(|&a, &b| {
                let o = sub[b].cmp(&sub[a]);
                if o != std::cmp::Ordering::Equal {
                    return o;
                }
                let na = &names[nodes[a].ns..nodes[a].ns + nodes[a].nl];
                let nb = &names[nodes[b].ns..nodes[b].ns + nodes[b].nl];
                na.cmp(nb)
            });
            nodes[v].ch = ch;
        }
    }

    fn op_mirror(&mut self) {
        self.build_order();
        let n = self.order.len();
        let Tree { nodes, order, .. } = self;
        for idx in 0..n {
            let v = order[idx];
            nodes[v].ch.reverse();
        }
    }

    fn op_cut(&mut self, name: &[u8]) {
        if let Some(v) = self.find_node(name) {
            let p = self.par[v];
            if p != usize::MAX {
                let children = std::mem::take(&mut self.nodes[v].ch);
                let pos = self.nodes[p]
                    .ch
                    .iter()
                    .position(|&c| c == v)
                    .unwrap();
                self.nodes[p].ch.splice(pos..pos + 1, children);
            }
        }
    }

    fn op_fold(&mut self) {
        let mut queue: Vec<usize> = vec![self.root];
        let mut qi = 0;
        while qi < queue.len() {
            let u = queue[qi];
            qi += 1;
            let len = self.nodes[u].ch.len();
            let mut newch: Vec<usize> = Vec::with_capacity(len);
            for k in 0..len {
                let mut c = self.nodes[u].ch[k];
                loop {
                    if self.nodes[c].ch.len() == 1 {
                        let g = self.nodes[c].ch[0];
                        let cns = self.nodes[c].ns;
                        let cnl = self.nodes[c].nl;
                        let cw = self.nodes[c].w;
                        let gns = self.nodes[g].ns;
                        let gnl = self.nodes[g].nl;
                        let gw = self.nodes[g].w;
                        let gch = std::mem::take(&mut self.nodes[g].ch);
                        let mut nm = Vec::with_capacity(cnl + 1 + gnl);
                        nm.extend_from_slice(&self.names[cns..cns + cnl]);
                        nm.push(b'+');
                        nm.extend_from_slice(&self.names[gns..gns + gnl]);
                        let ns = self.names.len();
                        let nl = nm.len();
                        self.names.extend_from_slice(&nm);
                        let idx = self.nodes.len();
                        self.nodes.push(Node {
                            ns,
                            nl,
                            w: cw + gw,
                            ch: gch,
                        });
                        c = idx;
                    } else {
                        break;
                    }
                }
                newch.push(c);
                queue.push(c);
            }
            self.nodes[u].ch = newch;
        }
    }
}

fn push_num(buf: &mut Vec<u8>, mut x: u64) {
    if x == 0 {
        buf.push(b'0');
        return;
    }
    let mut tmp = [0u8; 20];
    let mut i = 20;
    while x > 0 {
        i -= 1;
        tmp[i] = (x % 10) as u8 + b'0';
        x /= 10;
    }
    buf.extend_from_slice(&tmp[i..]);
}

fn parse_name(b: &[u8]) -> Option<Vec<u8>> {
    if b.is_empty() {
        return None;
    }
    for &c in b {
        if !(c.is_ascii_lowercase() || c == b'+') {
            return None;
        }
    }
    Some(b.to_vec())
}

fn parse_num(b: &[u8]) -> Option<u64> {
    if b.is_empty() {
        return None;
    }
    if b.len() > 1 && b[0] == b'0' {
        return None;
    }
    let mut v: u64 = 0;
    for &c in b {
        if !c.is_ascii_digit() {
            return None;
        }
        v = v.checked_mul(10)?.checked_add((c - b'0') as u64)?;
    }
    if v > 1_000_000_000_000_000 {
        return None;
    }
    Some(v)
}

fn parse_ops(lines: &[&[u8]]) -> Option<Vec<Op>> {
    let mut ops = Vec::with_capacity(lines.len());
    for &line in lines {
        if line.is_empty() {
            return None;
        }
        let op = if line == b"total" {
            Op::Total
        } else if line == b"stats" {
            Op::Stats
        } else if line == b"print" {
            Op::Print
        } else if line == b"sort" {
            Op::Sort
        } else if line == b"mirror" {
            Op::Mirror
        } else if line == b"fold" {
            Op::Fold
        } else if let Some(rest) = line.strip_prefix(b"level ") {
            Op::Level(parse_num(rest)?)
        } else if let Some(rest) = line.strip_prefix(b"prune ") {
            Op::Prune(parse_num(rest)?)
        } else if let Some(rest) = line.strip_prefix(b"find ") {
            Op::Find(parse_name(rest)?)
        } else if let Some(rest) = line.strip_prefix(b"cut ") {
            Op::Cut(parse_name(rest)?)
        } else {
            return None;
        };
        ops.push(op);
    }
    Some(ops)
}

fn parse_tree(line: &[u8]) -> Option<Tree> {
    let b = line;
    let n = b.len();
    if n == 0 {
        return None;
    }
    let mut t = Tree {
        names: Vec::new(),
        nodes: Vec::new(),
        root: 0,
        par: Vec::new(),
        sub: Vec::new(),
        order: Vec::new(),
        depth: Vec::new(),
    };
    let mut i = 0usize;
    let mut stack: Vec<usize> = Vec::new();
    let mut cur: Option<usize> = None;
    let mut can_open = true;
    loop {
        if cur.is_none() {
            let start = i;
            while i < n && b[i].is_ascii_lowercase() {
                i += 1;
            }
            let namelen = i - start;
            if namelen == 0 || namelen > 16 {
                return None;
            }
            if i >= n || b[i] != b':' {
                return None;
            }
            let ns = t.names.len();
            t.names.extend_from_slice(&b[start..i]);
            i += 1;
            let ws = i;
            while i < n && b[i].is_ascii_digit() {
                i += 1;
            }
            if i == ws {
                return None;
            }
            let wbytes = &b[ws..i];
            if wbytes.len() > 1 && wbytes[0] == b'0' {
                return None;
            }
            if wbytes.len() > 7 {
                return None;
            }
            let mut w: u64 = 0;
            for &d in wbytes {
                w = w * 10 + (d - b'0') as u64;
            }
            if w > 1_000_000 {
                return None;
            }
            let idx = t.nodes.len();
            t.nodes.push(Node {
                ns,
                nl: namelen,
                w,
                ch: Vec::new(),
            });
            if let Some(&p) = stack.last() {
                t.nodes[p].ch.push(idx);
            }
            cur = Some(idx);
            can_open = true;
        }
        if i >= n {
            if !stack.is_empty() {
                return None;
            }
            break;
        }
        match b[i] {
            b'[' => {
                if !can_open {
                    return None;
                }
                can_open = false;
                i += 1;
                if i >= n || b[i] == b']' {
                    return None;
                }
                stack.push(cur.unwrap());
                cur = None;
            }
            b']' => {
                if stack.is_empty() {
                    return None;
                }
                i += 1;
                stack.pop();
                can_open = false;
            }
            b' ' => {
                if stack.is_empty() {
                    return None;
                }
                i += 1;
                if i >= n {
                    return None;
                }
                let nx = b[i];
                if nx == b' ' || nx == b']' || nx == b'[' {
                    return None;
                }
                cur = None;
                can_open = true;
            }
            _ => return None,
        }
    }
    if t.nodes.is_empty() {
        return None;
    }
    t.root = 0;
    Some(t)
}

fn main() {
    let mut data: Vec<u8> = Vec::new();
    if io::stdin().read_to_end(&mut data).is_err() {
        std::process::exit(1);
    }
    if data.contains(&b'\r') {
        std::process::exit(1);
    }
    let mut lines: Vec<&[u8]> = data.split(|&b| b == b'\n').collect();
    if let Some(last) = lines.last() {
        if last.is_empty() {
            lines.pop();
        }
    }
    if lines.is_empty() || lines[0].is_empty() {
        std::process::exit(1);
    }
    let mut tree = match parse_tree(lines[0]) {
        Some(t) => t,
        None => std::process::exit(1),
    };
    let ops = match parse_ops(&lines[1..]) {
        Some(o) => o,
        None => std::process::exit(1),
    };

    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());

    for op in ops {
        let r: io::Result<()> = match op {
            Op::Total => tree.op_total(&mut out),
            Op::Stats => tree.op_stats(&mut out),
            Op::Level(d) => tree.op_level(d, &mut out),
            Op::Find(name) => tree.op_find(&name, &mut out),
            Op::Print => tree.op_print(&mut out),
            Op::Prune(w) => {
                tree.op_prune(w);
                Ok(())
            }
            Op::Sort => {
                tree.op_sort();
                Ok(())
            }
            Op::Mirror => {
                tree.op_mirror();
                Ok(())
            }
            Op::Fold => {
                tree.op_fold();
                Ok(())
            }
            Op::Cut(name) => {
                tree.op_cut(&name);
                Ok(())
            }
        };
        if r.is_err() {
            break;
        }
    }
    let _ = out.flush();
}
