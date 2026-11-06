import sys

MAXV = 0xFFFFFFFF
KEYWORDS = {'set', 'out', 'loop', 'when', 'else', 'end', 'break'}


class ParseError(Exception):
    def __init__(self, line):
        self.line = line


class EvalError(Exception):
    pass


class RError(Exception):
    def __init__(self, line):
        self.line = line


class BreakSignal(Exception):
    pass


def tokenize(s, line):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r':
            i += 1
        elif '0' <= c <= '9':
            j = i
            while j < n and '0' <= s[j] <= '9':
                j += 1
            if j < n and (('a' <= s[j] <= 'z') or s[j] == '_'):
                raise ParseError(line)
            v = int(s[i:j])
            if v > MAXV:
                raise ParseError(line)
            toks.append(('num', v))
            i = j
        elif ('a' <= c <= 'z') or c == '_':
            j = i + 1
            while j < n and (('a' <= s[j] <= 'z') or ('0' <= s[j] <= '9') or s[j] == '_'):
                j += 1
            toks.append(('word', s[i:j]))
            i = j
        else:
            two = s[i:i + 2]
            if two in ('<>', '><', '==', '!='):
                toks.append(('op', two))
                i += 2
            elif c in '<>+-*/%~#!(),=':
                toks.append(('op', c))
                i += 1
            else:
                raise ParseError(line)
    return toks


class Parser:
    def __init__(self, toks, line):
        self.toks = toks
        self.line = line
        self.pos = 0
        self.pdepth = 0

    def peek(self):
        if self.pos < len(self.toks):
            return self.toks[self.pos]
        return None

    def next(self):
        t = self.peek()
        if t is None:
            raise ParseError(self.line)
        self.pos += 1
        return t

    def at_op(self, *ops):
        t = self.peek()
        return t is not None and t[0] == 'op' and t[1] in ops

    def parse_expr(self):
        self.pdepth = 0
        return self.lvl1()

    def lvl1(self):
        node = self.lvl2()
        while self.at_op('<>', '><'):
            op = self.next()[1]
            node = ('bin', op, node, self.lvl2())
        return node

    def lvl2(self):
        node = self.lvl3()
        if self.at_op('==', '!=', '<', '>'):
            op = self.next()[1]
            node = ('bin', op, node, self.lvl3())
            if self.at_op('==', '!=', '<', '>'):
                raise ParseError(self.line)
        return node

    def lvl3(self):
        node = self.lvl4()
        while self.at_op('+', '-'):
            op = self.next()[1]
            node = ('bin', op, node, self.lvl4())
        return node

    def lvl4(self):
        node = self.lvl5()
        while self.at_op('*', '/', '%'):
            op = self.next()[1]
            node = ('bin', op, node, self.lvl5())
        return node

    def lvl5(self):
        node = self.lvl6()
        if self.at_op('~'):
            self.next()
            node = ('bin', '~', node, self.lvl5())
        return node

    def lvl6(self):
        if self.at_op('-', '#', '!'):
            op = self.next()[1]
            return ('un', op, self.lvl6())
        return self.lvl7()

    def lvl7(self):
        t = self.next()
        if t[0] == 'num':
            return ('num', t[1])
        if t[0] == 'word':
            if t[1] in KEYWORDS:
                raise ParseError(self.line)
            return ('var', t[1])
        if t[1] == '(':
            self.pdepth += 1
            if self.pdepth > 32:
                raise ParseError(self.line)
            node = self.lvl1()
            if not self.at_op(')'):
                raise ParseError(self.line)
            self.next()
            self.pdepth -= 1
            return node
        raise ParseError(self.line)


