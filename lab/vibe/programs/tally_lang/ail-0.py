import sys

MASK = 0xFFFFFFFF
KEYWORDS = frozenset(('set', 'out', 'loop', 'when', 'else', 'end', 'break'))


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ' or c == '\t' or c == '\r':
            i += 1
            continue
        if '0' <= c <= '9':
            j = i
            while j < n and '0' <= s[j] <= '9':
                j += 1
            if j < n and ('a' <= s[j] <= 'z' or s[j] == '_'):
                raise ValueError('number followed by letter')
            v = int(s[i:j])
            if v > MASK:
                raise ValueError('number too large')
            toks.append(('num', v))
            i = j
            continue
        if 'a' <= c <= 'z' or c == '_':
            j = i + 1
            while j < n and ('a' <= s[j] <= 'z' or '0' <= s[j] <= '9' or s[j] == '_'):
                j += 1
            toks.append(('word', s[i:j]))
            i = j
            continue
        if i + 1 < n:
            two = s[i:i + 2]
            if two == '<>' or two == '><' or two == '==' or two == '!=':
                toks.append(('op', two))
                i += 2
                continue
        if c in '<>+-*/%~#!(),=':
            toks.append(('op', c))
            i += 1
            continue
        raise ValueError('bad character')
    return toks


class Parser:
    __slots__ = ('toks', 'i', 'depth')

    def __init__(self, toks):
        self.toks = toks
        self.i = 0
        self.depth = 0

    def peek(self):
        if self.i < len(self.toks):
            return self.toks[self.i]
        return None

    def parse_level1(self):
        left = self.parse_level2()
        while True:
            t = self.peek()
            if t is not None and t[0] == 'op' and (t[1] == '<>' or t[1] == '><'):
                self.i += 1
                right = self.parse_level2()
                left = ('bin', t[1], left, right)
            else:
                break
        return left

    def parse_level2(self):
        left = self.parse_level3()
        t = self.peek()
        if t is not None and t[0] == 'op' and (t[1] == '==' or t[1] == '!=' or t[1] == '<' or t[1] == '>'):
            self.i += 1
            right = self.parse_level3()
            return ('bin', t[1], left, right)
        return left

    def parse_level3(self):
        left = self.parse_level4()
        while True:
            t = self.peek()
            if t is not None and t[0] == 'op' and (t[1] == '+' or t[1] == '-'):
                self.i += 1
                right = self.parse_level4()
                left = ('bin', t[1], left, right)
            else:
                break
        return left

    def parse_level4(self):
        left = self.parse_level5()
        while True:
            t = self.peek()
            if t is not None and t[0] == 'op' and (t[1] == '*' or t[1] == '/' or t[1] == '%'):
                self.i += 1
                right = self.parse_level5()
                left = ('bin', t[1], left, right)
            else:
                break
        return left

    def parse_level5(self):
        left = self.parse_level6()
        t = self.peek()
        if t is not None and t[0] == 'op' and t[1] == '~':
            self.i += 1
            right = self.parse_level5()
            return ('bin', '~', left, right)
        return left

    def parse_level6(self):
        t = self.peek()
        if t is not None and t[0] == 'op' and (t[1] == '-' or t[1] == '#' or t[1] == '!'):
            self.i += 1
            operand = self.parse_level6()
            return ('un', t[1], operand)
        return self.parse_level7()

    def parse_level7(self):
        t = self.peek()
        if t is None:
            raise ValueError('unexpected end')
        if t[0] == 'num':
            self.i += 1
            return ('num', t[1])
        if t[0] == 'word':
            if t[1] in KEYWORDS:
                raise ValueError('keyword')
            self.i += 1
            return ('var', t[1])
        if t[1] == '(':
            self.i += 1
            self.depth += 1
            if self.depth > 32:
                raise ValueError('too deep')
            node = self.parse_level1()
            nt = self.peek()
            if nt is None or nt[0] != 'op' or nt[1] != ')':
                raise ValueError('expected )')
            self.i += 1
            self.depth -= 1
            return node
        raise ValueError('unexpected token')


def current_body(root, stack):
    if not stack:
        return root
    e = stack[-1]
    if e['type'] == 'when' and e['has_else']:
        return e['else_body']
    return e['body']


