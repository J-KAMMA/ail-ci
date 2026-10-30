import sys
import re

NODE = re.compile(r'([a-z]{1,16}):(0|[1-9][0-9]{0,6})')
NUM = re.compile(r'(?:0|[1-9][0-9]*)\Z')
NAMEOK = re.compile(r'[a-z+]+\Z')


def fail():
    sys.exit(1)


def parse_tree(s):
    n = len(s)
    names = []
    w = []
    kids = []
    stack = []
    pos = 0
    match = NODE.match
    while True:
        m = match(s, pos)
        if m is None:
            fail()
        wt = int(m.group(2))
        if wt > 1000000:
            fail()
        i = len(names)
        names.append(m.group(1))
        w.append(wt)
        if stack:
            kids[stack[-1]].append(i)
        pos = m.end()
        if pos < n and s[pos] == '[':
            kids.append([])
            stack.append(i)
            pos += 1
            continue
        kids.append(())
        while True:
            if pos == n:
                if stack:
                    fail()
                return names, w, kids
            ch = s[pos]
            if ch == ' ':
                if not stack:
                    fail()
                pos += 1
                break
            elif ch == ']':
                if not stack:
                    fail()
                stack.pop()
                pos += 1
            else:
                fail()


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    lines = data.split('\n')
    if lines and lines[-1] == '' and len(lines) > 1:
        lines.pop()
    for ln in lines:
        if ln == '':
            fail()
    names, w, kids = parse_tree(lines[0])
    ops = []
    for ln in lines[1:]:
        if ln in ('total', 'stats', 'print', 'sort', 'mirror', 'fold'):
            ops.append((ln, None))
            continue
        sp = ln.find(' ')
        if sp < 0:
            fail()
        kw = ln[:sp]
        arg = ln[sp + 1:]
        if kw in ('level', 'prune'):
            if not NUM.match(arg):
                fail()
            v = int(arg)
            if v > 10 ** 15:
                fail()
            ops.append((kw, v))
        elif kw in ('find', 'cut'):
            if not NAMEOK.match(arg):
                fail()
            ops.append((kw, arg))
        else:
            fail()

    out = []

    def preorder():
        order = []
        st = [0]
        pop = st.pop
        while st:
            v = pop()
            order.append(v)
            k = kids[v]
            if k:
                st.extend(reversed(k))
        return order

    def subtree(order):
        sub = {}
        for v in reversed(order):
            s = w[v]
            for c in kids[v]:
                s += sub[c]
            sub[v] = s
        return sub

    def find_first(name):
        par = {}
        st = [0]
        while st:
            v = st.pop()
            if names[v] == name:
                return v, par
            k = kids[v]
            if k:
                for c in k:
                    par[c] = v
                st.extend(reversed(k))
        return None, par

    for op, arg in ops:
        if op == 'total':
            out.append(str(sum(w[v] for v in preorder())))
        elif op == 'stats':
            cnt = 0
            leaves = 0
            widest = 0
            level = [0]
            h = -1
            while level:
                h += 1
                nxt = []
                for v in level:
                    cnt += 1
                    k = kids[v]
                    if k:
                        if len(k) > widest:
                            widest = len(k)
                        nxt.extend(k)
                    else:
                        leaves += 1
                level = nxt
            out.append("nodes=%d leaves=%d height=%d widest=%d" % (cnt, leaves, h, widest))
        elif op == 'level':
            level = [0]
            d = 0
            while level and d < arg:
                nxt = []
                for v in level:
                    nxt.extend(kids[v])
                level = nxt
                d += 1
            if d == arg and level:
                out.append("%d %d" % (len(level), sum(w[v] for v in level)))
            else:
                out.append("0 0")
        elif op == 'find':
            v, par = find_first(arg)
            if v is None:
                out.append('none')
            else:
                path = []
                while True:
                    path.append(names[v])
                    if v == 0:
                        break
                    v = par[v]
                path.reverse()
                out.append('/'.join(path))
        elif op == 'print':
            res = []
            st = [0]
            while st:
                it = st.pop()
                if it.__class__ is str:
                    res.append(it)
                    continue
                res.append("%s:%d" % (names[it], w[it]))
                k = kids[it]
                if k:
                    res.append('[')
                    st.append(']')
                    first = True
                    for c in reversed(k):
                        if not first:
                            st.append(' ')
                        first = False
                        st.append(c)
            out.append(''.join(res))
        elif op == 'prune':
            order = preorder()
            sub = subtree(order)
            for v in order:
                k = kids[v]
                if k:
                    kids[v] = [c for c in k if sub[c] >= arg]
        elif op == 'sort':
            order = preorder()
            sub = subtree(order)
            for v in order:
                k = kids[v]
                if len(k) > 1:
                    kids[v] = sorted(k, key=lambda c: (-sub[c], names[c]))
        elif op == 'mirror':
            for v in preorder():
                k = kids[v]
                if len(k) > 1:
                    kids[v] = k[::-1]
        elif op == 'fold':
            heads = [0]
            while heads:
                h = heads.pop()
                cur = h
                if h != 0:
                    parts = [names[h]]
                    total = w[h]
                    while len(kids[cur]) == 1:
                        cur = kids[cur][0]
                        parts.append(names[cur])
                        total += w[cur]
                    if cur != h:
                        names[h] = '+'.join(parts)
                        w[h] = total
                        kids[h] = kids[cur]
                heads.extend(kids[h])
        elif op == 'cut':
            v, par = find_first(arg)
            if v is not None and v != 0:
                p = par[v]
                k = kids[p]
                i = k.index(v)
                kids[p] = k[:i] + list(kids[v]) + k[i + 1:]

    if out:
        sys.stdout.write('\n'.join(out) + '\n')


main()
