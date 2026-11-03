from ail import read_stdin_bytes
import sys

class T:

    def __init__(self, nm: list[str], w: list[int], dep: list[int], par: list[int]):
        self.nm = nm
        self.w = w
        self.dep = dep
        self.par = par

def is_lower(c: int) -> bool:
    return c >= 97 and c <= 122

def parse_tree(data: bytes, end: int, t: T) -> bool:
    pos = 0
    stack: list[int] = []
    n = 0
    while True:
        # expect a node at pos
        s = pos
        while pos < end and is_lower(data[pos]):
            pos += 1
        if pos == s or pos - s > 16:
            return False
        if pos >= end or data[pos] != 58:
            return False
        name = data[s:pos].decode()
        pos += 1
        ds = pos
        v = 0
        while pos < end and data[pos] >= 48 and (data[pos] <= 57):
            v = v * 10 + data[pos] - 48
            if v > 1000000:
                return False
            pos += 1
        if pos == ds:
            return False
        if data[ds] == 48 and pos - ds > 1:
            return False
        t.nm.append(name)
        t.w.append(v)
        t.dep.append(len(stack))
        if len(stack) > 0:
            t.par.append(stack[len(stack) - 1])
        else:
            t.par.append(-1)
        me = n
        n += 1
        if pos < end and data[pos] == 91:
            stack.append(me)
            pos += 1
            continue
        # after state
        again = False
        while True:
            if pos >= end:
                return len(stack) == 0
            c = data[pos]
            if c == 93:
                if len(stack) == 0:
                    return False
                stack.pop()
                pos += 1
            elif c == 32:
                if len(stack) == 0:
                    return False
                pos += 1
                break
            else:
                return False
    return False

# parse a decimal number 0..10^15 in data[a:b]; -1 if bad
def parse_num(data: bytes, a: int, b: int) -> int:
    if b <= a or b - a > 16:
        return -1
    if data[a] == 48 and b - a > 1:
        return -1
    v = 0
    for i in range(a, b):
        c = data[i]
        if c < 48 or c > 57:
            return -1
        v = v * 10 + c - 48
    if v > 1000000000000000:
        return -1
    return v

def name_ok(data: bytes, a: int, b: int) -> bool:
    if b <= a:
        return False
    for i in range(a, b):
        c = data[i]
        if not (is_lower(c) or c == 43):
            return False
    return True

def compact(t: T, keep: list[bool]) -> None:
    n = len(t.nm)
    mp = [0] * n
    nm: list[str] = []
    w: list[int] = []
    dep: list[int] = []
    par: list[int] = []
    for i in range(n):
        if keep[i]:
            mp[i] = len(nm)
            nm.append(t.nm[i])
            w.append(t.w[i])
            dep.append(t.dep[i])
            if t.par[i] < 0:
                par.append(-1)
            else:
                par.append(mp[t.par[i]])
    t.nm = nm
    t.w = w
    t.dep = dep
    t.par = par

def rebuild(t: T, cl: list[int], cs: list[int]) -> None:
    n = len(t.nm)
    stack = [0]
    ord: list[int] = []
    while len(stack) > 0:
        v = stack.pop()
        ord.append(v)
        k = cs[v + 1] - 1
        while k >= cs[v]:
            stack.append(cl[k])
            k -= 1
    ni = [0] * n
    for k in range(n):
        ni[ord[k]] = k
    nm: list[str] = []
    w: list[int] = []
    dep: list[int] = []
    par: list[int] = []
    for k in range(n):
        o = ord[k]
        nm.append(t.nm[o])
        w.append(t.w[o])
        dep.append(t.dep[o])
        if t.par[o] < 0:
            par.append(-1)
        else:
            par.append(ni[t.par[o]])
    t.nm = nm
    t.w = w
    t.dep = dep
    t.par = par

def counts(t: T) -> list[int]:
    n = len(t.nm)
    cs = [0] * (n + 1)
    for i in range(1, n):
        cs[t.par[i] + 1] += 1
    for i in range(n):
        cs[i + 1] += cs[i]
    return cs

def subw(t: T) -> list[int]:
    n = len(t.nm)
    sub = t.w.copy()
    i = n - 1
    while i >= 1:
        sub[t.par[i]] += sub[i]
        i -= 1
    return sub

def do_mirror(t: T) -> None:
    n = len(t.nm)
    cs = counts(t)
    pos = cs.copy()
    cl = [0] * n
    i = n - 1
    while i >= 1:
        p = t.par[i]
        cl[pos[p]] = i
        pos[p] += 1
        i -= 1
    rebuild(t, cl, cs)

def do_sort(t: T) -> None:
    n = len(t.nm)
    cs = counts(t)
    sub = subw(t)
    nm = t.nm
    par = t.par
    idx = [i for i in range(1, n)]
    idx.sort(key=lambda i: (par[i], -sub[i], nm[i], i))
    rebuild(t, idx, cs)

def do_prune(t: T, lim: int) -> None:
    n = len(t.nm)
    sub = subw(t)
    keep: list[bool] = []
    for i in range(n):
        keep.append(i == 0 or sub[i] >= lim)
    compact(t, keep)

def find_first(t: T, name: str) -> int:
    n = len(t.nm)
    for i in range(n):
        if t.nm[i] == name:
            return i
    return -1

