import sys

M = 4294967295
KEYWORDS = ['set', 'out', 'loop', 'when', 'else', 'end', 'break']
TWO_OPS = ['<>', '><', '==', '!=']
ONE_OPS = '<>+-*/%~#!(),='


class Tok:
    def __init__(self, kind, text, num):
        self.kind = kind
        self.text = text
        self.num = num


class Node:
    def __init__(self, kind, op, val, kids):
        self.kind = kind
        self.op = op
        self.val = val
        self.kids = kids


class Blk:
    def __init__(self, kind, line):
        self.kind = kind
        self.line = line
        self.name = ''
        self.exprs = []
        self.body = []
        self.els = []
        self.in_else = False


def check_strip(s):
    if len(s) > 1000:
        return None
    for ch in s:
        o = ord(ch)
        if not (o == 9 or o == 13 or 32 <= o <= 126):
            return None
    i = s.find(';')
    if i >= 0:
        return s[:i]
    return s


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ' or c == '\t' or c == '\r':
            i += 1
        elif '0' <= c <= '9':
            j = i
            while j < n and '0' <= s[j] <= '9':
                j += 1
            if j < n and (('a' <= s[j] <= 'z') or s[j] == '_'):
                return None
            digits = s[i:j].lstrip('0')
            if len(digits) > 10 or (len(digits) == 10 and digits > '4294967295'):
                return None
            val = int(digits) if digits else 0
            toks.append(Tok('num', '', val))
            i = j
        elif ('a' <= c <= 'z') or c == '_':
            j = i + 1
            while j < n and (('a' <= s[j] <= 'z') or ('0' <= s[j] <= '9') or s[j] == '_'):
                j += 1
            w = s[i:j]
            if w in KEYWORDS:
                toks.append(Tok('kw', w, 0))
            else:
                toks.append(Tok('name', w, 0))
            i = j
        elif i + 2 <= n and s[i:i + 2] in TWO_OPS:
            toks.append(Tok('op', s[i:i + 2], 0))
            i += 2
        elif c in ONE_OPS:
            toks.append(Tok('op', c, 0))
            i += 1
        else:
            return None
    return toks


class P:
    def __init__(self, toks, start):
        self.t = toks
        self.p = start
        self.d = 0
        self.err = False

    def isop(self, ops):
        if self.p >= len(self.t):
            return False
        tk = self.t[self.p]
        return tk.kind == 'op' and tk.text in ops

    def l1(self):
        left = self.l2()
        while self.isop(['<>', '><']):
            op = self.t[self.p].text
            self.p += 1
            right = self.l2()
            left = Node('bin', op, 0, [left, right])
        return left

    def l2(self):
        left = self.l3()
        if self.isop(['==', '!=', '<', '>']):
            op = self.t[self.p].text
            self.p += 1
            right = self.l3()
            left = Node('bin', op, 0, [left, right])
        return left

    def l3(self):
        left = self.l4()
        while self.isop(['+', '-']):
            op = self.t[self.p].text
            self.p += 1
            right = self.l4()
            left = Node('bin', op, 0, [left, right])
        return left

    def l4(self):
        left = self.l5()
        while self.isop(['*', '/', '%']):
            op = self.t[self.p].text
            self.p += 1
            right = self.l5()
            left = Node('bin', op, 0, [left, right])
        return left

    def l5(self):
        left = self.l6()
        if self.isop(['~']):
            self.p += 1
            right = self.l5()
            return Node('bin', '~', 0, [left, right])
        return left

    def l6(self):
        if self.isop(['-', '#', '!']):
            op = self.t[self.p].text
            self.p += 1
            inner = self.l6()
            return Node('un', op, 0, [inner])
        return self.l7()

    def l7(self):
        if self.p >= len(self.t):
            self.err = True
            return Node('num', '', 0, [])
        tk = self.t[self.p]
        if tk.kind == 'num':
            self.p += 1
            return Node('num', '', tk.num, [])
        if tk.kind == 'name':
            self.p += 1
            return Node('var', tk.text, 0, [])
        if tk.kind == 'op' and tk.text == '(':
            self.d += 1
            if self.d > 32:
                self.err = True
            self.p += 1
            e = self.l1()
            if not self.isop([')']):
                self.err = True
                return e
            self.p += 1
            self.d -= 1
            return e
        self.err = True
        return Node('num', '', 0, [])


def parse_stmt(toks, lineno):
    h = toks[0]
    if h.kind != 'kw':
        return None
    kw = h.text
    n = len(toks)
    st = Blk(kw, lineno)
    if kw == 'set':
        if n < 4 or toks[1].kind != 'name' or toks[2].kind != 'op' or toks[2].text != '=':
            return None
        ex = P(toks, 3)
        e = ex.l1()
        if ex.err or ex.p != n:
            return None
        st.name = toks[1].text
        st.exprs.append(e)
        return st
    if kw == 'out':
        if n < 2:
            return None
        ex = P(toks, 1)
        while True:
            e = ex.l1()
            if ex.err:
                return None
            st.exprs.append(e)
            if ex.p == n:
                break
            if toks[ex.p].kind != 'op' or toks[ex.p].text != ',':
                return None
            ex.p += 1
        return st
    if kw == 'loop' or kw == 'when':
        ex = P(toks, 1)
        e = ex.l1()
        if ex.err or ex.p != n:
            return None
        st.exprs.append(e)
        return st
    if n != 1:
        return None
    return st


