import sys, re

sys.setrecursionlimit(20000)
M = 0xFFFFFFFF
KW = {"set", "out", "loop", "when", "else", "end", "break"}
TOK = re.compile(r"[ \t\r]*(?:(\d+)|([a-z_][a-z0-9_]*)|(<>|><|==|!=|<|>|\+|-|\*|/|%|~|#|!|\(|\)|,|=))")


class PE(Exception):
    pass


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while True:
        while i < n and s[i] in " \t\r":
            i += 1
        if i >= n:
            break
        m = TOK.match(s, i)
        if not m:
            raise PE()
        i = m.end()
        if m.group(1) is not None:
            if i < n and (s[i] == "_" or "a" <= s[i] <= "z"):
                raise PE()
            v = int(m.group(1))
            if v > M:
                raise PE()
            toks.append(("n", v))
        elif m.group(2) is not None:
            w = m.group(2)
            toks.append(("k" if w in KW else "v", w))
        else:
            toks.append(("o", m.group(3)))
    return toks


class Parser:
    def __init__(self, toks, pos):
        self.t = toks
        self.p = pos
        self.depth = 0

    def peek(self):
        return self.t[self.p] if self.p < len(self.t) else (None, None)

    def isop(self, *ops):
        k, v = self.peek()
        return k == "o" and v in ops

    def expr(self):
        left = self.cmp()
        while self.isop("<>", "><"):
            op = self.t[self.p][1]
            self.p += 1
            right = self.cmp()
            left = ("max" if op == "<>" else "min", left, right)
        return left

    def cmp(self):
        left = self.add()
        if self.isop("==", "!=", "<", ">"):
            op = self.t[self.p][1]
            self.p += 1
            right = self.add()
            left = (op, left, right)
        return left

    def add(self):
        left = self.mul()
        while self.isop("+", "-"):
            op = self.t[self.p][1]
            self.p += 1
            left = (op, left, self.mul())
        return left

    def mul(self):
        left = self.rot()
        while self.isop("*", "/", "%"):
            op = self.t[self.p][1]
            self.p += 1
            left = (op, left, self.rot())
        return left

    def rot(self):
        left = self.unary()
        if self.isop("~"):
            self.p += 1
            right = self.rot()
            return ("~", left, right)
        return left

    def unary(self):
        k, v = self.peek()
        if k == "o" and v in ("-", "#", "!"):
            self.p += 1
            return ("u" + v, self.unary())
        if k == "n":
            self.p += 1
            return ("num", v)
        if k == "v":
            self.p += 1
            return ("var", v)
        if k == "o" and v == "(":
            self.p += 1
            self.depth += 1
            if self.depth > 32:
                raise PE()
            e = self.expr()
            if not self.isop(")"):
                raise PE()
            self.p += 1
            self.depth -= 1
            return e
        raise PE()


def parse_expr(toks, pos):
    p = Parser(toks, pos)
    e = p.expr()
    return e, p.p


class Gen:
    def __init__(self):
        self.pre = []
        self.nt = 0

    def g(self, n):
        c, d = self._g(n)
        return c, d

    def _g(self, n):
        k = n[0]
        if k == "num":
            return str(n[1]), 0
        if k == "var":
            return 'v["%s"]' % n[1], 0
        if k[0] == "u":
            c, d = self._g(n[1])
            if k == "u-":
                r = "((-%s)&4294967295)" % c
            elif k == "u#":
                r = "(%s).bit_count()" % c
            else:
                r = "(1 if %s==0 else 0)" % c
            return self.hoist(r, d + 1)
        a, da = self._g(n[1])
        b, db = self._g(n[2])
        d = max(da, db) + 1
        if k == "max":
            r = "max(%s,%s)" % (a, b)
        elif k == "min":
            r = "min(%s,%s)" % (a, b)
        elif k in ("==", "!=", "<", ">"):
            r = "(1 if %s%s%s else 0)" % (a, k, b)
        elif k in ("+", "-", "*"):
            r = "((%s%s%s)&4294967295)" % (a, k, b)
        elif k == "/":
            r = "(%s//%s)" % (a, b)
        elif k == "%":
            r = "(%s%%%s)" % (a, b)
        else:
            r = "rot(%s,%s)" % (a, b)
        return self.hoist(r, d)

    def hoist(self, r, d):
        if d > 20:
            self.nt += 1
            t = "t%d" % self.nt
            self.pre.append("%s=%s" % (t, r))
            return t, 0
        return r, d