def do_cut(t: T, name: str) -> None:
    i = find_first(t, name)
    if i <= 0:
        return
    n = len(t.nm)
    d = t.dep[i]
    j = i + 1
    while j < n and t.dep[j] > d:
        t.dep[j] -= 1
        if t.par[j] == i:
            t.par[j] = t.par[i]
        j += 1
    keep = [True] * n
    keep[i] = False
    compact(t, keep)

def do_fold(t: T) -> None:
    n = len(t.nm)
    cc = [0] * n
    for i in range(1, n):
        cc[t.par[i]] += 1
    mp = [0] * n
    nm: list[str] = []
    w: list[int] = []
    dep: list[int] = []
    par: list[int] = []
    for i in range(n):
        if i > 0 and t.par[i] > 0 and (cc[t.par[i]] == 1):
            continue
        k = len(nm)
        name = t.nm[i]
        wt = t.w[i]
        mp[i] = k
        if i > 0:
            j = i
            while cc[j] == 1:
                j += 1
                name += '+'
                name += t.nm[j]
                wt += t.w[j]
                mp[j] = k
        nm.append(name)
        w.append(wt)
        if t.par[i] < 0:
            par.append(-1)
            dep.append(0)
        else:
            par.append(mp[t.par[i]])
            dep.append(dep[mp[t.par[i]]] + 1)
    t.nm = nm
    t.w = w
    t.dep = dep
    t.par = par

def do_print(t: T) -> str:
    n = len(t.nm)
    out = ''
    for i in range(n):
        if i > 0:
            pd = t.dep[i - 1]
            d = t.dep[i]
            if d > pd:
                out += '['
            else:
                k = pd - d
                while k > 0:
                    out += ']'
                    k -= 1
                out += ' '
        out += t.nm[i]
        out += ':'
        out += str(t.w[i])
    k = t.dep[n - 1]
    while k > 0:
        out += ']'
        k -= 1
    out += '\n'
    return out

def do_find(t: T, name: str) -> str:
    i = find_first(t, name)
    if i < 0:
        return 'none\n'
    parts: list[str] = []
    while i >= 0:
        parts.append(t.nm[i])
        i = t.par[i]
    parts.reverse()
    return '/'.join(parts) + '\n'

def main() -> int:
    data = read_stdin_bytes(1 << 40)
    total = len(data)
    if total == 0:
        return 1
    lend = total
    if data[total - 1] == 10:
        lend = total - 1
    # operations: code, int arg, str arg
    codes: list[int] = []
    iargs: list[int] = []
    sargs: list[str] = []
    t = T([], [], [], [])
    a = 0
    first = True
    while a <= lend:
        b = a
        while b < lend and data[b] != 10:
            b += 1
        if b == a:
            return 1
        if first:
            if not parse_tree(data, b, t):
                return 1
            first = False
        else:
            sp = a
            while sp < b and data[sp] != 32:
                sp += 1
            kw = data[a:sp].decode()
            code = -1
            iv = 0
            sv = ''
            if sp == b:
                if kw == 'total':
                    code = 0
                elif kw == 'stats':
                    code = 1
                elif kw == 'print':
                    code = 5
                elif kw == 'sort':
                    code = 7
                elif kw == 'mirror':
                    code = 8
                elif kw == 'fold':
                    code = 9
                else:
                    return 1
            elif kw == 'level':
                code = 2
                iv = parse_num(data, sp + 1, b)
                if iv < 0:
                    return 1
            elif kw == 'prune':
                code = 6
                iv = parse_num(data, sp + 1, b)
                if iv < 0:
                    return 1
            elif kw == 'find' or kw == 'cut':
                if not name_ok(data, sp + 1, b):
                    return 1
                sv = data[sp + 1:b].decode()
                if kw == 'find':
                    code = 3
                else:
                    code = 10
            else:
                return 1
            codes.append(code)
            iargs.append(iv)
            sargs.append(sv)
        a = b + 1
        if b >= lend:
            break
    out = ''
    for q in range(len(codes)):
        c = codes[q]
        if c == 0:
            s = 0
            for x in t.w:
                s += x
            out += str(s)
            out += '\n'
        elif c == 1:
            n = len(t.nm)
            cc = [0] * n
            for i in range(1, n):
                cc[t.par[i]] += 1
            leaves = 0
            wide = 0
            h = 0
            for i in range(n):
                if cc[i] == 0:
                    leaves += 1
                if cc[i] > wide:
                    wide = cc[i]
                if t.dep[i] > h:
                    h = t.dep[i]
            out += f'nodes={n} leaves={leaves} height={h} widest={wide}\n'
        elif c == 2:
            cnt = 0
            s = 0
            n = len(t.nm)
            for i in range(n):
                if t.dep[i] == iargs[q]:
                    cnt += 1
                    s += t.w[i]
            out += f'{cnt} {s}\n'
        elif c == 3:
            out += do_find(t, sargs[q])
        elif c == 5:
            out += do_print(t)
        elif c == 6:
            do_prune(t, iargs[q])
        elif c == 7:
            do_sort(t)
        elif c == 8:
            do_mirror(t)
        elif c == 9:
            do_fold(t)
        elif c == 10:
            do_cut(t, sargs[q])
    print(out, end='')
    return 0

if __name__ == "__main__":
    sys.exit(main())
