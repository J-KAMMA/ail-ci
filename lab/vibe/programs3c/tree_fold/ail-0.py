import sys
import re


class Bad(Exception):
    pass


NUM_RE = re.compile(r'0|[1-9][0-9]{0,15}')
NAME_RE = re.compile(r'[a-z+]+')


def parse_tree(s):
    n = len(s)
    pos = 0
    root = None
    stack = []
    while True:
        start = pos
        while pos < n and 'a' <= s[pos] <= 'z':
            pos += 1
        ln = pos - start
        if ln < 1 or ln > 16:
            raise Bad()
        name = s[start:pos]
        if pos >= n or s[pos] != ':':
            raise Bad()
        pos += 1
        start = pos
        while pos < n and '0' <= s[pos] <= '9':
            pos += 1
        dl = pos - start
        if dl < 1 or dl > 7:
            raise Bad()
        if dl > 1 and s[start] == '0':
            raise Bad()
        w = int(s[start:pos])
        if w > 1000000:
            raise Bad()
        node = [name, w, [], 0]
        if stack:
            stack[-1][2].append(node)
        else:
            if root is not None:
                raise Bad()
            root = node
        if pos < n and s[pos] == '[':
            stack.append(node)
            pos += 1
            continue
        while True:
            if pos == n:
                if stack:
                    raise Bad()
                return root
            c = s[pos]
            if c == ']':
                if not stack:
                    raise Bad()
                stack.pop()
                pos += 1
            elif c == ' ':
                if not stack:
                    raise Bad()
                pos += 1
                break
            else:
                raise Bad()


def parse_ops(lines):
    ops = []
    for line in lines:
        if line == '':
            raise Bad()
        parts = line.split(' ')
        kw = parts[0]
        if kw in ('total', 'stats', 'print', 'sort', 'mirror', 'fold'):
            if len(parts) != 1:
                raise Bad()
            ops.append((kw, None))
        elif kw == 'level' or kw == 'prune':
            if len(parts) != 2:
                raise Bad()
            a = parts[1]
            if NUM_RE.fullmatch(a) is None:
                raise Bad()
            v = int(a)
            if v > 1000000000000000:
                raise Bad()
            ops.append((kw, v))
        elif kw == 'find' or kw == 'cut':
            if len(parts) != 2:
                raise Bad()
            a = parts[1]
            if NAME_RE.fullmatch(a) is None:
                raise Bad()
            ops.append((kw, a))
        else:
            raise Bad()
    return ops


def preorder(root):
    order = []
    st = [root]
    while st:
        nd = st.pop()
        order.append(nd)
        st.extend(reversed(nd[2]))
    return order


def compute_sub(root):
    order = preorder(root)
    for nd in reversed(order):
        s = nd[1]
        for c in nd[2]:
            s += c[3]
        nd[3] = s
    return order


def total(root):
    s = 0
    st = [root]
    while st:
        nd = st.pop()
        s += nd[1]
        st.extend(nd[2])
    return s


def stats(root):
    n = 0
    leaves = 0
    height = 0
    widest = 0
    st = [(root, 0)]
    while st:
        nd, d = st.pop()
        n += 1
        ch = nd[2]
        if not ch:
            leaves += 1
        elif len(ch) > widest:
            widest = len(ch)
        if d > height:
            height = d
        for c in ch:
            st.append((c, d + 1))
    return 'nodes=' + str(n) + ' leaves=' + str(leaves) + ' height=' + str(height) + ' widest=' + str(widest)


def level(root, D):
    cnt = 0
    sm = 0
    st = [(root, 0)]
    while st:
        nd, d = st.pop()
        if d == D:
            cnt += 1
            sm += nd[1]
        elif d < D:
            for c in nd[2]:
                st.append((c, d + 1))
    return str(cnt) + ' ' + str(sm)


def find_path(root, name):
    anc = []
    st = [(root, 0)]
    while st:
        nd, d = st.pop()
        if len(anc) == d:
            anc.append(nd[0])
        else:
            anc[d] = nd[0]
        if nd[0] == name:
            return '/'.join(anc[:d + 1])
        ch = nd[2]
        for i in range(len(ch) - 1, -1, -1):
            st.append((ch[i], d + 1))
    return 'none'


def serialize(root):
    out = []
    st = [root]
    while st:
        it = st.pop()
        if type(it) is str:
            out.append(it)
            continue
        out.append(it[0] + ':' + str(it[1]))
        ch = it[2]
        if ch:
            st.append(']')
            for i in range(len(ch) - 1, -1, -1):
                st.append(ch[i])
                if i > 0:
                    st.append(' ')
            st.append('[')
    return ''.join(out)


def prune(root, W):
    compute_sub(root)
    st = [root]
    while st:
        nd = st.pop()
        kept = [c for c in nd[2] if c[3] >= W]
        nd[2] = kept
        st.extend(kept)


def sort_key(c):
    return (-c[3], c[0])


def sort_tree(root):
    order = compute_sub(root)
    for nd in order:
        if len(nd[2]) > 1:
            nd[2].sort(key=sort_key)


def mirror(root):
    for nd in preorder(root):
        nd[2].reverse()


def fold(root):
    st = list(root[2])
    while st:
        nd = st.pop()
        ch = nd[2]
        if len(ch) == 1:
            parts = [nd[0]]
            w = nd[1]
            while len(ch) == 1:
                c = ch[0]
                parts.append(c[0])
                w += c[1]
                ch = c[2]
            nd[0] = '+'.join(parts)
            nd[1] = w
            nd[2] = ch
        st.extend(ch)


def cut(root, name):
    st = [(root, None)]
    found = None
    while st:
        nd, par = st.pop()
        if nd[0] == name:
            found = (nd, par)
            break
        ch = nd[2]
        for i in range(len(ch) - 1, -1, -1):
            st.append((ch[i], nd))
    if found is None:
        return
    nd, par = found
    if par is None:
        return
    idx = 0
    for i, c in enumerate(par[2]):
        if c is nd:
            idx = i
            break
    par[2] = par[2][:idx] + nd[2] + par[2][idx + 1:]


def main():
    raw = sys.stdin.buffer.read().decode('latin-1')
    if '\r' in raw:
        sys.exit(1)
    lines = raw.split('\n')
    if lines[-1] == '':
        lines.pop()
    try:
        for ln in lines:
            if ln == '':
                raise Bad()
        if not lines:
            raise Bad()
        root = parse_tree(lines[0])
        ops = parse_ops(lines[1:])
    except Bad:
        sys.exit(1)

    out = []
    for kw, arg in ops:
        if kw == 'total':
            out.append(str(total(root)) + '\n')
        elif kw == 'stats':
            out.append(stats(root) + '\n')
        elif kw == 'level':
            out.append(level(root, arg) + '\n')
        elif kw == 'find':
            out.append(find_path(root, arg) + '\n')
        elif kw == 'print':
            out.append(serialize(root) + '\n')
        elif kw == 'prune':
            prune(root, arg)
        elif kw == 'sort':
            sort_tree(root)
        elif kw == 'mirror':
            mirror(root)
        elif kw == 'fold':
            fold(root)
        elif kw == 'cut':
            cut(root, arg)
    sys.stdout.write(''.join(out))


main()
