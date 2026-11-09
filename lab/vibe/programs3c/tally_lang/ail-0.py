import sys

MAXV = 4294967295
M = 4294967295
KW = {'set', 'out', 'loop', 'when', 'else', 'end', 'break'}
SINGLE = set('<>+-*/%~#!(),=')
OUT = []


class PErr(Exception):
    pass


class RtErr(Exception):
    def __init__(self, line):
        super().__init__(line)
        self.line = line


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r':
            i += 1
            continue
        if '0' <= c <= '9':
            j = i
            while j < n and '0' <= s[j] <= '9':
                j += 1
            if j < n and (('a' <= s[j] <= 'z') or s[j] == '_'):
                raise PErr()
            v = int(s[i:j])
            if v > MAXV:
                raise PErr()
            toks.append(('num', v))
            i = j
            continue
        if ('a' <= c <= 'z') or c == '_':
            j = i + 1
            while j < n and (('a' <= s[j] <= 'z') or ('0' <= s[j] <= '9') or s[j] == '_'):
                j += 1
            w = s[i:j]
            toks.append(('kw' if w in KW else 'name', w))
            i = j
            continue
        two = s[i:i + 2]
        if two in ('<>', '><', '==', '!='):
            toks.append(('op', two))
            i += 2
            continue
        if c in SINGLE:
            toks.append(('op', c))
            i += 1
            continue
        raise PErr()
    return toks


class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.depth = 0

    def at(self, op):
        return self.i < len(self.t) and self.t[self.i] == ('op', op)

    def at_any(self, ops):
        if self.i < len(self.t):
            k, v = self.t[self.i]
            return k == 'op' and v in ops
        return False

    def nxt(self):
        if self.i >= len(self.t):
            raise PErr()
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expect(self, op):
        if self.nxt() != ('op', op):
            raise PErr()

    def finish(self):
        if self.i != len(self.t):
            raise PErr()

    def e1(self):
        node = self.e2()
        while self.at_any(('<>', '><')):
            op = self.nxt()[1]
            b = self.e2()
            node = ('bin', op, node, b)
        return node

    def e2(self):
        a = self.e3()
        if self.at_any(('==', '!=', '<', '>')):
            op = self.nxt()[1]
            b = self.e3()
            return ('bin', op, a, b)
        return a

    def e3(self):
        node = self.e4()
        while self.at_any(('+', '-')):
            op = self.nxt()[1]
            b = self.e4()
            node = ('bin', op, node, b)
        return node

    def e4(self):
        node = self.e5()
        while self.at_any(('*', '/', '%')):
            op = self.nxt()[1]
            b = self.e5()
            node = ('bin', op, node, b)
        return node

    def e5(self):
        a = self.e6()
        if self.at_any(('~',)):
            self.nxt()
            b = self.e5()
            return ('bin', '~', a, b)
        return a

    def e6(self):
        if self.at_any(('-', '#', '!')):
            op = self.nxt()[1]
            return ('un', op, self.e6())
        return self.e7()

    def e7(self):
        k, v = self.nxt()
        if k == 'num':
            return ('num', v)
        if k == 'name':
            return ('var', v)
        if k == 'op' and v == '(':
            self.depth += 1
            if self.depth > 32:
                raise PErr()
            e = self.e1()
            self.expect(')')
            self.depth -= 1
            return e
        raise PErr()


