import sys


class Bad(Exception):
    pass


def parse_tree(s):
    n = len(s)
    pos = 0
    stack = []
    root = None
    while True:
        st = pos
        while pos < n and 'a' <= s[pos] <= 'z':
            pos += 1
        ln = pos - st
        if ln < 1 or ln > 16:
            raise Bad()
        name = s[st:pos]
        if pos >= n or s[pos] != ':':
            raise Bad()
        pos += 1
        st = pos
        while pos < n and '0' <= s[pos] <= '9':
            pos += 1
        ds = s[st:pos]
        if len(ds) == 0 or (len(ds) > 1 and ds[0] == '0'):
            raise Bad()
        w = int(ds)
        if w > 1000000:
            raise Bad()
        node = [name, w, [], 0]
        if stack:
            stack[-1][2].append(node)
        else:
            root = node
        if pos < n and s[pos] == '[':
            pos += 1
            stack.append(node)
            continue
        while True:
            if pos == n:
                if stack:
                    raise Bad()
                return root
            c = s[pos]
            if c == ' ':
                if not stack:
                    raise Bad()
                pos += 1
                break
            if c == ']':
                if not stack:
                    raise Bad()
                stack.pop()
                pos += 1
                continue
            raise Bad()


def parse_num(s):
    if len(s) == 0:
        raise Bad()
    for ch in s:
        if not ('0' <= ch <= '9'):
            raise Bad()
    if len(s) > 1 and s[0] == '0':
        raise Bad()
    v = int(s)
    if v > 10 ** 15:
        raise Bad()
    return v


def check_name(s):
    if len(s) == 0:
        raise Bad()
    for ch in s:
        if not (('a' <= ch <= 'z') or ch == '+'):
            raise Bad()
    return s


def parse_op(line):
    if line in ('total', 'stats', 'print', 'sort', 'mirror', 'fold'):
        return (line, None)
    if line.startswith('level '):
        return ('level', parse_num(line[6:]))
    if line.startswith('prune '):
        return ('prune', parse_num(line[6:]))
    if line.startswith('find '):
        return ('find', check_name(line[5:]))
    if line.startswith('cut '):
        return ('cut', check_name(line[4:]))
    raise Bad()


def walk(root):
    res = []
    st = [(root, 0)]
    while st:
        nd, d = st.pop()
        res.append((nd, d))
        ch = nd[2]
        k = len(ch) - 1
        while k >= 0:
            st.append((ch[k], d + 1))
            k -= 1
    return res


def compute_sub(W):
    for i in range(len(W) - 1, -1, -1):
        nd = W[i][0]
        s = nd[1]
        for c in nd[2]:
            s += c[3]
        nd[3] = s


def find_path(root, name):
    if root[0] == name:
        return [root]
    path = [root]
    idx = [0]
    while path:
        nd = path[-1]
        i = idx[-1]
        ch = nd[2]
        if i < len(ch):
            idx[-1] = i + 1
            c = ch[i]
            if c[0] == name:
                return path + [c]
            path.append(c)
            idx.append(0)
        else:
            path.pop()
            idx.pop()
    return None


def tostr(root):
    parts = []
    st = [root]
    while st:
        it = st.pop()
        if type(it) is str:
            parts.append(it)
            continue
        parts.append(it[0] + ':' + str(it[1]))
        ch = it[2]
        if ch:
            parts.append('[')
            st.append(']')
            k = len(ch) - 1
            while k >= 0:
                if k < len(ch) - 1:
                    st.append(' ')
                st.append(ch[k])
                k -= 1
    return ''.join(parts)


def sortkey(c):
    return (-c[3], c[0])


def fold(root):
    stack = [root]
    while stack:
        cur = stack.pop()
        newch = []
        for c in cur[2]:
            parts = [c[0]]
            w = c[1]
            x = c
            while len(x[2]) == 1:
                y = x[2][0]
                parts.append(y[0])
                w += y[1]
                x = y
            if len(parts) == 1:
                m = c
            else:
                m = ['+'.join(parts), w, x[2], 0]
            newch.append(m)
            stack.append(m)
        cur[2] = newch


def main():
    try:
        data = sys.stdin.buffer.read().decode('latin-1')
        if '\r' in data:
            raise Bad()
        lines = data.split('\n')
        if data.endswith('\n'):
            lines.pop()
        if not lines:
            raise Bad()
        for ln in lines:
            if ln == '':
                raise Bad()
        root = parse_tree(lines[0])
        ops = [parse_op(ln) for ln in lines[1:]]
    except Bad:
        sys.exit(1)

    out = []
    for kind, arg in ops:
        if kind == 'total':
            t = 0
            for nd, d in walk(root):
                t += nd[1]
            out.append(str(t) + '\n')
        elif kind == 'stats':
            W = walk(root)
            nodes = len(W)
            leaves = 0
            height = 0
            widest = 0
            for nd, d in W:
                if not nd[2]:
                    leaves += 1
                if d > height:
                    height = d
                if len(nd[2]) > widest:
                    widest = len(nd[2])
            out.append('nodes=' + str(nodes) + ' leaves=' + str(leaves)
                       + ' height=' + str(height) + ' widest=' + str(widest) + '\n')
        elif kind == 'level':
            cnt = 0
            sm = 0
            for nd, d in walk(root):
                if d == arg:
                    cnt += 1
                    sm += nd[1]
            out.append(str(cnt) + ' ' + str(sm) + '\n')
        elif kind == 'find':
            p = find_path(root, arg)
            if p is None:
                out.append('none\n')
            else:
                out.append('/'.join([x[0] for x in p]) + '\n')
        elif kind == 'print':
            out.append(tostr(root) + '\n')
        elif kind == 'prune':
            W = walk(root)
            compute_sub(W)
            st = [root]
            while st:
                nd = st.pop()
                kept = [c for c in nd[2] if c[3] >= arg]
                nd[2] = kept
                st.extend(kept)
        elif kind == 'sort':
            W = walk(root)
            compute_sub(W)
            for nd, d in W:
                nd[2].sort(key=sortkey)
        elif kind == 'mirror':
            for nd, d in walk(root):
                nd[2].reverse()
        elif kind == 'fold':
            fold(root)
        elif kind == 'cut':
            p = find_path(root, arg)
            if p is not None and len(p) > 1:
                parent = p[-2]
                node = p[-1]
                ch = parent[2]
                i = 0
                while i < len(ch):
                    if ch[i] is node:
                        break
                    i += 1
                ch[i:i + 1] = node[2]

    sys.stdout.write(''.join(out))
    sys.exit(0)


main()