def process_tokens(toks, lineno, root, stack):
    if not toks:
        return
    first = toks[0]
    if first[0] != 'word':
        raise ValueError('bad statement')
    w = first[1]
    if w == 'set':
        if len(toks) < 4:
            raise ValueError('short set')
        if toks[1][0] != 'word' or toks[1][1] in KEYWORDS:
            raise ValueError('bad name')
        if not (toks[2][0] == 'op' and toks[2][1] == '='):
            raise ValueError('expected =')
        p = Parser(toks)
        p.i = 3
        p.depth = 0
        expr = p.parse_level1()
        if p.i != len(toks):
            raise ValueError('trailing')
        current_body(root, stack).append(('set', lineno, toks[1][1], expr))
    elif w == 'out':
        p = Parser(toks)
        p.i = 1
        exprs = []
        while True:
            p.depth = 0
            exprs.append(p.parse_level1())
            t = p.peek()
            if t is not None and t[0] == 'op' and t[1] == ',':
                p.i += 1
                continue
            break
        if p.i != len(toks):
            raise ValueError('trailing')
        current_body(root, stack).append(('out', lineno, exprs))
    elif w == 'loop':
        p = Parser(toks)
        p.i = 1
        p.depth = 0
        expr = p.parse_level1()
        if p.i != len(toks):
            raise ValueError('trailing')
        if len(stack) >= 16:
            raise ValueError('too many blocks')
        body = []
        current_body(root, stack).append(('loop', lineno, expr, body))
        stack.append({'type': 'loop', 'line': lineno, 'body': body})
    elif w == 'when':
        p = Parser(toks)
        p.i = 1
        p.depth = 0
        expr = p.parse_level1()
        if p.i != len(toks):
            raise ValueError('trailing')
        if len(stack) >= 16:
            raise ValueError('too many blocks')
        body = []
        else_body = []
        current_body(root, stack).append(('when', lineno, expr, body, else_body))
        stack.append({'type': 'when', 'line': lineno, 'body': body,
                      'else_body': else_body, 'has_else': False})
    elif w == 'else':
        if len(toks) != 1:
            raise ValueError('trailing')
        if not stack or stack[-1]['type'] != 'when' or stack[-1]['has_else']:
            raise ValueError('bad else')
        stack[-1]['has_else'] = True
    elif w == 'end':
        if len(toks) != 1:
            raise ValueError('trailing')
        if not stack:
            raise ValueError('bad end')
        stack.pop()
    elif w == 'break':
        if len(toks) != 1:
            raise ValueError('trailing')
        if not any(e['type'] == 'loop' for e in stack):
            raise ValueError('bad break')
        current_body(root, stack).append(('break', lineno))
    else:
        raise ValueError('unknown statement')


class RuntimeErr(Exception):
    def __init__(self, line):
        self.line = line


class BreakSig(Exception):
    pass


def eval_expr(node, env, line):
    tag = node[0]
    if tag == 'num':
        return node[1]
    if tag == 'var':
        try:
            return env[node[1]]
        except KeyError:
            raise RuntimeErr(line)
    if tag == 'un':
        op = node[1]
        v = eval_expr(node[2], env, line)
        if op == '-':
            return (-v) & MASK
        if op == '#':
            return bin(v).count('1')
        return 1 if v == 0 else 0
    op = node[1]
    a = eval_expr(node[2], env, line)
    b = eval_expr(node[3], env, line)
    if op == '+':
        return (a + b) & MASK
    if op == '-':
        return (a - b) & MASK
    if op == '*':
        return (a * b) & MASK
    if op == '/':
        if b == 0:
            raise RuntimeErr(line)
        return a // b
    if op == '%':
        if b == 0:
            raise RuntimeErr(line)
        return a % b
    if op == '<':
        return 1 if a < b else 0
    if op == '>':
        return 1 if a > b else 0
    if op == '==':
        return 1 if a == b else 0
    if op == '!=':
        return 1 if a != b else 0
    if op == '<>':
        return a if a > b else b
    if op == '~':
        k = b & 31
        if k:
            return ((a << k) | (a >> (32 - k))) & MASK
        return a
    return a if a < b else b


def run_body(body, env):
    for node in body:
        tag = node[0]
        if tag == 'set':
            env[node[2]] = eval_expr(node[3], env, node[1])
        elif tag == 'out':
            vals = [eval_expr(e, env, node[1]) for e in node[2]]
            sys.stdout.write(' '.join(map(str, vals)) + '\n')
        elif tag == 'loop':
            line = node[1]
            n = eval_expr(node[2], env, line)
            body2 = node[3]
            for _ in range(n):
                try:
                    run_body(body2, env)
                except BreakSig:
                    break
        elif tag == 'when':
            line = node[1]
            if eval_expr(node[2], env, line) != 0:
                run_body(node[3], env)
            else:
                run_body(node[4], env)
        else:
            raise BreakSig


def main():
    sys.setrecursionlimit(10000)
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    if data.endswith(b'\n'):
        raw_lines = data.split(b'\n')[:-1]
    else:
        raw_lines = data.split(b'\n')

    root = []
    stack = []

    for idx, raw in enumerate(raw_lines, 1):
        bad = False
        for byte in raw:
            if byte == 9 or byte == 13 or (0x20 <= byte <= 0x7E):
                continue
            bad = True
            break
        if bad:
            sys.stdout.write('parse error line %d\n' % idx)
            sys.exit(2)
        if len(raw) > 1000:
            sys.stdout.write('parse error line %d\n' % idx)
            sys.exit(2)
        p = raw.find(b';')
        if p != -1:
            raw = raw[:p]
        s = raw.decode('ascii')
        try:
            toks = tokenize(s)
            process_tokens(toks, idx, root, stack)
        except ValueError:
            sys.stdout.write('parse error line %d\n' % idx)
            sys.exit(2)

    if stack:
        sys.stdout.write('parse error line %d\n' % stack[-1]['line'])
        sys.exit(2)

    env = {}
    try:
        run_body(root, env)
    except RuntimeErr as e:
        sys.stdout.write('runtime error line %d\n' % e.line)
        sys.exit(3)
    sys.exit(0)


if __name__ == '__main__':
    main()
