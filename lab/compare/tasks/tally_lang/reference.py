"""Reference implementation of tally_lang (see spec.md): reference.py SCRIPT

The script is parsed into an AST, then translated into Python source (three-address style, one
generated line per script statement part) and executed; Python's own UnboundLocalError /
ZeroDivisionError become Tally runtime errors, mapped back to script lines.
"""
import sys

KEYWORDS = {'set', 'out', 'loop', 'when', 'else', 'end', 'break'}
OPS = ['<>', '><', '==', '!=', '<', '>', '+', '-', '*', '/', '%', '~', '#', '!', '(', ')', ',', '=']
MAXV = 4294967295
ALLOWED = set(range(0x20, 0x7f)) | {9, 10, 13}
WS = ' \t\r'


class ParseError(Exception):
    pass


def tokenize(text):
    toks = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in WS:
            i += 1
        elif c.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            if j < n and (text[j].isdigit() or 'a' <= text[j] <= 'z' or text[j] == '_'):
                raise ParseError
            v = int(text[i:j])
            if v > MAXV:
                raise ParseError
            toks.append(('num', v))
            i = j
        elif 'a' <= c <= 'z' or c == '_':
            j = i
            while j < n and ('a' <= text[j] <= 'z' or text[j].isdigit() or text[j] == '_'):
                j += 1
            w = text[i:j]
            toks.append(('kw', w) if w in KEYWORDS else ('name', w))
            i = j
        else:
            for op in OPS:
                if text.startswith(op, i):
                    toks.append(('op', op))
                    i += len(op)
                    break
            else:
                raise ParseError
    return toks


class ExprParser:
    def __init__(self, toks, pos):
        self.toks = toks
        self.pos = pos
        self.depth = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else (None, None)

    def take_op(self, ops):
        k, v = self.peek()
        if k == 'op' and v in ops:
            self.pos += 1
            return v
        return None

    def level1(self):
        left = self.level2()
        while True:
            op = self.take_op(('<>', '><'))
            if op is None:
                return left
            left = ('bin', op, left, self.level2())

    def level2(self):
        left = self.level3()
        op = self.take_op(('==', '!=', '<', '>'))
        if op is None:
            return left
        node = ('bin', op, left, self.level3())
        k, v = self.peek()
        if k == 'op' and v in ('==', '!=', '<', '>'):
            raise ParseError
        return node

    def level3(self):
        left = self.level4()
        while True:
            op = self.take_op(('+', '-'))
            if op is None:
                return left
            left = ('bin', op, left, self.level4())

    def level4(self):
        left = self.level5()
        while True:
            op = self.take_op(('*', '/', '%'))
            if op is None:
                return left
            left = ('bin', op, left, self.level5())

    def level5(self):
        left = self.level6()
        if self.take_op(('~',)):
            return ('bin', '~', left, self.level5())
        return left

    def level6(self):
        op = self.take_op(('-', '#', '!'))
        if op is not None:
            return ('un', op, self.level6())
        return self.primary()

    def primary(self):
        k, v = self.peek()
        if k == 'num':
            self.pos += 1
            return ('num', v)
        if k == 'name':
            self.pos += 1
            return ('var', v)
        if k == 'op' and v == '(':
            self.pos += 1
            self.depth += 1
            if self.depth > 32:
                raise ParseError
            e = self.level1()
            if not self.take_op((')',)):
                raise ParseError
            self.depth -= 1
            return e
        raise ParseError


def parse_expr(toks, pos):
    p = ExprParser(toks, pos)
    e = p.level1()
    return e, p.pos


def parse_line(toks):
    """Returns a statement tuple (kind, ...) for a non-empty token list."""
    k, v = toks[0]
    if k != 'kw':
        raise ParseError
    if v == 'set':
        if len(toks) < 4 or toks[1][0] != 'name' or toks[2] != ('op', '='):
            raise ParseError
        e, pos = parse_expr(toks, 3)
        if pos != len(toks):
            raise ParseError
        return ('set', toks[1][1], e)
    if v == 'out':
        exprs = []
        pos = 1
        while True:
            e, pos = parse_expr(toks, pos)
            exprs.append(e)
            if pos == len(toks):
                return ('out', exprs)
            if toks[pos] != ('op', ','):
                raise ParseError
            pos += 1
    if v in ('loop', 'when'):
        e, pos = parse_expr(toks, 1)
        if pos != len(toks):
            raise ParseError
        return (v, e)
    if len(toks) != 1:
        raise ParseError
    return (v,)


