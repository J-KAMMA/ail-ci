import sys

MASK = 0xFFFFFFFF
MAXNUM = 4294967295
KEYWORDS = {'set', 'out', 'loop', 'when', 'else', 'end', 'break'}
OPS = ['<>', '><', '==', '!=', '<', '>', '+', '-', '*', '/', '%', '~', '#', '!', '(', ')', ',', '=']


class ParseErr(Exception):
    pass


class ParseFail(Exception):
    def __init__(self, line):
        self.line = line


class RtErr(Exception):
    pass


class Fail(Exception):
    def __init__(self, line):
        self.line = line


class Brk(Exception):
    pass


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
                raise ParseErr()
            v = int(s[i:j])
            if v > MAXNUM:
                raise ParseErr()
            toks.append(('num', v))
            i = j
            continue
        if ('a' <= c <= 'z') or c == '_':
            j = i + 1
            while j < n and (('a' <= s[j] <= 'z') or ('0' <= s[j] <= '9') or s[j] == '_'):
                j += 1
            w = s[i:j]
            toks.append(('kw' if w in KEYWORDS else 'word', w))
            i = j
            continue
        for op in OPS:
            if s.startswith(op, i):
                toks.append(('op', op))
                i += len(op)
                break
        else:
            raise ParseErr()
    return toks


class Parser:
    def __init__(self, toks, pos=0):
        self.t = toks
        self.p = pos
        self.depth = 0

    def peek(self):
        return self.t[self.p] if self.p < len(self.t) else None

    def isop(self, ops):
        tok = self.peek()
        return tok is not None and tok[0] == 'op' and tok[1] in ops

    def take(self):
        tok = self.t[self.p]
        self.p += 1
        return tok

    def expr(self):
        node = self.cmp()
        while self.isop(('<>', '><')):
            op = self.take()[1]
            node = ('bin', op, node, self.cmp())
        return node

    def cmp(self):
        left = self.add()
        if self.isop(('==', '!=', '<', '>')):
            op = self.take()[1]
            right = self.add()
            return ('bin', op, left, right)
        return left

    def add(self):
        node = self.mul()
        while self.isop(('+', '-')):
            op = self.take()[1]
            node = ('bin', op, node, self.mul())
        return node

    def mul(self):
        node = self.tilde()
        while self.isop(('*', '/', '%')):
            op = self.take()[1]
            node = ('bin', op, node, self.tilde())
        return node

    def tilde(self):
        items = [self.unary()]
        while self.isop(('~',)):
            self.take()
            items.append(self.unary())
        if len(items) == 1:
            return items[0]
        return ('tilde', items)

    def unary(self):
        ops = []
        while self.isop(('-', '#', '!')):
            ops.append(self.take()[1])
        a = self.atom()
        if ops:
            return ('un', ops, a)
        return a

    def atom(self):
        tok = self.peek()
        if tok is None:
            raise ParseErr()
        if tok[0] == 'num':
            self.p += 1
            return ('num', tok[1])
        if tok[0] == 'word':
            self.p += 1
            return ('var', tok[1])
        if tok == ('op', '('):
            self.p += 1
            self.depth += 1
            if self.depth > 32:
                raise ParseErr()
            e = self.expr()
            if not self.isop((')',)):
                raise ParseErr()
            self.p += 1
            self.depth -= 1
            return e
        raise ParseErr()

    def done(self):
        if self.p != len(self.t):
            raise ParseErr()


