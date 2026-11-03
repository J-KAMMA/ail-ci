from ail import read_bytes, wrapping_mul
import sys

class Prog:

    def __init__(self, n_op: list[int], n_a: list[int], n_b: list[int], s_kind: list[int], s_line: list[int], s_e: list[int], s_var: list[int], s_a: list[int], s_b: list[int], s_j: list[int], outroots: list[int], vars: dict[str, int], val: list[int], has: list[bool], bs: list[int]):
        self.n_op = n_op
        self.n_a = n_a
        self.n_b = n_b
        self.s_kind = s_kind
        self.s_line = s_line
        self.s_e = s_e
        self.s_var = s_var
        self.s_a = s_a
        self.s_b = s_b
        self.s_j = s_j
        self.outroots = outroots
        self.vars = vars
        self.val = val
        self.has = has
        self.bs = bs

class Lx:

    def __init__(self, tk: list[int], tv: list[int], pos: int, depth: int):
        self.tk = tk
        self.tv = tv
        self.pos = pos
        self.depth = depth

def node(p: Prog, op: int, a: int, b: int) -> int:
    p.n_op.append(op)
    p.n_a.append(a)
    p.n_b.append(b)
    return len(p.n_op) - 1

def peekop(lx: Lx) -> int:
    if lx.pos < len(lx.tk) and lx.tk[lx.pos] == 3:
        return lx.tv[lx.pos]
    return 0

def pprim(p: Prog, lx: Lx) -> int:
    if lx.pos >= len(lx.tk):
        raise ValueError('e')
    k = lx.tk[lx.pos]
    v = lx.tv[lx.pos]
    if k == 0:
        lx.pos += 1
        return node(p, 100, v, 0)
    if k == 1:
        lx.pos += 1
        return node(p, 101, v, 0)
    if k == 3 and v == 15:
        lx.pos += 1
        lx.depth += 1
        if lx.depth > 32:
            raise ValueError('e')
        r = pe1(p, lx)
        if peekop(lx) != 16:
            raise ValueError('e')
        lx.pos += 1
        lx.depth -= 1
        return r
    raise ValueError('e')

def punary(p: Prog, lx: Lx) -> int:
    o = peekop(lx)
    if o == 8:
        lx.pos += 1
        x = punary(p, lx)
        return node(p, 20, x, 0)
    if o == 13 or o == 14:
        lx.pos += 1
        y = punary(p, lx)
        return node(p, o, y, 0)
    return pprim(p, lx)

def pe5(p: Prog, lx: Lx) -> int:
    l = punary(p, lx)
    if peekop(lx) == 12:
        lx.pos += 1
        r = pe5(p, lx)
        return node(p, 12, l, r)
    return l

def pe4(p: Prog, lx: Lx) -> int:
    l = pe5(p, lx)
    while True:
        o = peekop(lx)
        if o == 9 or o == 10 or o == 11:
            lx.pos += 1
            r = pe5(p, lx)
            l = node(p, o, l, r)
        else:
            break
    return l

def pe3(p: Prog, lx: Lx) -> int:
    l = pe4(p, lx)
    while True:
        o = peekop(lx)
        if o == 7 or o == 8:
            lx.pos += 1
            r = pe4(p, lx)
            l = node(p, o, l, r)
        else:
            break
    return l

def pe2(p: Prog, lx: Lx) -> int:
    l = pe3(p, lx)
    o = peekop(lx)
    if o >= 3 and o <= 6:
        lx.pos += 1
        r = pe3(p, lx)
        return node(p, o, l, r)
    return l

def pe1(p: Prog, lx: Lx) -> int:
    l = pe2(p, lx)
    while True:
        o = peekop(lx)
        if o == 1 or o == 2:
            lx.pos += 1
            r = pe2(p, lx)
            l = node(p, o, l, r)
        else:
            break
    return l

def isdig(c: int) -> bool:
    return c >= ord('0') and c <= ord('9')

def islow(c: int) -> bool:
    return c >= ord('a') and c <= ord('z') or c == ord('_')

def push(lx: Lx, k: int, v: int) -> None:
    lx.tk.append(k)
    lx.tv.append(v)