def target(stack, root):
    if not stack:
        return root.body
    f = stack[-1]
    if f.in_else:
        return f.els
    return f.body


def handle(raw, lineno, root, stack):
    text = check_strip(raw)
    if text is None:
        return False
    toks = tokenize(text)
    if toks is None:
        return False
    if len(toks) == 0:
        return True
    st = parse_stmt(toks, lineno)
    if st is None:
        return False
    k = st.kind
    if k == 'set' or k == 'out':
        target(stack, root).append(st)
    elif k == 'loop' or k == 'when':
        if len(stack) >= 16:
            return False
        stack.append(st)
    elif k == 'else':
        if not stack:
            return False
        top = stack[-1]
        if top.kind != 'when' or top.in_else:
            return False
        top.in_else = True
    elif k == 'end':
        if not stack:
            return False
        f = stack.pop()
        target(stack, root).append(f)
    else:
        ok = False
        for f in stack:
            if f.kind == 'loop':
                ok = True
        if not ok:
            return False
        target(stack, root).append(st)
    return True


def parse_program(lines, root):
    # returns 0 on success, otherwise the line number of the parse error
    stack = []
    lineno = 0
    for raw in lines:
        lineno += 1
        if not handle(raw, lineno, root, stack):
            return lineno
    if stack:
        return stack[-1].line
    return 0


def mul(a, b):
    lo = a * (b & 0xFFFF)
    hi = (a * (b >> 16)) & 0xFFFF
    return (lo + (hi << 16)) & M


def ev(node, env, line, rt):
    # returns value (always >= 0) or -1 on runtime error (rt[0] holds the line)
    k = node.kind
    if k == 'num':
        return node.val
    if k == 'var':
        if node.op not in env:
            rt[0] = line
            return -1
        return env[node.op]
    if k == 'un':
        x = ev(node.kids[0], env, line, rt)
        if x < 0:
            return -1
        op = node.op
        if op == '-':
            return (-x) & M
        if op == '!':
            return 1 if x == 0 else 0
        c = 0
        while x:
            c += x & 1
            x >>= 1
        return c
    a = ev(node.kids[0], env, line, rt)
    if a < 0:
        return -1
    b = ev(node.kids[1], env, line, rt)
    if b < 0:
        return -1
    op = node.op
    if op == '+':
        return (a + b) & M
    if op == '-':
        return (a - b) & M
    if op == '*':
        return mul(a, b)
    if op == '/':
        if b == 0:
            rt[0] = line
            return -1
        return a // b
    if op == '%':
        if b == 0:
            rt[0] = line
            return -1
        return a % b
    if op == '~':
        s = b & 31
        if s == 0:
            return a
        return ((a << s) & M) | (a >> (32 - s))
    if op == '==':
        return 1 if a == b else 0
    if op == '!=':
        return 1 if a != b else 0
    if op == '<':
        return 1 if a < b else 0
    if op == '>':
        return 1 if a > b else 0
    if op == '<>':
        return a if a > b else b
    if op == '><':
        return a if a < b else b
    rt[0] = line
    return -1


def run_block(body, env, rt):
    # returns 0 normally, 1 on break, 2 on runtime error
    for st in body:
        k = st.kind
        if k == 'set':
            v = ev(st.exprs[0], env, st.line, rt)
            if v < 0:
                return 2
            env[st.name] = v
        elif k == 'out':
            parts = []
            for e in st.exprs:
                v = ev(e, env, st.line, rt)
                if v < 0:
                    return 2
                parts.append(str(v))
            sys.stdout.write(' '.join(parts) + '\n')
        elif k == 'loop':
            n = ev(st.exprs[0], env, st.line, rt)
            if n < 0:
                return 2
            for _i in range(n):
                r = run_block(st.body, env, rt)
                if r == 2:
                    return 2
                if r == 1:
                    break
        elif k == 'when':
            v = ev(st.exprs[0], env, st.line, rt)
            if v < 0:
                return 2
            if v != 0:
                r = run_block(st.body, env, rt)
            else:
                r = run_block(st.els, env, rt)
            if r == 2:
                return 2
            if r == 1:
                return 1
        elif k == 'break':
            return 1
    return 0


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    fh = open(sys.argv[1], 'rb')
    data = fh.read()
    fh.close()
    pieces = data.split(b'\n')
    if len(pieces) > 0 and pieces[-1] == b'':
        pieces.pop()
    lines = [p.decode('latin-1') for p in pieces]
    root = Blk('root', 0)
    bad = parse_program(lines, root)
    if bad > 0:
        sys.stdout.write('parse error line ' + str(bad) + '\n')
        sys.stdout.flush()
        sys.exit(2)
    env = {}
    rt = [0]
    r = run_block(root.body, env, rt)
    if r == 2:
        sys.stdout.write('runtime error line ' + str(rt[0]) + '\n')
        sys.stdout.flush()
        sys.exit(3)
    sys.stdout.flush()
    sys.exit(0)


main()
