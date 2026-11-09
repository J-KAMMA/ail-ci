import re
import sys

MASK = 0xFFFFFFFF
MAXNUM = 0xFFFFFFFF
KW = frozenset(("set", "out", "loop", "when", "else", "end", "break"))
OPS2 = ("<>", "><", "==", "!=")
OPS1 = frozenset("<>+-*/%~#!(),=")
BADBYTE = re.compile(rb"[^\t\r\x20-\x7e]")
ENV = {}


class Bad(Exception):
    pass


class RtFail(Exception):
    pass


class RtError(Exception):
    def __init__(self, line):
        super().__init__(line)
        self.line = line


class BreakEx(Exception):
    pass


class Frame:
    def __init__(self, kind, line, expr):
        self.kind = kind
        self.line = line
        self.expr = expr
        self.body = []
        self.orelse = []
        self.in_else = False


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in " \t\r":
            i += 1
        elif "0" <= c <= "9":
            j = i
            while j < n and "0" <= s[j] <= "9":
                j += 1
            if j < n and ("a" <= s[j] <= "z" or s[j] == "_"):
                raise Bad()
            v = int(s[i:j])
            if v > MAXNUM:
                raise Bad()
            toks.append(("num", v))
            i = j
        elif ("a" <= c <= "z") or c == "_":
            j = i + 1
            while j < n and (("a" <= s[j] <= "z") or ("0" <= s[j] <= "9") or s[j] == "_"):
                j += 1
            toks.append(("word", s[i:j]))
            i = j
        elif s[i:i + 2] in OPS2:
            toks.append(("op", s[i:i + 2]))
            i += 2
        elif c in OPS1:
            toks.append(("op", c))
            i += 1
        else:
            raise Bad()
    return toks


class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.d = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def isop(self, ops):
        tk = self.peek()
        return tk is not None and tk[0] == "op" and tk[1] in ops

    def end(self):
        if self.i != len(self.t):
            raise Bad()

    def expr(self):
        left = self.l2()
        while self.isop(("<>", "><")):
            op = self.peek()[1]
            self.i += 1
            left = ("bin", op, left, self.l2())
        return left

    def l2(self):
        left = self.l3()
        if self.isop(("==", "!=", "<", ">")):
            op = self.peek()[1]
            self.i += 1
            left = ("bin", op, left, self.l3())
        return left

    def l3(self):
        left = self.l4()
        while self.isop(("+", "-")):
            op = self.peek()[1]
            self.i += 1
            left = ("bin", op, left, self.l4())
        return left

    def l4(self):
        left = self.l5()
        while self.isop(("*", "/", "%")):
            op = self.peek()[1]
            self.i += 1
            left = ("bin", op, left, self.l5())
        return left

    def l5(self):
        items = [self.l6()]
        while self.isop(("~",)):
            self.i += 1
            items.append(self.l6())
        res = items[-1]
        for x in reversed(items[:-1]):
            res = ("bin", "~", x, res)
        return res

    def l6(self):
        ops = []
        while self.isop(("-", "#", "!")):
            ops.append(self.peek()[1])
            self.i += 1
        x = self.l7()
        for op in reversed(ops):
            x = ("un", op, x)
        return x

    def l7(self):
        tk = self.peek()
        if tk is None:
            raise Bad()
        if tk[0] == "num":
            self.i += 1
            return ("num", tk[1])
        if tk[0] == "word":
            if tk[1] in KW:
                raise Bad()
            self.i += 1
            return ("var", tk[1])
        if tk == ("op", "("):
            self.d += 1
            if self.d > 32:
                raise Bad()
            self.i += 1
            e = self.expr()
            if not self.isop((")",)):
                raise Bad()
            self.i += 1
            self.d -= 1
            return e
        raise Bad()