def opid(c: int, d: int) -> int:
    # returns id*10 + length consumed, 0 if none
    if c == ord('<'):
        if d == ord('>'):
            return 12
        return 51
    if c == ord('>'):
        if d == ord('<'):
            return 22
        return 61
    if c == ord('='):
        if d == ord('='):
            return 32
        return 181
    if c == ord('!'):
        if d == ord('='):
            return 42
        return 141
    if c == ord('+'):
        return 71
    if c == ord('-'):
        return 81
    if c == ord('*'):
        return 91
    if c == ord('/'):
        return 101
    if c == ord('%'):
        return 111
    if c == ord('~'):
        return 121
    if c == ord('#'):
        return 131
    if c == ord('('):
        return 151
    if c == ord(')'):
        return 161
    if c == ord(','):
        return 171
    return 0

def kwid(w: str) -> int:
    if w == 'set':
        return 1
    if w == 'out':
        return 2
    if w == 'loop':
        return 3
    if w == 'when':
        return 4
    if w == 'else':
        return 5
    if w == 'end':
        return 6
    if w == 'break':
        return 7
    return 0

def lex(p: Prog, lx: Lx, data: bytes, a: int, b: int) -> None:
    i = a
    while i < b:
        c = data[i]
        if c == 32 or c == 9 or c == 13:
            i += 1
            continue
        if c == ord(';'):
            return
        if isdig(c):
            v = 0
            while i < b and isdig(data[i]):
                v = v * 10 + (data[i] - ord('0'))
                if v > 4294967295:
                    raise ValueError('e')
                i += 1
            if i < b and islow(data[i]):
                raise ValueError('e')
            push(lx, 0, v)
            continue
        if islow(c):
            s = i
            while i < b and (islow(data[i]) or isdig(data[i])):
                i += 1
            w = data[s:i].decode()
            k = kwid(w)
            if k > 0:
                push(lx, 2, k)
            else:
                if w not in p.vars:
                    p.vars[w] = len(p.val)
                    p.val.append(0)
                    p.has.append(False)
                push(lx, 1, p.vars[w])
            continue
        d = 0
        if i + 1 < b:
            d = data[i + 1]
        r = opid(c, d)
        if r == 0:
            raise ValueError('e')
        push(lx, 3, r // 10)
        i += r % 10

def newstmt(p: Prog, kind: int, line: int) -> int:
    p.s_kind.append(kind)
    p.s_line.append(line)
    p.s_e.append(-1)
    p.s_var.append(-1)
    p.s_a.append(0)
    p.s_b.append(0)
    p.s_j.append(-1)
    return len(p.s_kind) - 1

def parse_line(p: Prog, lx: Lx, line: int) -> None:
    if len(lx.tk) == 0:
        return
    if lx.tk[0] != 2:
        raise ValueError('e')
    kw = lx.tv[0]
    lx.pos = 1
    n = len(lx.tk)
    if kw == 1:
        if n < 4 or lx.tk[1] != 1 or lx.tk[2] != 3 or (lx.tv[2] != 18):
            raise ValueError('e')
        lx.pos = 3
        s = newstmt(p, 0, line)
        p.s_var[s] = lx.tv[1]
        p.s_e[s] = pe1(p, lx)
        if lx.pos != n:
            raise ValueError('e')
        return
    if kw == 2:
        s2 = newstmt(p, 1, line)
        p.s_a[s2] = len(p.outroots)
        cnt = 0
        p.outroots.append(pe1(p, lx))
        cnt += 1
        while peekop(lx) == 17:
            lx.pos += 1
            p.outroots.append(pe1(p, lx))
            cnt += 1
        p.s_b[s2] = cnt
        if lx.pos != n:
            raise ValueError('e')
        return
    if kw == 3 or kw == 4:
        if len(p.bs) >= 16:
            raise ValueError('e')
        s3 = newstmt(p, kw - 1, line)
        p.s_e[s3] = pe1(p, lx)
        if lx.pos != n:
            raise ValueError('e')
        p.bs.append(s3)
        return
    if n != 1:
        raise ValueError('e')
    if kw == 5:
        if len(p.bs) == 0:
            raise ValueError('e')
        t = p.bs[len(p.bs) - 1]
        if p.s_kind[t] != 3 or p.s_j[t] != -1:
            raise ValueError('e')
        s4 = newstmt(p, 4, line)
        p.s_j[t] = s4
        return
    if kw == 6:
        if len(p.bs) == 0:
            raise ValueError('e')
        t2 = p.bs.pop()
        s5 = newstmt(p, 5, line)
        p.s_e[s5] = t2
        if p.s_kind[t2] == 3:
            if p.s_j[t2] == -1:
                p.s_j[t2] = s5
            else:
                p.s_j[p.s_j[t2]] = s5
        else:
            p.s_j[t2] = s5
        return
    # break
    found = False
    for q in p.bs:
        if p.s_kind[q] == 2:
            found = True
    if not found:
        raise ValueError('e')
    s6 = newstmt(p, 6, line)

def popcnt(x: int) -> int:
    c = 0
    v = x
    while v != 0:
        c += v & 1
        v = v >> 1
    return c

def ev(p: Prog, i: int) -> int:
    op = p.n_op[i]
    a = p.n_a[i]
    if op == 100:
        return a
    if op == 101:
        if not p.has[a]:
            raise ValueError('r')
        return p.val[a]
    M = 4294967295
    if op == 20:
        x = ev(p, a)
        return 0 - x & M
    if op == 13:
        x2 = ev(p, a)
        return popcnt(x2)
    if op == 14:
        x3 = ev(p, a)
        if x3 == 0:
            return 1
        return 0
    l = ev(p, a)
    r = ev(p, p.n_b[i])
    if op == 1:
        if l > r:
            return l
        return r
    if op == 2:
        if l < r:
            return l
        return r
    if op == 3:
        if l == r:
            return 1
        return 0
    if op == 4:
        if l != r:
            return 1
        return 0
    if op == 5:
        if l < r:
            return 1
        return 0
    if op == 6:
        if l > r:
            return 1
        return 0
    if op == 7:
        return l + r & M
    if op == 8:
        return l - r & M
    if op == 9:
        return wrapping_mul(l, r) & M
    if op == 10:
        if r == 0:
            raise ValueError('r')
        return l // r
    if op == 11:
        if r == 0:
            raise ValueError('r')
        return l % r
    k = r % 32
    return (l << k | l >> 32 - k) & M

def run(p: Prog) -> int:
    pc = 0
    n = len(p.s_kind)
    lpc: list[int] = []
    lcnt: list[int] = []
    while pc < n:
        k = p.s_kind[pc]
        try:
            if k == 0:
                v = ev(p, p.s_e[pc])
                p.val[p.s_var[pc]] = v
                p.has[p.s_var[pc]] = True
                pc += 1
            elif k == 1:
                parts: list[str] = []
                for j in range(p.s_b[pc]):
                    parts.append(str(ev(p, p.outroots[p.s_a[pc] + j])))
                print(' '.join(parts))
                pc += 1
            elif k == 2:
                c = ev(p, p.s_e[pc])
                if c == 0:
                    pc = p.s_j[pc] + 1
                else:
                    lpc.append(pc)
                    lcnt.append(c)
                    pc += 1
            elif k == 3:
                w = ev(p, p.s_e[pc])
                if w != 0:
                    pc += 1
                else:
                    jj = p.s_j[pc]
                    if p.s_kind[jj] == 4:
                        pc = jj + 1
                    else:
                        pc = jj
            elif k == 4:
                pc = p.s_j[pc]
            elif k == 5:
                o = p.s_e[pc]
                if p.s_kind[o] == 2:
                    t = len(lcnt) - 1
                    lcnt[t] = lcnt[t] - 1
                    if lcnt[t] > 0:
                        pc = o + 1
                    else:
                        lpc.pop()
                        lcnt.pop()
                        pc += 1
                else:
                    pc += 1
            else:
                o2 = lpc.pop()
                lcnt.pop()
                pc = p.s_j[o2] + 1
        except ValueError as err:
            print(f'runtime error line {p.s_line[pc]}')
            return 3
    return 0

def main() -> int:
    if len(sys.argv) != 2:
        return 1
    data = b''
    try:
        data = read_bytes(sys.argv[1])
    except OSError as e0:
        return 1
    p = Prog([], [], [], [], [], [], [], [], [], [], [], {}, [], [], [])
    lx = Lx([], [], 0, 0)
    total = len(data)
    start = 0
    lineno = 0
    while start < total:
        e = start
        while e < total and data[e] != 10:
            e += 1
        lineno += 1
        try:
            if e - start > 1000:
                raise ValueError('e')
            for i in range(start, e):
                c = data[i]
                if not (c == 9 or c == 13 or (c >= 32 and c <= 126)):
                    raise ValueError('e')
            lx.tk.clear()
            lx.tv.clear()
            lx.pos = 0
            lx.depth = 0
            lex(p, lx, data, start, e)
            parse_line(p, lx, lineno)
        except ValueError as err:
            print(f'parse error line {lineno}')
            return 2
        start = e + 1
    if len(p.bs) > 0:
        print(f'parse error line {p.s_line[p.bs[len(p.bs) - 1]]}')
        return 2
    return run(p)

if __name__ == "__main__":
    sys.exit(main())