def parse(data):
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    root = []
    stack = []
    for idx, raw in enumerate(lines, 1):
        for b in raw:
            if b != 9 and b != 13 and not (32 <= b <= 126):
                raise ParseFail(idx)
        if len(raw) > 1000:
            raise ParseFail(idx)
        s = raw.decode('ascii')
        semi = s.find(';')
        if semi >= 0:
            s = s[:semi]
        try:
            toks = tokenize(s)
            if not toks:
                continue
            h = toks[0]
            if h[0] != 'kw':
                raise ParseErr()
            k = h[1]
            if not stack:
                cur = root
            elif stack[-1]['t'] == 'when' and stack[-1]['inelse']:
                cur = stack[-1]['els']
            else:
                cur = stack[-1]['body']

            if k == 'set':
                if len(toks) < 4 or toks[1][0] != 'word' or toks[2] != ('op', '='):
                    raise ParseErr()
                p = Parser(toks, 3)
                e = p.expr()
                p.done()
                cur.append({'t': 'set', 'line': idx, 'name': toks[1][1], 'e': e})
            elif k == 'out':
                p = Parser(toks, 1)
                es = [p.expr()]
                while p.isop((',',)):
                    p.take()
                    es.append(p.expr())
                p.done()
                cur.append({'t': 'out', 'line': idx, 'es': es})
            elif k == 'loop' or k == 'when':
                p = Parser(toks, 1)
                e = p.expr()
                p.done()
                if len(stack) >= 16:
                    raise ParseErr()
                node = {'t': k, 'line': idx, 'e': e, 'body': [], 'els': [], 'inelse': False}
                cur.append(node)
                stack.append(node)
            elif k == 'else':
                if len(toks) != 1 or not stack or stack[-1]['t'] != 'when' or stack[-1]['inelse']:
                    raise ParseErr()
                stack[-1]['inelse'] = True
            elif k == 'end':
                if len(toks) != 1 or not stack:
                    raise ParseErr()
                stack.pop()
            elif k == 'break':
                if len(toks) != 1 or not any(nd['t'] == 'loop' for nd in stack):
                    raise ParseErr()
                cur.append({'t': 'break', 'line': idx})
            else:
                raise ParseErr()
        except ParseErr:
            raise ParseFail(idx)
    if stack:
        raise ParseFail(stack[-1]['line'])
    return root


def rot(a, b):
    a &= MASK
    s = b % 32
    if s == 0:
        return a
    return ((a << s) | (a >> (32 - s))) & MASK


def ev(e, env):
    t = e[0]
    if t == 'num':
        return e[1]
    if t == 'var':
        if e[1] not in env:
            raise RtErr()
        return env[e[1]]
    if t == 'un':
        v = ev(e[2], env)
        for op in reversed(e[1]):
            if op == '-':
                v = (-v) & MASK
            elif op == '#':
                v = bin(v).count('1')
            else:
                v = 1 if v == 0 else 0
        return v
    if t == 'tilde':
        vals = [ev(x, env) for x in e[1]]
        r = vals[-1]
        for i in range(len(vals) - 2, -1, -1):
            r = rot(vals[i], r)
        return r
    op = e[1]
    a = ev(e[2], env)
    b = ev(e[3], env)
    if op == '<>':
        return max(a, b)
    if op == '><':
        return min(a, b)
    if op == '==':
        return 1 if a == b else 0
    if op == '!=':
        return 1 if a != b else 0
    if op == '<':
        return 1 if a < b else 0
    if op == '>':
        return 1 if a > b else 0
    if op == '+':
        return (a + b) & MASK
    if op == '-':
        return (a - b) & MASK
    if op == '*':
        return (a * b) & MASK
    if op == '/':
        if b == 0:
            raise RtErr()
        return a // b
    if op == '%':
        if b == 0:
            raise RtErr()
        return a % b
    raise RtErr()


def run_block(stmts, env, outbuf):
    for st in stmts:
        k = st['t']
        line = st['line']
        n = 0
        c = 0
        try:
            if k == 'set':
                env[st['name']] = ev(st['e'], env)
                continue
            if k == 'out':
                vals = [ev(x, env) for x in st['es']]
                outbuf.append(' '.join(str(v) for v in vals) + '\n')
                continue
            if k == 'break':
                raise Brk()
            if k == 'loop':
                n = ev(st['e'], env)
            else:
                c = ev(st['e'], env)
        except RtErr:
            raise Fail(line)
        if k == 'loop':
            body = st['body']
            if body:
                for _ in range(n):
                    try:
                        run_block(body, env, outbuf)
                    except Brk:
                        break
        elif k == 'when':
            if c != 0:
                run_block(st['body'], env, outbuf)
            elif st['els']:
                run_block(st['els'], env, outbuf)


def main():
    sys.setrecursionlimit(20000)
    args = sys.argv[1:]
    if len(args) != 1:
        sys.exit(1)
    try:
        with open(args[0], 'rb') as f:
            data = f.read()
    except OSError:
        sys.exit(1)
    try:
        root = parse(data)
    except ParseFail as e:
        sys.stdout.write("parse error line %d\n" % e.line)
        sys.exit(2)
    outbuf = []
    env = {}
    try:
        run_block(root, env, outbuf)
    except Fail as e:
        sys.stdout.write(''.join(outbuf))
        sys.stdout.write("runtime error line %d\n" % e.line)
        sys.exit(3)
    sys.stdout.write(''.join(outbuf))
    sys.exit(0)


if __name__ == '__main__':
    main()
