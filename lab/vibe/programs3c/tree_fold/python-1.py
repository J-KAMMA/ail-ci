import sys
import re

TOK = re.compile(r'[a-z]+|[0-9]+|.', re.DOTALL)
NUM_RE = re.compile(r'0|[1-9][0-9]*')
NAME_RE = re.compile(r'[a-z+]+')
NOARG = {'total', 'stats', 'print', 'sort', 'mirror', 'fold'}
NUMARG = {'level', 'prune'}
NAMEARG = {'find', 'cut'}


def parse_tree(s):
    toks = TOK.findall(s)
    n = len(toks)
    i = 0
    stack = []
    root = None
    while True:
        if i >= n:
            return None
        t = toks[i]
        if not ('a' <= t[0] <= 'z') or len(t) > 16:
            return None
        i += 1
        if i >= n or toks[i] != ':':
            return None
        i += 1
        if i >= n:
            return None
        wt = toks[i]
        if not ('0' <= wt[0] <= '9'):
            return None
        if len(wt) > 1 and wt[0] == '0':
            return None
        if len(wt) > 8:
            return None
        w = int(wt)
        if w > 1000000:
            return None
        i += 1
        node = [t, w, [], 0]
        if stack:
            stack[-1][2].append(node)
        elif root is None:
            root = node
        else:
            return None
        if i < n and toks[i] == '[':
            stack.append(node)
            i += 1
            continue
        while True:
            if i == n:
                return root if not stack else None
            t2 = toks[i]
            if t2 == ']':
                if not stack:
                    return None
                stack.pop()
                i += 1
            elif t2 == ' ':
                if not stack:
                    return None
                i += 1
                break
            else:
                return None


def preorder(root):
    order = []
    stack = [(root, 0)]
    while stack:
        node, d = stack.pop()
        order.append((node, d))
        ch = node[2]
        for k in range(len(ch) - 1, -1, -1):
            stack.append((ch[k], d + 1))
    return order


def compute_sub(order):
    for node, _ in reversed(order):
        s = node[1]
        for c in node[2]:
            s += c[3]
        node[3] = s


def serialize(root):
    out = []
    stack = [root]
    while stack:
        it = stack.pop()
        if it.__class__ is str:
            out.append(it)
            continue
        out.append(f"{it[0]}:{it[1]}")
        ch = it[2]
        if ch:
            stack.append(']')
            for idx in range(len(ch) - 1, -1, -1):
                stack.append(ch[idx])
                if idx > 0:
                    stack.append(' ')
            out.append('[')
    return ''.join(out)


def find_path(root, name):
    stack = [(root, None)]
    while stack:
        node, anc = stack.pop()
        if node[0] == name:
            parts = []
            cur = (node[0], anc)
            while cur is not None:
                parts.append(cur[0])
                cur = cur[1]
            parts.reverse()
            return '/'.join(parts)
        ch = node[2]
        if ch:
            link = (node[0], anc)
            for k in range(len(ch) - 1, -1, -1):
                stack.append((ch[k], link))
    return None


def fold(root):
    stack = [root]
    while stack:
        n = stack.pop()
        for c in n[2]:
            if len(c[2]) == 1:
                parts = [c[0]]
                w = c[1]
                cur = c
                while len(cur[2]) == 1:
                    cur = cur[2][0]
                    parts.append(cur[0])
                    w += cur[1]
                c[0] = '+'.join(parts)
                c[1] = w
                c[2] = cur[2]
            stack.append(c)


def cut(root, name):
    stack = [(root, None)]
    while stack:
        node, par = stack.pop()
        if node[0] == name:
            if par is not None:
                pch = par[2]
                idx = 0
                for i, c in enumerate(pch):
                    if c is node:
                        idx = i
                        break
                pch[idx:idx + 1] = node[2]
            return
        ch = node[2]
        for k in range(len(ch) - 1, -1, -1):
            stack.append((ch[k], node))


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    if '\r' in data:
        return 1
    lines = data.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if not lines:
        return 1
    if any(l == '' for l in lines):
        return 1
    root = parse_tree(lines[0])
    if root is None:
        return 1

    ops = []
    for line in lines[1:]:
        cmd, sep, arg = line.partition(' ')
        if cmd in NOARG:
            if sep:
                return 1
            ops.append((cmd, None))
        elif cmd in NUMARG:
            if not sep or len(arg) > 16 or not NUM_RE.fullmatch(arg):
                return 1
            v = int(arg)
            if v > 10 ** 15:
                return 1
            ops.append((cmd, v))
        elif cmd in NAMEARG:
            if not sep or not NAME_RE.fullmatch(arg):
                return 1
            ops.append((cmd, arg))
        else:
            return 1

    out = []
    for cmd, arg in ops:
        if cmd == 'total':
            order = preorder(root)
            out.append(str(sum(n[1] for n, _ in order)))
        elif cmd == 'stats':
            order = preorder(root)
            nodes = len(order)
            leaves = sum(1 for n, _ in order if not n[2])
            height = max(d for _, d in order)
            widest = max(len(n[2]) for n, _ in order)
            out.append(f"nodes={nodes} leaves={leaves} height={height} widest={widest}")
        elif cmd == 'level':
            cnt = 0
            s = 0
            for n, d in preorder(root):
                if d == arg:
                    cnt += 1
                    s += n[1]
            out.append(f"{cnt} {s}")
        elif cmd == 'find':
            res = find_path(root, arg)
            out.append(res if res is not None else 'none')
        elif cmd == 'print':
            out.append(serialize(root))
        elif cmd == 'prune':
            order = preorder(root)
            compute_sub(order)
            stack = [root]
            while stack:
                n = stack.pop()
                ch = [c for c in n[2] if c[3] >= arg]
                n[2] = ch
                stack.extend(ch)
        elif cmd == 'sort':
            order = preorder(root)
            compute_sub(order)
            for n, _ in order:
                if len(n[2]) > 1:
                    n[2].sort(key=lambda c: (-c[3], c[0]))
        elif cmd == 'mirror':
            for n, _ in preorder(root):
                n[2].reverse()
        elif cmd == 'fold':
            fold(root)
        elif cmd == 'cut':
            cut(root, arg)

    if out:
        sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