def handle_line(ln, raw, frames):
    for b in raw:
        if not (b == 9 or b == 13 or 0x20 <= b <= 0x7E):
            raise PErr()
    if len(raw) > 1000:
        raise PErr()
    text = raw.split(b';', 1)[0].decode('ascii')
    toks = tokenize(text)
    if not toks:
        return
    p = P(toks)
    first = toks[0]
    if first[0] != 'kw':
        raise PErr()
    word = first[1]
    p.i = 1
    cur = frames[-1]
    if word == 'set':
        t = p.nxt()
        if t[0] != 'name':
            raise PErr()
        p.expect('=')
        e = p.e1()
        p.finish()
        cur['cur'].append(('set', ln, t[1], e))
    elif word == 'out':
        es = [p.e1()]
        while p.at(','):
            p.i += 1
            es.append(p.e1())
        p.finish()
        cur['cur'].append(('out', ln, es))
    elif word == 'loop':
        e = p.e1()
        p.finish()
        if len(frames) - 1 >= 16:
            raise PErr()
        f = {'kind': 'loop', 'line': ln, 'expr': e, 'body': [],
             'else_body': [], 'has_else': False}
        f['cur'] = f['body']
        frames.append(f)
    elif word == 'when':
        e = p.e1()
        p.finish()
        if len(frames) - 1 >= 16:
            raise PErr()
        f = {'kind': 'when', 'line': ln, 'expr': e, 'body': [],
             'else_body': [], 'has_else': False}
        f['cur'] = f['body']
        frames.append(f)
    elif word == 'else':
        p.finish()
        if cur['kind'] != 'when' or cur['has_else']:
            raise PErr()
        cur['has_else'] = True
        cur['cur'] = cur['else_body']
    elif word == 'end':
        p.finish()
        if len(frames) == 1:
            raise PErr()
        f = frames.pop()
        if f['kind'] == 'loop':
            node = ('loop', f['line'], f['expr'], f['body'])
        else:
            node = ('when', f['line'], f['expr'], f['body'], f['else_body'])
        frames[-1]['cur'].append(node)
    elif word == 'break':
        p.finish()
        if not any(f['kind'] == 'loop' for f in frames):
            raise PErr()
        cur['cur'].append(('break', ln))
    else:
        raise PErr()


def parse_all(lines):
    root = {'kind': None, 'line': 0, 'body': [], 'else_body': [], 'has_else': False}
    root['cur'] = root['body']
    frames = [root]
    for ln, raw in enumerate(lines, 1):
        try:
            handle_line(ln, raw, frames)
        except PErr:
            return None, ln
    if len(frames) > 1:
        return None, frames[-1]['line']
    return root['body'], 0


def ev(e, env, ln):
    t = e[0]
    if t == 'num':
        return e[1]
    if t == 'var':
        if e[1] in env:
            return env[e[1]]
        raise RtErr(ln)
    if t == 'un':
        v = ev(e[2], env, ln)
        op = e[1]
        if op == '-':
            return (-v) & M
        if op == '#':
            return bin(v).count('1')
        return 1 if v == 0 else 0
    a = ev(e[2], env, ln)
    b = ev(e[3], env, ln)
    op = e[1]
    if op == '<>':
        return a if a >= b else b
    if op == '><':
        return a if a <= b else b
    if op == '==':
        return 1 if a == b else 0
    if op == '!=':
        return 1 if a != b else 0
    if op == '<':
        return 1 if a < b else 0
    if op == '>':
        return 1 if a > b else 0
    if op == '+':
        return (a + b) & M
    if op == '-':
        return (a - b) & M
    if op == '*':
        return (a * b) & M
    if op == '/':
        if b == 0:
            raise RtErr(ln)
        return a // b
    if op == '%':
        if b == 0:
            raise RtErr(ln)
        return a % b
    r = b & 31
    if r == 0:
        return a
    return ((a << r) | (a >> (32 - r))) & M


def run(stmts, env):
    for st in stmts:
        k = st[0]
        if k == 'set':
            env[st[2]] = ev(st[3], env, st[1])
        elif k == 'out':
            vals = [ev(x, env, st[1]) for x in st[2]]
            OUT.append(' '.join(str(v) for v in vals) + '\n')
        elif k == 'loop':
            n = ev(st[2], env, st[1])
            body = st[3]
            for _ in range(n):
                if run(body, env):
                    break
        elif k == 'when':
            v = ev(st[2], env, st[1])
            if v != 0:
                if run(st[3], env):
                    return True
            else:
                if run(st[4], env):
                    return True
        else:
            return True
    return False


def main():
    sys.setrecursionlimit(10000)
    argv = sys.argv
    if len(argv) != 2:
        sys.exit(1)
    try:
        with open(argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    pieces = data.split(b'\n')
    if pieces and pieces[-1] == b'':
        pieces.pop()

    prog, err = parse_all(pieces)
    if prog is None:
        sys.stdout.write("parse error line %d\n" % err)
        sys.exit(2)

    try:
        run(prog, {})
    except RtErr as e:
        sys.stdout.write(''.join(OUT))
        sys.stdout.write("runtime error line %d\n" % e.line)
        sys.exit(3)
    sys.stdout.write(''.join(OUT))
    sys.exit(0)


if __name__ == '__main__':
    main()