def parse_program(data):
    """Returns (body, None) or (None, error_line)."""
    pieces = data.split(b'\n')
    if pieces and pieces[-1] == b'':
        pieces.pop()
    root = []
    stack = []   # entries: [kind, line, body_list, node]
    current = root
    for idx, raw in enumerate(pieces):
        line_no = idx + 1
        try:
            if len(raw) > 1000 or any(b not in ALLOWED for b in raw):
                raise ParseError
            text = raw.decode('ascii')
            cut = text.find(';')
            if cut >= 0:
                text = text[:cut]
            toks = tokenize(text)
            if not toks:
                continue
            st = parse_line(toks)
            kind = st[0]
            if kind in ('set', 'out'):
                current.append((kind, line_no) + st[1:])
            elif kind in ('loop', 'when'):
                if len(stack) >= 16:
                    raise ParseError
                node = [kind, line_no, st[1], [], None]   # when: then-body, else-body
                current.append(node)
                stack.append([kind, line_no, node, False])
                current = node[3]
            elif kind == 'else':
                if not stack or stack[-1][0] != 'when' or stack[-1][3]:
                    raise ParseError
                stack[-1][3] = True
                node = stack[-1][2]
                node[4] = []
                current = node[4]
            elif kind == 'end':
                if not stack:
                    raise ParseError
                stack.pop()
                if stack:
                    top = stack[-1]
                    current = top[2][4] if top[3] else top[2][3]
                else:
                    current = root
            elif kind == 'break':
                if not any(s[0] == 'loop' for s in stack):
                    raise ParseError
                current.append(('break', line_no))
        except ParseError:
            return None, line_no
    if stack:
        return None, stack[-1][1]
    return root, None


class Gen:
    def __init__(self):
        self.lines = []      # (indent, text, script_line)
        self.tmp = 0

    def emit(self, indent, text, line):
        self.lines.append((indent, text, line))

    def new_tmp(self):
        self.tmp += 1
        return 't%d' % self.tmp

    def simple(self, e, indent, line):
        """Expression -> operand string that is safe to use more than once (const/var/temp)."""
        s = self.expr(e, indent, line)
        if e[0] in ('num', 'var'):
            return s
        t = self.new_tmp()
        self.emit(indent, '%s = %s' % (t, s), line)
        return t

    def expr(self, e, indent, line, depth=0):
        kind = e[0]
        if kind == 'num':
            return str(e[1])
        if kind == 'var':
            return 'v_' + e[1]
        if depth > 12:
            return self.simple(e, indent, line)
        if kind == 'un':
            a = self.expr(e[2], indent, line, depth + 1)
            if e[1] == '-':
                return '((-%s) & 4294967295)' % a
            if e[1] == '#':
                return '(%s).bit_count()' % a
            return '(1 if %s == 0 else 0)' % a
        op = e[1]
        if op in ('<>', '><', '~'):
            a = self.simple(e[2], indent, line)
            b = self.simple(e[3], indent, line)
            if op == '<>':
                return '(%s if %s >= %s else %s)' % (a, a, b, b)
            if op == '><':
                return '(%s if %s <= %s else %s)' % (a, a, b, b)
            s = self.new_tmp()
            self.emit(indent, '%s = %s & 31' % (s, b), line)
            return '(((%s << %s) | (%s >> (32 - %s))) & 4294967295)' % (a, s, a, s)
        a = self.expr(e[2], indent, line, depth + 1)
        b = self.expr(e[3], indent, line, depth + 1)
        if op in ('+', '-', '*'):
            return '((%s %s %s) & 4294967295)' % (a, op, b)
        if op == '/':
            return '(%s // %s)' % (a, b)
        if op == '%':
            return '(%s %% %s)' % (a, b)
        return '(1 if %s %s %s else 0)' % (a, op, b)

    def block(self, body, indent):
        if not body:
            self.emit(indent, 'pass', 0)
        for st in body:
            kind = st[0]
            if kind == 'set':
                v = self.expr(st[3], indent, st[1])
                self.emit(indent, 'v_%s = %s' % (st[2], v), st[1])
            elif kind == 'out':
                vals = [self.simple(e, indent, st[1]) for e in st[2]]
                self.emit(indent, "_out(' '.join((%s,)))" % ', '.join('str(%s)' % v for v in vals), st[1])
            elif kind == 'break':
                self.emit(indent, 'break', st[1])
            elif kind == 'loop':
                v = self.expr(st[2], indent, st[1])
                self.emit(indent, 'for _ in range(%s):' % v, st[1])
                self.block(st[3], indent + 1)
            elif kind == 'when':
                v = self.expr(st[2], indent, st[1])
                self.emit(indent, 'if %s:' % v, st[1])
                self.block(st[3], indent + 1)
                if st[4] is not None:
                    self.emit(indent, 'else:', st[1])
                    self.block(st[4], indent + 1)


def main(argv):
    if len(argv) != 2:
        return 1
    try:
        with open(argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        return 1
    body, err = parse_program(data)
    if err is not None:
        sys.stdout.write('parse error line %d\n' % err)
        return 2
    g = Gen()
    g.block(body, 1)
    src = ['def _run(_out):']
    line_map = {}
    for i, (indent, text, line) in enumerate(g.lines):
        src.append('    ' * indent + text)
        line_map[i + 2] = line
    code = compile('\n'.join(src) + '\n', '<tally>', 'exec')
    env = {}
    exec(code, env)
    out = []
    try:
        env['_run'](out.append)
    except (NameError, ZeroDivisionError) as exc:
        tb = exc.__traceback__
        line = None
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == '<tally>':
                line = line_map[tb.tb_lineno]
            tb = tb.tb_next
        out.append('runtime error line %d' % line)
        sys.stdout.write('\n'.join(out) + '\n')
        return 3
    if out:
        sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.setrecursionlimit(20000)
    sys.exit(main(sys.argv))
