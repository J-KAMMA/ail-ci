import sys


def main():
    data = sys.stdin.buffer.read()
    if b'\r' in data:
        return 1
    parts = data.split(b'\n')
    if parts and parts[-1] == b'':
        parts.pop()
    if not parts:
        return 1
    for p in parts:
        if p == b'':
            return 1

    s = parts[0].decode('latin-1')

    try:
        names = []
        weights = []
        children = []
        parent = []
        n = len(s)

        def hdr(i):
            j = i
            while j < n and 'a' <= s[j] <= 'z':
                j += 1
            ln = j - i
            if ln < 1 or ln > 16:
                raise ValueError
            nm = s[i:j]
            if j >= n or s[j] != ':':
                raise ValueError
            j += 1
            k = j
            while k < n and '0' <= s[k] <= '9':
                k += 1
            if k == j:
                raise ValueError
            if k - j > 7:
                raise ValueError
            if k - j > 1 and s[j] == '0':
                raise ValueError
            w = int(s[j:k])
            if w > 1000000:
                raise ValueError
            return nm, w, k

        nm, w, i = hdr(0)
        names.append(nm)
        weights.append(w)
        children.append([])
        parent.append(-1)
        root = 0

        stack = []
        if i < n and s[i] == '[':
            i += 1
            stack.append([root, 0])
        elif i < n:
            raise ValueError

        while stack:
            frame = stack[-1]
            idx = frame[0]
            if frame[1] == 0:
                nm, w, i = hdr(i)
                c = len(names)
                names.append(nm)
                weights.append(w)
                children.append([])
                parent.append(idx)
                children[idx].append(c)
                frame[1] = 1
                if i < n and s[i] == '[':
                    i += 1
                    stack.append([c, 0])
            else:
                if i < n and s[i] == ' ':
                    i += 1
                    frame[1] = 0
                elif i < n and s[i] == ']':
                    i += 1
                    stack.pop()
                else:
                    raise ValueError

        if i != n:
            raise ValueError

    except ValueError:
        return 1

    def pnum(b):
        if not b or len(b) > 16:
            return None
        if len(b) > 1 and b[0] == 48:
            return None
        v = 0
        for ch in b:
            if ch < 48 or ch > 57:
                return None
            v = v * 10 + (ch - 48)
            if v > 10 ** 15:
                return None
        return v

    def pname(b):
        if not b:
            return False
        for ch in b:
            if not (97 <= ch <= 122 or ch == 43):
                return False
        return True

    ops = []
    for line in parts[1:]:
        if line == b'total':
            ops.append((0,))
        elif line == b'stats':
            ops.append((1,))
        elif line == b'print':
            ops.append((2,))
        elif line == b'sort':
            ops.append((3,))
        elif line == b'mirror':
            ops.append((4,))
        elif line == b'fold':
            ops.append((5,))
        elif line.startswith(b'level '):
            v = pnum(line[6:])
            if v is None:
                return 1
            ops.append((6, v))
        elif line.startswith(b'find '):
            b = line[5:]
            if not pname(b):
                return 1
            ops.append((7, b.decode('ascii')))
        elif line.startswith(b'prune '):
            v = pnum(line[6:])
            if v is None:
                return 1
            ops.append((8, v))
        elif line.startswith(b'cut '):
            b = line[4:]
            if not pname(b):
                return 1
            ops.append((9, b.decode('ascii')))
        else:
            return 1

    out = []

    def order_sub():
        order = []
        st = [root]
        while st:
            v = st.pop()
            order.append(v)
            ch = children[v]
            j = len(ch) - 1
            while j >= 0:
                st.append(ch[j])
                j -= 1
        sub = weights[:]
        for v in reversed(order):
            p = parent[v]
            if p != -1:
                sub[p] += sub[v]
        return order, sub

    for op in ops:
        k = op[0]

        if k == 0:
            st = [root]
            t = 0
            while st:
                v = st.pop()
                t += weights[v]
                ch = children[v]
                if ch:
                    st.extend(ch)
            out.append(str(t))

        elif k == 1:
            cnt = 0
            leaves = 0
            height = 0
            widest = 0
            st = [(root, 0)]
            while st:
                v, d = st.pop()
                cnt += 1
                ch = children[v]
                if not ch:
                    leaves += 1
                else:
                    lc = len(ch)
                    if lc > widest:
                        widest = lc
                    nd = d + 1
                    for c in ch:
                        st.append((c, nd))
                if d > height:
                    height = d
            out.append('nodes=%d leaves=%d height=%d widest=%d'
                       % (cnt, leaves, height, widest))

        elif k == 6:
            D = op[1]
            cnt = 0
            sm = 0
            st = [(root, 0)]
            while st:
                v, d = st.pop()
                if d == D:
                    cnt += 1
                    sm += weights[v]
                elif d < D:
                    nd = d + 1
                    for c in children[v]:
                        st.append((c, nd))
            out.append('%d %d' % (cnt, sm))

        elif k == 7:
            NAME = op[1]
            target = -1
            st = [root]
            while st:
                v = st.pop()
                if names[v] == NAME:
                    target = v
                    break
                ch = children[v]
                j = len(ch) - 1
                while j >= 0:
                    st.append(ch[j])
                    j -= 1
            if target == -1:
                out.append('none')
            else:
                path = []
                x = target
                while x != -1:
                    path.append(names[x])
                    x = parent[x]
                path.reverse()
                out.append('/'.join(path))

        elif k == 2:
            pp = []
            st = [(0, root)]
            while st:
                typ, val = st.pop()
                if typ == 0:
                    pp.append(names[val])
                    pp.append(':')
                    pp.append(str(weights[val]))
                    ch = children[val]
                    if ch:
                        pp.append('[')
                        st.append((1, ']'))
                        j = len(ch) - 1
                        while j >= 0:
                            st.append((0, ch[j]))
                            if j > 0:
                                st.append((1, ' '))
                            j -= 1
                else:
                    pp.append(val)
            out.append(''.join(pp))

        elif k == 8:
            W = op[1]
            order, sub = order_sub()
            st = [root]
            while st:
                v = st.pop()
                ch = children[v]
                if ch:
                    nc = []
                    for c in ch:
                        if sub[c] >= W:
                            nc.append(c)
                    children[v] = nc
                    st.extend(nc)

        elif k == 3:
            order, sub = order_sub()
            for v in order:
                ch = children[v]
                if len(ch) > 1:
                    ch.sort(key=lambda c: (-sub[c], names[c]))

        elif k == 4:
            st = [root]
            while st:
                v = st.pop()
                ch = children[v]
                ch.reverse()
                st.extend(ch)

        elif k == 5:
            st = list(children[root])
            while st:
                v = st.pop()
                parts_ = []
                wsum = 0
                x = v
                while True:
                    parts_.append(names[x])
                    wsum += weights[x]
                    ch = children[x]
                    if len(ch) == 1:
                        x = ch[0]
                    else:
                        break
                if x != v:
                    names[v] = '+'.join(parts_)
                    weights[v] = wsum
                    nc = children[x]
                    children[v] = nc
                    for c in nc:
                        parent[c] = v
                st.extend(children[v])

        elif k == 9:
            NAME = op[1]
            target = -1
            st = [root]
            while st:
                v = st.pop()
                if names[v] == NAME:
                    target = v
                    break
                ch = children[v]
                j = len(ch) - 1
                while j >= 0:
                    st.append(ch[j])
                    j -= 1
            if target != -1 and target != root:
                p = parent[target]
                ch = children[p]
                ix = 0
                while ch[ix] != target:
                    ix += 1
                newc = children[target]
                ch[ix:ix + 1] = newc
                for c in newc:
                    parent[c] = p
                children[target] = []

    if out:
        sys.stdout.write('\n'.join(out))
        sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
