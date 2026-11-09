use std::io::{self, Read, Write};

const NONE: usize = usize::MAX;

struct Node {
    name: Vec<u8>,
    weight: u64,
    children: Vec<usize>,
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

enum Item {
    Node(usize),
    Lit(u8),
}

fn fail() -> ! {
    std::process::exit(1);
}

fn parse_tree(line: &[u8], nodes: &mut Vec<Node>) -> bool {
    let len = line.len();
    let mut pos = 0usize;
    let mut stack: Vec<usize> = Vec::new();
    let mut has_root = false;
    'outer: loop {
        let start = pos;
        while pos < len && line[pos].is_ascii_lowercase() {
            pos += 1;
        }
        let nl = pos - start;
        if nl == 0 || nl > 16 {
            return false;
        }
        let name = line[start..pos].to_vec();
        if pos >= len || line[pos] != b':' {
            return false;
        }
        pos += 1;
        let ws = pos;
        while pos < len && line[pos].is_ascii_digit() {
            pos += 1;
        }
        let wl = pos - ws;
        if wl == 0 || wl > 7 || (wl > 1 && line[ws] == b'0') {
            return false;
        }
        let mut w: u64 = 0;
        for &b in &line[ws..pos] {
            w = w * 10 + (b - b'0') as u64;
        }
        if w > 1_000_000 {
            return false;
        }
        let id = nodes.len();
        nodes.push(Node {
            name,
            weight: w,
            children: Vec::new(),
        });
        match stack.last() {
            Some(&p) => nodes[p].children.push(id),
            None => {
                if has_root {
                    return false;
                }
                has_root = true;
            }
        }
        if pos < len && line[pos] == b'[' {
            pos += 1;
            stack.push(id);
            continue 'outer;
        }
        loop {
            if pos == len {
                return stack.is_empty();
            }
            match line[pos] {
                b']' => {
                    if stack.is_empty() {
                        return false;
                    }
                    stack.pop();
                    pos += 1;
                }
                b' ' => {
                    if stack.is_empty() {
                        return false;
                    }
                    pos += 1;
                    continue 'outer;
                }
                _ => return false,
            }
        }
    }
}

fn parse_num(s: &[u8]) -> Option<u64> {
    if s.is_empty() || s.len() > 16 || !s.iter().all(|b| b.is_ascii_digit()) {
        return None;
    }
    if s.len() > 1 && s[0] == b'0' {
        return None;
    }
    let mut v: u64 = 0;
    for &b in s {
        v = v * 10 + (b - b'0') as u64;
    }
    if v > 1_000_000_000_000_000 {
        return None;
    }
    Some(v)
}

fn valid_name(s: &[u8]) -> bool {
    !s.is_empty() && s.iter().all(|&b| b.is_ascii_lowercase() || b == b'+')
}

fn parse_op(l: &[u8]) -> Option<Op> {
    if l == b"total" {
        return Some(Op::Total);
    }
    if l == b"stats" {
        return Some(Op::Stats);
    }
    if l == b"print" {
        return Some(Op::Print);
    }
    if l == b"sort" {
        return Some(Op::Sort);
    }
    if l == b"mirror" {
        return Some(Op::Mirror);
    }
    if l == b"fold" {
        return Some(Op::Fold);
    }
    if l.starts_with(b"level ") {
        return parse_num(&l[6..]).map(Op::Level);
    }
    if l.starts_with(b"prune ") {
        return parse_num(&l[6..]).map(Op::Prune);
    }
    if l.starts_with(b"find ") {
        let r = &l[5..];
        return if valid_name(r) {
            Some(Op::Find(r.to_vec()))
        } else {
            None
        };
    }
    if l.starts_with(b"cut ") {
        let r = &l[4..];
        return if valid_name(r) {
            Some(Op::Cut(r.to_vec()))
        } else {
            None
        };
    }
    None
}

fn traverse(nodes: &[Node]) -> (Vec<usize>, Vec<usize>, Vec<u64>) {
    let n = nodes.len();
    let mut parent = vec![NONE; n];
    let mut depth = vec![0u64; n];
    let mut order = Vec::new();
    let mut stack = vec![0usize];
    while let Some(x) = stack.pop() {
        order.push(x);
        for &c in nodes[x].children.iter().rev() {
            parent[c] = x;
            depth[c] = depth[x] + 1;
            stack.push(c);
        }
    }
    (order, parent, depth)
}

fn subtree_sums(nodes: &[Node], order: &[usize]) -> Vec<u64> {
    let mut sub = vec![0u64; nodes.len()];
    for &x in order.iter().rev() {
        let mut s = nodes[x].weight;
        for &c in &nodes[x].children {
            s += sub[c];
        }
        sub[x] = s;
    }
    sub
}

