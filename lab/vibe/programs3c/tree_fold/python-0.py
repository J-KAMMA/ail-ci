import sys
import re


class Bad(Exception):
    pass


class Node:
    __slots__ = ('name', 'weight', 'children', 'sub')

    def __init__(self, name, weight):
        self.name = name
        self.weight = weight
        self.children = []
        self.sub = 0


HEAD = re.compile(r'([a-z]+):([0-9]+)')
NAME_RE = re.compile(r'[a-z+]+')
SIMPLE = {'total', 'stats', 'print', 'sort', 'mirror', 'fold'}


def parse_tree(s):
    n = len(s)
    i = 0
    stack = []
    root = None
    while True:
        m = HEAD.match(s, i)
        if m is None:
            raise Bad()
        name = m.group(1)
        if len(name) > 16:
            raise Bad()
        digits = m.group(2)
        if len(digits) > 1 and digits[0] == '0':
            raise Bad()
        w = int(digits)
        if w > 1000000:
            raise Bad()
        node = Node(name, w)
        if stack:
            stack[-1].children.append(node)
        else:
            root = node
        i = m.end()
        if i < n and s[i] == '[':
            stack.append(node)
            i += 1
            continue
        while True:
            if not stack:
                if i != n:
                    raise Bad()
                return root
            if i < n and s[i] == ' ':
                i += 1
                break
            if i < n and s[i] == ']':
                i += 1
                stack.pop()
                continue
            raise Bad()


def parse_num(t):
    if not t or not all('0' <= c <= '9' for c in t):
        raise Bad()
    if len(t) > 1 and t[0] == '0':
        raise Bad()
    v = int(t)
    if v > 10 ** 15:
        raise Bad()
    return v


def parse_ops(lines):
    ops = []
    for ln in lines:
        if ln in SIMPLE:
            ops.append((ln, None))
        elif ln.startswith('level '):
            ops.append(('level', parse_num(ln[6:])))
        elif ln.startswith('prune '):
            ops.append(('prune', parse_num(ln[6:])))
        elif ln.startswith('find '):
            nm = ln[5:]
            if not NAME_RE.fullmatch(nm):
                raise Bad()
            ops.append(('find', nm))
        elif ln.startswith('cut '):
            nm = ln[4:]
            if not NAME_RE.fullmatch(nm):
                raise Bad()
            ops.append(('cut', nm))
        else:
            raise Bad()
    return ops


def walk(root):
    stack = [(root, 0, None)]
    while stack:
        nd, d, p = stack.pop()
        yield nd, d, p
        ch = nd.children
        for c in reversed(ch):
            stack.append((c, d + 1, nd))


def compute_sub(root):
    pre = [nd for nd, _, _ in walk(root)]
    for nd in reversed(pre):
        s = nd.weight
        for c in nd.children:
            s += c.sub
        nd.sub = s


def render(root):
    out = []
    stack = [root]
    while stack:
        it = stack.pop()
        if isinstance(it, str):
            out.append(it)
            continue
        out.append(f"{it.name}:{it.weight}")
        ch = it.children
        if ch:
            stack.append(']')
            for idx in range(len(ch) - 1, -1, -1):
                stack.append(ch[idx])
                if idx > 0:
                    stack.append(' ')
            stack.append('[')
    return ''.join(out)


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    try:
        if '\r' in data:
            raise Bad()
        if data.endswith('\n'):
            data = data[:-1]
        lines = data.split('\n')
        for ln in lines:
            if ln == '':
                raise Bad()
        root = parse_tree(lines[0])
        ops = parse_ops(lines[1:])
    except Bad:
        sys.exit(1)

    out = []
    for op, arg in ops:
        if op == 'total':
            t = 0
            for nd, _, _ in walk(root):
                t += nd.weight
            out.append(f"{t}\n")
        elif op == 'stats':
            n = 0
            leaves = 0
            h = 0
            wd = 0
            for nd, d, _ in walk(root):
                n += 1
                if not nd.children:
                    leaves += 1
                if d > h:
                    h = d
                if len(nd.children) > wd:
                    wd = len(nd.children)
            out.append(f"nodes={n} leaves={leaves} height={h} widest={wd}\n")
        elif op == 'level':
            cnt = 0
            sm = 0
            for nd, d, _ in walk(root):
                if d == arg:
                    cnt += 1
                    sm += nd.weight
            out.append(f"{cnt} {sm}\n")
        elif op == 'find':
            anc = []
            res = None
            for nd, d, _ in walk(root):
                del anc[d:]
                anc.append(nd)
                if nd.name == arg:
                    res = '/'.join(a.name for a in anc)
                    break
            out.append((res if res is not None else 'none') + '\n')
        elif op == 'print':
            out.append(render(root) + '\n')
        elif op == 'prune':
            compute_sub(root)
            for nd, _, _ in walk(root):
                nd.children = [c for c in nd.children if c.sub >= arg]
        elif op == 'sort':
            compute_sub(root)
            for nd, _, _ in walk(root):
                nd.children.sort(key=lambda c: (-c.sub, c.name))
        elif op == 'mirror':
            for nd, _, _ in walk(root):
                nd.children.reverse()
        elif op == 'fold':
            stack = [root]
            while stack:
                x = stack.pop()
                if x is not root:
                    parts = [x.name]
                    w = x.weight
                    while len(x.children) == 1:
                        c = x.children[0]
                        parts.append(c.name)
                        w += c.weight
                        x.children = c.children
                    x.name = '+'.join(parts)
                    x.weight = w
                stack.extend(x.children)
        elif op == 'cut':
            for nd, d, p in walk(root):
                if nd.name == arg:
                    if p is not None:
                        idx = p.children.index(nd)
                        p.children[idx:idx + 1] = nd.children
                    break

    sys.stdout.write(''.join(out))
    sys.exit(0)


if __name__ == '__main__':
    main()