def ev(node):
    k = node[0]
    if k == "num":
        return node[1]
    if k == "var":
        if node[1] not in ENV:
            raise RtFail()
        return ENV[node[1]]
    if k == "un":
        x = ev(node[2])
        op = node[1]
        if op == "-":
            return (-x) & MASK
        if op == "#":
            return bin(x).count("1")
        return 1 if x == 0 else 0
    a = ev(node[2])
    b = ev(node[3])
    op = node[1]
    if op == "~":
        s = b & 31
        if s == 0:
            return a
        return ((a << s) | (a >> (32 - s))) & MASK
    if op == "<>":
        return max(a, b)
    if op == "><":
        return min(a, b)
    if op == "==":
        return 1 if a == b else 0
    if op == "!=":
        return 1 if a != b else 0
    if op == "<":
        return 1 if a < b else 0
    if op == ">":
        return 1 if a > b else 0
    if op == "+":
        return (a + b) & MASK
    if op == "-":
        return (a - b) & MASK
    if op == "*":
        return (a * b) & MASK
    if op == "/":
        if b == 0:
            raise RtFail()
        return a // b
    if op == "%":
        if b == 0:
            raise RtFail()
        return a % b
    raise RtFail()


def evl(node, line):
    try:
        return ev(node)
    except RtFail:
        raise RtError(line)


def target(root, stack):
    if not stack:
        return root
    f = stack[-1]
    return f.orelse if f.in_else else f.body


def process(lineno, raw, root, stack):
    if len(raw) > 1000:
        raise Bad()
    if BADBYTE.search(raw):
        raise Bad()
    s = raw.decode("ascii")
    k = s.find(";")
    if k >= 0:
        s = s[:k]
    toks = tokenize(s)
    if not toks:
        return
    head = toks[0]
    if head[0] != "word" or head[1] not in KW:
        raise Bad()
    kw = head[1]
    p = P(toks)
    p.i = 1
    if kw == "set":
        tk = p.peek()
        if tk is None or tk[0] != "word" or tk[1] in KW:
            raise Bad()
        name = tk[1]
        p.i += 1
        if p.peek() != ("op", "="):
            raise Bad()
        p.i += 1
        e = p.expr()
        p.end()
        target(root, stack).append(("set", lineno, name, e))
    elif kw == "out":
        es = [p.expr()]
        while p.isop((",",)):
            p.i += 1
            es.append(p.expr())
        p.end()
        target(root, stack).append(("out", lineno, es))
    elif kw in ("loop", "when"):
        e = p.expr()
        p.end()
        if len(stack) >= 16:
            raise Bad()
        stack.append(Frame(kw, lineno, e))
    elif kw == "else":
        p.end()
        if not stack or stack[-1].kind != "when" or stack[-1].in_else:
            raise Bad()
        stack[-1].in_else = True
    elif kw == "end":
        p.end()
        if not stack:
            raise Bad()
        f = stack.pop()
        if f.kind == "loop":
            node = ("loop", f.line, f.expr, f.body)
        else:
            node = ("when", f.line, f.expr, f.body, f.orelse)
        target(root, stack).append(node)
    elif kw == "break":
        p.end()
        if not any(f.kind == "loop" for f in stack):
            raise Bad()
        target(root, stack).append(("break", lineno))


def run(stmts):
    for st in stmts:
        k = st[0]
        if k == "set":
            ENV[st[2]] = evl(st[3], st[1])
        elif k == "out":
            vals = [evl(e, st[1]) for e in st[2]]
            sys.stdout.write(" ".join(map(str, vals)) + "\n")
        elif k == "loop":
            n = evl(st[2], st[1])
            for _ in range(n):
                try:
                    run(st[3])
                except BreakEx:
                    break
        elif k == "when":
            v = evl(st[2], st[1])
            run(st[3] if v != 0 else st[4])
        else:
            raise BreakEx()


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except OSError:
        sys.exit(1)
    sys.setrecursionlimit(10000)
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    root = []
    stack = []
    for lineno, raw in enumerate(lines, 1):
        try:
            process(lineno, raw, root, stack)
        except Bad:
            print(f"parse error line {lineno}")
            sys.exit(2)
    if stack:
        print(f"parse error line {stack[-1].line}")
        sys.exit(2)
    try:
        run(root)
    except RtError as e:
        sys.stdout.write(f"runtime error line {e.line}\n")
        sys.stdout.flush()
        sys.exit(3)
    except BreakEx:
        pass
    sys.stdout.flush()


if __name__ == "__main__":
    main()