fn main() {
    let mut input = Vec::new();
    if io::stdin().read_to_end(&mut input).is_err() {
        fail();
    }
    if input.contains(&b'\r') {
        fail();
    }
    let mut lines: Vec<&[u8]> = input.split(|&b| b == b'\n').collect();
    if lines.last().map_or(false, |l| l.is_empty()) {
        lines.pop();
    }
    if lines.is_empty() || lines.iter().any(|l| l.is_empty()) {
        fail();
    }

    let mut nodes: Vec<Node> = Vec::new();
    if !parse_tree(lines[0], &mut nodes) {
        fail();
    }

    let mut ops: Vec<Op> = Vec::with_capacity(lines.len());
    for &l in &lines[1..] {
        match parse_op(l) {
            Some(o) => ops.push(o),
            None => fail(),
        }
    }

    let mut out: Vec<u8> = Vec::new();

    for op in ops {
        match op {
            Op::Total => {
                let (order, _, _) = traverse(&nodes);
                let s: u64 = order.iter().map(|&x| nodes[x].weight).sum();
                writeln!(out, "{}", s).unwrap();
            }
            Op::Stats => {
                let (order, _, depth) = traverse(&nodes);
                let mut leaves = 0u64;
                let mut height = 0u64;
                let mut widest = 0usize;
                for &x in &order {
                    if nodes[x].children.is_empty() {
                        leaves += 1;
                    }
                    height = height.max(depth[x]);
                    widest = widest.max(nodes[x].children.len());
                }
                writeln!(
                    out,
                    "nodes={} leaves={} height={} widest={}",
                    order.len(),
                    leaves,
                    height,
                    widest
                )
                .unwrap();
            }
            Op::Level(d) => {
                let (order, _, depth) = traverse(&nodes);
                let mut c = 0u64;
                let mut s = 0u64;
                for &x in &order {
                    if depth[x] == d {
                        c += 1;
                        s += nodes[x].weight;
                    }
                }
                writeln!(out, "{} {}", c, s).unwrap();
            }
            Op::Find(name) => {
                let (order, parent, _) = traverse(&nodes);
                match order.iter().find(|&&x| nodes[x].name == name) {
                    None => {
                        out.extend_from_slice(b"none\n");
                    }
                    Some(&x) => {
                        let mut path = Vec::new();
                        let mut y = x;
                        loop {
                            path.push(y);
                            if y == 0 {
                                break;
                            }
                            y = parent[y];
                        }
                        path.reverse();
                        for (i, &p) in path.iter().enumerate() {
                            if i > 0 {
                                out.push(b'/');
                            }
                            out.extend_from_slice(&nodes[p].name);
                        }
                        out.push(b'\n');
                    }
                }
            }
            Op::Print => {
                let mut st = vec![Item::Node(0)];
                while let Some(it) = st.pop() {
                    match it {
                        Item::Lit(b) => out.push(b),
                        Item::Node(x) => {
                            out.extend_from_slice(&nodes[x].name);
                            out.push(b':');
                            write!(out, "{}", nodes[x].weight).unwrap();
                            let ch = &nodes[x].children;
                            if !ch.is_empty() {
                                out.push(b'[');
                                st.push(Item::Lit(b']'));
                                for j in (0..ch.len()).rev() {
                                    st.push(Item::Node(ch[j]));
                                    if j > 0 {
                                        st.push(Item::Lit(b' '));
                                    }
                                }
                            }
                        }
                    }
                }
                out.push(b'\n');
            }
            Op::Prune(w) => {
                let (order, _, _) = traverse(&nodes);
                let sub = subtree_sums(&nodes, &order);
                let mut st = vec![0usize];
                while let Some(x) = st.pop() {
                    let mut ch = std::mem::take(&mut nodes[x].children);
                    ch.retain(|&c| sub[c] >= w);
                    st.extend_from_slice(&ch);
                    nodes[x].children = ch;
                }
            }
            Op::Sort => {
                let (order, _, _) = traverse(&nodes);
                let sub = subtree_sums(&nodes, &order);
                for &x in &order {
                    let mut ch = std::mem::take(&mut nodes[x].children);
                    ch.sort_by(|&a, &b| {
                        sub[b]
                            .cmp(&sub[a])
                            .then_with(|| nodes[a].name.cmp(&nodes[b].name))
                    });
                    nodes[x].children = ch;
                }
            }
            Op::Mirror => {
                let (order, _, _) = traverse(&nodes);
                for &x in &order {
                    nodes[x].children.reverse();
                }
            }
            Op::Fold => {
                let mut stack = vec![0usize];
                while let Some(u) = stack.pop() {
                    let len = nodes[u].children.len();
                    for j in 0..len {
                        let c = nodes[u].children[j];
                        while nodes[c].children.len() == 1 {
                            let g = nodes[c].children[0];
                            let gname = std::mem::take(&mut nodes[g].name);
                            let gw = nodes[g].weight;
                            let gch = std::mem::take(&mut nodes[g].children);
                            let cn = &mut nodes[c];
                            cn.name.push(b'+');
                            cn.name.extend_from_slice(&gname);
                            cn.weight += gw;
                            cn.children = gch;
                        }
                        stack.push(c);
                    }
                }
            }
            Op::Cut(name) => {
                let (order, parent, _) = traverse(&nodes);
                if let Some(&x) = order.iter().find(|&&x| nodes[x].name == name) {
                    if x != 0 {
                        let p = parent[x];
                        let pos = nodes[p]
                            .children
                            .iter()
                            .position(|&c| c == x)
                            .unwrap();
                        let kids = std::mem::take(&mut nodes[x].children);
                        nodes[p].children.splice(pos..pos + 1, kids);
                    }
                }
            }
        }
    }

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = lock.write_all(&out);
    let _ = lock.flush();
}