def parse_script(lines):
    root = []
    stack = []
    cur = root
    for idx, raw in enumerate(lines, 1):
        for b in raw:
            if not (b == 9 or b == 13 or 32 <= b <= 126):
                raise ParseError(idx)
        if len(raw) > 1000:
            raise ParseError(idx)
        s = raw.decode('ascii')
        k = s.find(';')
        if k >= 0:
            s = s[:k]
        toks = tokenize(s, idx)
        if not toks:
            continue
        t0 = toks[0]
        if t0[0] != 'word' or t0[1] not in KEYWORDS:
            raise ParseError(idx)
        kw = t0[1]
        rest = toks[1:]

        if kw == 'set':
            p = Parser(rest, idx)
            nt = p.next()
            if nt[0] != 'word' or nt[1] in KEYWORDS:
                raise ParseError(idx)
            eq = p.next()
            if eq[0] != 'op' or eq[1] != '=':
                raise ParseError(idx)
            e = p.parse_expr()
            if p.pos != len(rest):
                raise ParseError(idx)
            cur.append(('set', idx, nt[1], e))

        elif kw == 'out':
            p = Parser(rest, idx)
            exprs = [p.parse_expr()]
            while p.at_op(','):
                p.next()
                exprs.append(p.parse_expr())
            if p.pos != len(rest):
                raise ParseError(idx)
            cur.append(('out', idx, exprs))

        elif kw == 'loop' or kw == 'when':
            p = Parser(rest, idx)
            e = p.parse_expr()
            if p.pos != len(rest):
                raise ParseError(idx)
            if len(stack) >= 16:
                raise ParseError(idx)
            if kw == 'loop':
                node = ['loop', idx, e, []]
            else:
                node = ['when', idx, e, [], []]
            cur.append(node)
            if kw == 'loop':
                body = node[3]
            else:
                body = node[3]
            stack.append({'kind': kw, 'line': idx, 'else_seen': False, 'node': node, 'cur': body})
            cur = body

        elif kw == 'else':
            if rest:
                raise ParseError(idx)
            if not stack:
                raise ParseError(idx)
            top = stack[-1]
            if top['kind'] != 'when' or top['else_seen']:
                raise ParseError(idx)
            top['else_seen'] = True
            top['cur'] = top['node'][4]
            cur = top['cur']

        elif kw == 'end':
            if rest:
                raise ParseError(idx)
            if not stack:
                raise ParseError(idx)
            stack.pop()
            cur = stack[-1]['cur'] if stack else root

        else:  # break
            if rest:
                raise ParseError(idx)
            if not any(e['kind'] == 'loop' for e in stack):
                raise ParseError(idx)
            cur.append(('break', idx))

    if stack:
        raise ParseError(stack[-1]['line'])
    return root


def ev(node, env):
    k = node[0]
    if k == 'num':
        return node[1]
    if k == 'var':
        name = node[1]
        if name not in env:
            raise EvalError()
        return env[name]
    if k == 'un':
        op = node[1]
        v = ev(node[2], env)
        if op == '-':
            return (-v) & MAXV
        if op == '#':
            return bin(v).count('1')
        return 1 if v == 0 else 0

    op = node[1]
    a = ev(node[2], env)
    b = ev(node[3], env)
    if op == '+':
        return (a + b) & MAXV
    if op == '-':
        return (a - b) & MAXV
    if op == '*':
        return (a * b) & MAXV
    if op == '/':
        if b == 0:
            raise EvalError()
        return a // b
    if op == '%':
        if b == 0:
            raise EvalError()
        return a % b
    if op == '~':
        r = b % 32
        return ((a << r) | (a >> (32 - r))) & MAXV
    if op == '<>':
        return a if a > b else b
    if op == '><':
        return a if a < b else b
    if op == '==':
        return 1 if a == b else 0
    if op == '!=':
        return 1 if a != b else 0
    if op == '<':
        return 1 if a < b else 0
    if op == '>':
        return 1 if a > b else 0
    raise EvalError()


out = sys.stdout


def run(stmts, env):
    for st in stmts:
        k = st[0]
        if k == 'set':
            try:
                v = ev(st[3], env)
            except EvalError:
                raise RError(st[1])
            env[st[2]] = v
        elif k == 'out':
            try:
                vals = [ev(e, env) for e in st[2]]
            except EvalError:
                raise RError(st[1])
            out.write(' '.join(str(v) for v in vals) + '\n')
        elif k == 'loop':
            try:
                n = ev(st[2], env)
            except EvalError:
                raise RError(st[1])
            for _ in range(n):
                try:
                    run(st[3], env)
                except BreakSignal:
                    break
        elif k == 'when':
            try:
                c = ev(st[2], env)
            except EvalError:
                raise RError(st[1])
            if c != 0:
                run(st[3], env)
            else:
                run(st[4], env)
        else:  # break
            raise BreakSignal()


def main():
    sys.setrecursionlimit(10000)
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    pieces = data.split(b'\n')
    if data.endswith(b'\n'):
        pieces.pop()

    try:
        prog = parse_script(pieces)
    except ParseError as e:
        sys.stdout.write('parse error line %d\n' % e.line)
        sys.exit(2)

    try:
        run(prog, {})
    except RError as e:
        sys.stdout.write('runtime error line %d\n' % e.line)
        sys.exit(3)

    sys.exit(0)


if __name__ == '__main__':
    main()