def rot(a, b):
    r = b & 31
    return ((a << r) | (a >> (32 - r))) & M


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except Exception:
        sys.exit(1)
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    out = []
    stack = []  # (kind, lineno, has_else, loopdepth)
    loops = 0
    ind = 0
    bad = None
    gen = Gen()

    def emit(s):
        out.append("    " * (ind + 1) + s)

    for ln, raw in enumerate(lines, 1):
        try:
            if len(raw) > 1000:
                raise PE()
            for b in raw:
                if not (b == 9 or b == 13 or 32 <= b <= 126):
                    raise PE()
            s = raw.decode("ascii")
            ci = s.find(";")
            if ci >= 0:
                s = s[:ci]
            toks = tokenize(s)
            if not toks:
                continue
            k, w = toks[0]
            if k != "k":
                raise PE()
            gen.pre = []
            if w == "set":
                if len(toks) < 4 or toks[1][0] != "v" or toks[2] != ("o", "="):
                    raise PE()
                e, p = parse_expr(toks, 3)
                if p != len(toks):
                    raise PE()
                c, _ = gen.g(e)
                emit("L=%d" % ln)
                for x in gen.pre:
                    emit(x)
                emit('v["%s"]=%s' % (toks[1][1], c))
            elif w == "out":
                pos = 1
                cs = []
                while True:
                    e, pos = parse_expr(toks, pos)
                    cs.append(gen.g(e)[0])
                    if pos < len(toks) and toks[pos] == ("o", ","):
                        pos += 1
                        continue
                    break
                if pos != len(toks):
                    raise PE()
                emit("L=%d" % ln)
                for x in gen.pre:
                    emit(x)
                emit('out.append(" ".join(map(str,(%s,))))' % ",".join(cs))
            elif w in ("loop", "when"):
                if len(stack) >= 16:
                    raise PE()
                e, p = parse_expr(toks, 1)
                if p != len(toks):
                    raise PE()
                c, _ = gen.g(e)
                emit("L=%d" % ln)
                for x in gen.pre:
                    emit(x)
                if w == "loop":
                    emit("for _ in range(%s):" % c)
                    loops += 1
                else:
                    emit("if %s:" % c)
                stack.append([w, ln, False])
                ind += 1
                emit("pass")
            elif w == "else":
                if len(toks) != 1 or not stack or stack[-1][0] != "when" or stack[-1][2]:
                    raise PE()
                stack[-1][2] = True
                ind -= 1
                emit("else:")
                ind += 1
                emit("pass")
            elif w == "end":
                if len(toks) != 1 or not stack:
                    raise PE()
                t = stack.pop()
                if t[0] == "loop":
                    loops -= 1
                ind -= 1
            elif w == "break":
                if len(toks) != 1 or not any(t[0] == "loop" for t in stack):
                    raise PE()
                emit("break")
            else:
                raise PE()
        except PE:
            bad = ln
            break
    if bad is None and stack:
        bad = stack[-1][1]
    if bad is not None:
        sys.stdout.write("parse error line %d\n" % bad)
        sys.exit(2)
    src = "def run(v,out,rot):\n    L=0\n    try:\n" + "\n".join(
        "    " + x for x in out) + "\n        pass\n    except (ZeroDivisionError, KeyError):\n        return L\n    return 0\n"
    ns = {}
    exec(compile(src, "<tally>", "exec"), ns)
    res = []
    r = ns["run"]({}, res, rot)
    if res:
        sys.stdout.write("\n".join(res) + "\n")
    if r:
        sys.stdout.write("runtime error line %d\n" % r)
        sys.stdout.flush()
        sys.exit(3)


main()
