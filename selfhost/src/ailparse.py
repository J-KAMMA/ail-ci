"""ailparse: a recursive-descent expression parser written in AIL.

``parse_expr(text)`` tokenizes ``text`` with :mod:`ailtok` and builds the :mod:`ailast` tree
CPython 3.12's ``ast.parse(text, mode="eval")`` builds, with attributes included.  A construct
outside the covered expression grammar raises ``ParseError`` whose message starts with
``ailparse:``.  The precedence follows ``Grammar/python.gram``; this is not a PEG engine.
"""
import ailast
import ailtok


class ParseError(Exception):
    pass


class _Ell:
    def __init__(self):
        pass
    def __repr__(self):
        return 'Ellipsis'


class _AwaitNode(ailast.AST):
    _typename = "Await"
    _fields = ('value',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset


SKIP = ('NL', 'NEWLINE', 'COMMENT', 'INDENT', 'DEDENT')
WALRUS = 'COLONEQUAL'


def _chr(n):
    return chr(n)


def _hexval(c):
    if c >= '0' and c <= '9':
        return ord(c) - 48
    if c >= 'a' and c <= 'f':
        return ord(c) - 87
    if c >= 'A' and c <= 'F':
        return ord(c) - 55
    return -1


def _octal(c):
    if c >= '0' and c <= '7':
        return ord(c) - 48
    return -1


def _normalize_newlines(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '\r':
            out.append('\n')
            i += 1
            if i < n and s[i] == '\n':
                i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _bytes_of(s):
    data = []
    k = 0
    while k < len(s):
        data.append(ord(s[k]))
        k += 1
    return bytes(data)


def _unescape(s, raw, as_bytes):
    s = _normalize_newlines(s)
    if raw:
        if as_bytes:
            return _bytes_of(s)
        return s
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c != '\\':
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            out.append('\\')
            break
        e = s[i]
        if as_bytes and (e == 'u' or e == 'U' or e == 'N'):
            out.append('\\')
            out.append(e)
            i += 1
        elif e == '\n':
            i += 1
        elif e == '\r':
            i += 1
            if i < n and s[i] == '\n':
                i += 1
        elif e == 'n':
            out.append('\n')
            i += 1
        elif e == 't':
            out.append('\t')
            i += 1
        elif e == 'r':
            out.append('\r')
            i += 1
        elif e == 'a':
            out.append('\a')
            i += 1
        elif e == 'b':
            out.append('\b')
            i += 1
        elif e == 'f':
            out.append('\f')
            i += 1
        elif e == 'v':
            out.append('\v')
            i += 1
        elif e == '\\':
            out.append('\\')
            i += 1
        elif e == "'":
            out.append("'")
            i += 1
        elif e == '"':
            out.append('"')
            i += 1
        elif e == 'x':
            i += 1
            v = 0
            k = 0
            while k < 2 and i < n:
                h = _hexval(s[i])
                if h < 0:
                    break
                v = v * 16 + h
                i += 1
                k += 1
            if k != 2:
                raise ParseError('ailparse: invalid \\x escape not supported')
            out.append(_chr(v))
        elif e == 'u':
            i += 1
            v = 0
            k = 0
            while k < 4 and i < n:
                h = _hexval(s[i])
                if h < 0:
                    break
                v = v * 16 + h
                i += 1
                k += 1
            if k != 4:
                raise ParseError('ailparse: invalid \\u escape not supported')
            out.append(_chr(v))
        elif e == 'U':
            i += 1
            v = 0
            k = 0
            while k < 8 and i < n:
                h = _hexval(s[i])
                if h < 0:
                    break
                v = v * 16 + h
                i += 1
                k += 1
            if k != 8:
                raise ParseError('ailparse: invalid \\U escape not supported')
            out.append(_chr(v))
        elif e == 'N':
            raise ParseError('ailparse: \\N named escape not supported')
        elif e >= '0' and e <= '7':
            v = _octal(e)
            i += 1
            k = 1
            while k < 3 and i < n:
                o = _octal(s[i])
                if o < 0:
                    break
                v = v * 8 + o
                i += 1
                k += 1
            if as_bytes:
                out.append(_chr(v & 255))
            else:
                out.append(_chr(v))
        else:
            out.append('\\')
            out.append(e)
            i += 1
    if as_bytes:
        return _bytes_of(''.join(out))
    return ''.join(out)


def _split_string_token(tok):
    s = tok
    j = 0
    n = len(s)
    while j < n and s[j] != "'" and s[j] != '"':
        j += 1
    prefix = s[:j]
    quote = s[j]
    ql = 1
    if j + 2 < n and s[j + 1] == quote and s[j + 2] == quote:
        ql = 3
    body = s[j + ql:n - ql]
    low = prefix.lower()
    return prefix, body, ql, ('r' in low), ('b' in low), ('u' in prefix)


def _merge_constants(values):
    out = []
    for v in values:
        if len(out) > 0 and isinstance(v, ailast.Constant) and isinstance(out[len(out) - 1], ailast.Constant):
            prev = out[len(out) - 1]
            if isinstance(prev.value, str) and isinstance(v.value, str):
                out[len(out) - 1] = ailast.Constant(prev.value + v.value, prev.kind,
                                                    prev.lineno, prev.col_offset,
                                                    v.end_lineno, v.end_col_offset)
                continue
        out.append(v)
    return out


class Parser:
    def __init__(self, text):
        self.text = text
        self.toks = ailtok.tokenize(text)
        self.i = 0
        self.prev = self.toks[0]
        self.starts = [0]
        k = 0
        n = len(text)
        while k < n:
            if text[k] == '\n':
                self.starts.append(k + 1)
            k += 1
        self._skip()

    def _skip(self):
        while self.i < len(self.toks) and self.toks[self.i].type in SKIP:
            self.i += 1

    def cur(self):
        return self.toks[self.i]

    def typ(self):
        return self.toks[self.i].type

    def val(self):
        return self.toks[self.i].string

    def is_name(self, name):
        t = self.toks[self.i]
        return t.type == 'NAME' and t.string == name

    def at(self, typ):
        return self.toks[self.i].type == typ

    def advance(self):
        self.prev = self.toks[self.i]
        self.i += 1
        self._skip()
        return self.prev

    def expect(self, typ, what):
        if not self.at(typ):
            raise ParseError('ailparse: expected ' + what + ' not supported')
        return self.advance()

    def expect_name(self, name):
        if not self.is_name(name):
            raise ParseError('ailparse: expected ' + name + ' not supported')
        return self.advance()

    def offset(self, tok):
        return self.starts[tok.srow - 1] + tok.scol

    def node(self, name, values, start):
        return self.mk(name, values, start)

    def plain(self, name, values):
        if name == 'arguments':
            return ailast.arguments(values[0], values[1], values[2], values[3], values[4], values[5], values[6])
        return ailast.comprehension(values[0], values[1], values[2], values[3])

    def mk(self, name, values, start):
        end = self.prev
        a = start.srow
        b = start.scol
        c = end.erow
        d = end.ecol
        if name == 'Constant':
            return ailast.Constant(values[0], values[1], a, b, c, d)
        if name == 'Name':
            return ailast.Name(values[0], values[1], a, b, c, d)
        if name == 'Attribute':
            return ailast.Attribute(values[0], values[1], values[2], a, b, c, d)
        if name == 'Call':
            return ailast.Call(values[0], values[1], values[2], a, b, c, d)
        if name == 'keyword':
            return ailast.keyword(values[0], values[1], a, b, c, d)
        if name == 'Starred':
            return ailast.Starred(values[0], values[1], a, b, c, d)
        if name == 'arg':
            return ailast.arg(values[0], values[1], values[2], a, b, c, d)
        if name == 'IfExp':
            return ailast.IfExp(values[0], values[1], values[2], a, b, c, d)
        if name == 'Lambda':
            return ailast.Lambda(values[0], values[1], a, b, c, d)
        if name == 'NamedExpr':
            return ailast.NamedExpr(values[0], values[1], a, b, c, d)
        if name == 'BoolOp':
            return ailast.BoolOp(values[0], values[1], a, b, c, d)
        if name == 'BinOp':
            return ailast.BinOp(values[0], values[1], values[2], a, b, c, d)
        if name == 'UnaryOp':
            return ailast.UnaryOp(values[0], values[1], a, b, c, d)
        if name == 'Compare':
            return ailast.Compare(values[0], values[1], values[2], a, b, c, d)
        if name == 'Slice':
            return ailast.Slice(values[0], values[1], values[2], a, b, c, d)
        if name == 'Subscript':
            return ailast.Subscript(values[0], values[1], values[2], a, b, c, d)
        if name == 'Tuple':
            return ailast.Tuple(values[0], values[1], a, b, c, d)
        if name == 'List':
            return ailast.List(values[0], values[1], a, b, c, d)
        if name == 'Set':
            return ailast.Set(values[0], a, b, c, d)
        if name == 'Dict':
            return ailast.Dict(values[0], values[1], a, b, c, d)
        if name == 'ListComp':
            return ailast.ListComp(values[0], values[1], a, b, c, d)
        if name == 'SetComp':
            return ailast.SetComp(values[0], values[1], a, b, c, d)
        if name == 'DictComp':
            return ailast.DictComp(values[0], values[1], values[2], a, b, c, d)
        if name == 'GeneratorExp':
            return ailast.GeneratorExp(values[0], values[1], a, b, c, d)
        if name == 'JoinedStr':
            return ailast.JoinedStr(values[0], a, b, c, d)
        if name == 'FormattedValue':
            return ailast.FormattedValue(values[0], values[1], values[2], a, b, c, d)
        raise ParseError('ailparse: node ' + name + ' not supported')

    def parse_namedexpr_test(self, allow):
        start = self.cur()
        left = self.parse_test()
        if self.at(WALRUS):
            if not allow:
                raise ParseError('ailparse: walrus here not supported')
            self.advance()
            if not isinstance(left, ailast.Name):
                raise ParseError('ailparse: walrus target not supported')
            target = ailast.Name(left.id, ailast.Store(), left.lineno, left.col_offset,
                                 left.end_lineno, left.end_col_offset)
            value = self.parse_test()
            return self.mk('NamedExpr', [target, value], start)
        return left

    def parse_test(self):
        start = self.cur()
        if self.is_name('lambda'):
            return self.parse_lambda()
        body = self.parse_or_test()
        if self.is_name('if'):
            self.advance()
            test = self.parse_or_test()
            self.expect_name('else')
            orelse = self.parse_test()
            return self.mk('IfExp', [test, body, orelse], start)
        return body

    def parse_lambda(self):
        start = self.cur()
        self.advance()
        args = self.parse_params(True)
        self.expect('COLON', ':')
        body = self.parse_test()
        return self.mk('Lambda', [args, body], start)

    def parse_params(self, is_lambda):
        posonly = []
        normal = []
        vararg = None
        kwonly = []
        kwdefs = []
        kwarg = None
        defaults = []
        seen_star = False
        seen_slash = False
        bare_star = False
        pending_default = None
        while True:
            self._skip()
            if self.at('COLON') or self.at('RPAR'):
                break
            if self.is_name('lambda'):
                break
            if self.at('COMMA'):
                self.advance()
                continue
            if self.at('SLASH'):
                if seen_slash:
                    raise ParseError('ailparse: / may appear only once not supported')
                if len(normal) == 0:
                    raise ParseError('ailparse: at least one argument must precede / not supported')
                seen_slash = True
                self.advance()
                k = 0
                while k < len(normal):
                    posonly.append(normal[k])
                    k += 1
                normal = []
                continue
            if self.at('STAR'):
                self.advance()
                seen_star = True
                if self.at('COMMA') or self.at('COLON') or self.at('RPAR'):
                    bare_star = True
                    continue
                if not self.at('NAME'):
                    raise ParseError('ailparse: lambda parameter not supported')
                t = self.cur()
                self.advance()
                vararg = self.mk('arg', [t.string, None, None], t)
                continue
            if self.at('DOUBLESTAR'):
                self.advance()
                if not self.at('NAME'):
                    raise ParseError('ailparse: lambda parameter not supported')
                t = self.cur()
                self.advance()
                kwarg = self.mk('arg', [t.string, None, None], t)
                continue
            if not self.at('NAME'):
                raise ParseError('ailparse: lambda parameter not supported')
            t = self.cur()
            self.advance()
            a = self.mk('arg', [t.string, None, None], t)
            default = None
            if self.at('EQUAL'):
                self.advance()
                default = self.parse_test()
            if seen_star:
                kwonly.append(a)
                kwdefs.append(default)
            else:
                normal.append(a)
                if default is not None:
                    defaults.append(default)
        if bare_star and len(kwonly) == 0:
            raise ParseError('ailparse: named arguments must follow bare * not supported')
        return self.plain('arguments', [posonly, normal, vararg, kwonly, kwdefs, kwarg, defaults])

    def parse_or_test(self):
        start = self.cur()
        left = self.parse_and_test()
        if not self.is_name('or'):
            return left
        values = [left]
        while self.is_name('or'):
            self.advance()
            values.append(self.parse_and_test())
        return self.mk('BoolOp', [ailast.Or(), values], start)

    def parse_and_test(self):
        start = self.cur()
        left = self.parse_not_test()
        if not self.is_name('and'):
            return left
        values = [left]
        while self.is_name('and'):
            self.advance()
            values.append(self.parse_not_test())
        return self.mk('BoolOp', [ailast.And(), values], start)

    def parse_not_test(self):
        start = self.cur()
        if self.is_name('not'):
            self.advance()
            operand = self.parse_not_test()
            return self.mk('UnaryOp', [ailast.Not(), operand], start)
        return self.parse_comparison()

    def parse_comparison(self):
        start = self.cur()
        left = self.parse_bit_or()
        ops = []
        comps = []
        while True:
            t = self.cur()
            if t.type in ('LESS', 'GREATER', 'EQEQUAL', 'GREATEREQUAL', 'LESSEQUAL', 'NOTEQUAL'):
                ops.append(self.cmp_node(t))
                self.advance()
                comps.append(self.parse_bit_or())
            elif self.is_name('in'):
                ops.append(ailast.In())
                self.advance()
                comps.append(self.parse_bit_or())
            elif self.is_name('is'):
                self.advance()
                if self.is_name('not'):
                    self.advance()
                    ops.append(ailast.IsNot())
                else:
                    ops.append(ailast.Is())
                comps.append(self.parse_bit_or())
            elif self.is_name('not'):
                self.advance()
                self.expect_name('in')
                ops.append(ailast.NotIn())
                comps.append(self.parse_bit_or())
            else:
                break
        if len(ops) == 0:
            return left
        return self.mk('Compare', [left, ops, comps], start)

    def cmp_node(self, t):
        if t.type == 'LESS':
            return ailast.Lt()
        if t.type == 'GREATER':
            return ailast.Gt()
        if t.type == 'EQEQUAL':
            return ailast.Eq()
        if t.type == 'GREATEREQUAL':
            return ailast.GtE()
        if t.type == 'LESSEQUAL':
            return ailast.LtE()
        return ailast.NotEq()

    def bin_type(self, level, t):
        if level == 0:
            return t == 'VBAR'
        if level == 1:
            return t == 'CIRCUMFLEX'
        if level == 2:
            return t == 'AMPER'
        if level == 3:
            return t == 'LEFTSHIFT' or t == 'RIGHTSHIFT'
        if level == 4:
            return t == 'PLUS' or t == 'MINUS'
        return t == 'STAR' or t == 'AT' or t == 'SLASH' or t == 'PERCENT' or t == 'DOUBLESLASH'

    def bin_op(self, level, t):
        if t == 'VBAR':
            return ailast.BitOr()
        if t == 'CIRCUMFLEX':
            return ailast.BitXor()
        if t == 'AMPER':
            return ailast.BitAnd()
        if t == 'LEFTSHIFT':
            return ailast.LShift()
        if t == 'RIGHTSHIFT':
            return ailast.RShift()
        if t == 'PLUS':
            return ailast.Add()
        if t == 'MINUS':
            return ailast.Sub()
        if t == 'AT':
            return ailast.MatMult()
        if t == 'SLASH':
            return ailast.Div()
        if t == 'PERCENT':
            return ailast.Mod()
        if t == 'DOUBLESLASH':
            return ailast.FloorDiv()
        return ailast.Mult()

    def parse_lower(self, level):
        if level == 0:
            return self.parse_bit_xor()
        if level == 1:
            return self.parse_bit_and()
        if level == 2:
            return self.parse_shift()
        if level == 3:
            return self.parse_sum()
        if level == 4:
            return self.parse_term()
        return self.parse_factor()

    def parse_bin(self, level):
        start = self.cur()
        left = self.parse_lower(level)
        while self.bin_type(level, self.cur().type):
            t = self.advance()
            right = self.parse_lower(level)
            left = self.mk('BinOp', [left, self.bin_op(level, t.type), right], start)
        return left

    def parse_bit_or(self):
        return self.parse_bin(0)

    def parse_bit_xor(self):
        return self.parse_bin(1)

    def parse_bit_and(self):
        return self.parse_bin(2)

    def parse_shift(self):
        return self.parse_bin(3)

    def parse_sum(self):
        return self.parse_bin(4)

    def parse_term(self):
        return self.parse_bin(5)

    def parse_factor(self):
        start = self.cur()
        if self.at('PLUS'):
            self.advance()
            operand = self.parse_factor()
            return self.mk('UnaryOp', [ailast.UAdd(), operand], start)
        if self.at('MINUS'):
            self.advance()
            operand = self.parse_factor()
            return self.mk('UnaryOp', [ailast.USub(), operand], start)
        if self.at('TILDE'):
            self.advance()
            operand = self.parse_factor()
            return self.mk('UnaryOp', [ailast.Invert(), operand], start)
        return self.parse_power()

    def parse_power(self):
        start = self.cur()
        left = self.parse_await_primary()
        if self.at('DOUBLESTAR'):
            self.advance()
            right = self.parse_factor()
            return self.mk('BinOp', [left, ailast.Pow(), right], start)
        return left

    def parse_await_primary(self):
        start = self.cur()
        if self.is_name('await'):
            self.advance()
            value = self.parse_primary()
            end = self.prev
            return _AwaitNode(value, start.srow, start.scol, end.erow, end.ecol)
        return self.parse_primary()

    def parse_primary(self):
        start = self.cur()
        node = self.parse_atom()
        while True:
            if self.at('DOT'):
                self.advance()
                if not self.at('NAME'):
                    raise ParseError('ailparse: attribute name not supported')
                t = self.cur()
                self.advance()
                node = self.mk('Attribute', [node, t.string, ailast.Load()], start)
            elif self.at('LPAR'):
                node = self.parse_call(node, start)
            elif self.at('LSQB'):
                node = self.parse_subscript(node, start)
            else:
                break
        return node

    def parse_call(self, func, start):
        self.advance()
        args = []
        keywords = []
        if self.at('RPAR'):
            self.advance()
            return self.mk('Call', [func, args, keywords], start)
        while True:
            if self.at('STAR'):
                self.advance()
                value = self.parse_test()
                args.append(self.mk('Starred', [value, ailast.Load()], self.prev))
            elif self.at('DOUBLESTAR'):
                self.advance()
                value = self.parse_test()
                keywords.append(self.mk('keyword', [None, value], self.prev))
            else:
                t = self.cur()
                if t.type == 'NAME' and self._next_type() == 'EQUAL':
                    self.advance()
                    self.advance()
                    value = self.parse_test()
                    keywords.append(self.mk('keyword', [t.string, value], t))
                else:
                    value = self.parse_namedexpr_test(True)
                    if self.is_name('for') or (self.is_name('async') and self._next_name() == 'for'):
                        gens = self.parse_comp_clauses()
                        gen = self.mk('GeneratorExp', [value, gens], t)
                        args.append(gen)
                        self.expect('RPAR', ')')
                        return self.mk('Call', [func, args, keywords], start)
                    args.append(value)
            if self.at('COMMA'):
                self.advance()
                if self.at('RPAR'):
                    break
                continue
            break
        self.expect('RPAR', ')')
        return self.mk('Call', [func, args, keywords], start)

    def _next_type(self):
        j = self.i + 1
        while j < len(self.toks) and self.toks[j].type in SKIP:
            j += 1
        if j < len(self.toks):
            return self.toks[j].type
        return ''

    def _next_name(self):
        j = self.i + 1
        while j < len(self.toks) and self.toks[j].type in SKIP:
            j += 1
        if j < len(self.toks):
            return self.toks[j].string if self.toks[j].type == 'NAME' else ''
        return ''

    def parse_subscript(self, value, start):
        self.advance()
        items = []
        trailing = False
        while True:
            if self.at('RSQB'):
                break
            items.append(self.parse_slice_item())
            trailing = False
            if self.at('COMMA'):
                self.advance()
                trailing = True
                continue
            break
        self.expect('RSQB', ']')
        if len(items) == 1 and not trailing and not isinstance(items[0], ailast.Starred):
            sl = items[0]
        else:
            sl = self.mk('Tuple', [items, ailast.Load()], start)
        return self.mk('Subscript', [value, sl, ailast.Load()], start)

    def parse_slice_item(self):
        start = self.cur()
        if self.at('STAR'):
            self.advance()
            value = self.parse_bit_or()
            return self.mk('Starred', [value, ailast.Load()], start)
        lower = None
        if not self.at('COLON'):
            lower = self.parse_namedexpr_test(True)
            if not self.at('COLON'):
                return lower
        self.expect('COLON', ':')
        upper = None
        step = None
        if not self.at('COLON') and not self.at('COMMA') and not self.at('RSQB'):
            upper = self.parse_namedexpr_test(True)
        if self.at('COLON'):
            self.advance()
            if not self.at('COMMA') and not self.at('RSQB'):
                step = self.parse_namedexpr_test(True)
        return self.mk('Slice', [lower, upper, step], start)

    def parse_atom(self):
        start = self.cur()
        t = self.cur()
        if t.type == 'NAME':
            self.advance()
            if t.string == 'yield':
                raise ParseError('ailparse: yield not supported')
            if t.string == 'True':
                return self.mk('Constant', [True, None], start)
            if t.string == 'False':
                return self.mk('Constant', [False, None], start)
            if t.string == 'None':
                return self.mk('Constant', [None, None], start)
            return self.mk('Name', [t.string, ailast.Load()], start)
        if t.type == 'NUMBER':
            self.advance()
            return self.mk('Constant', [self.number_value(t.string), None], start)
        if t.type == 'STRING' or t.type == 'FSTRING_START':
            return self.parse_strings()
        if t.type == 'ELLIPSIS':
            self.advance()
            return self.mk('Constant', [_Ell(), None], start)
        if t.type == 'LPAR':
            return self.parse_group(start)
        if t.type == 'LSQB':
            return self.parse_list_display(start)
        if t.type == 'LBRACE':
            return self.parse_brace_display(start)
        raise ParseError('ailparse: token ' + t.type + ' not supported')

    def number_value(self, s):
        last = s[len(s) - 1]
        if last == 'j' or last == 'J':
            raise ParseError('ailparse: complex literal not supported')
        if s.startswith('0x') or s.startswith('0X') or s.startswith('0o') or s.startswith('0O') or s.startswith('0b') or s.startswith('0B'):
            return int(s, 0)
        k = 0
        n = len(s)
        while k < n:
            c = s[k]
            if c == '.' or c == 'e' or c == 'E':
                return float(s)
            k += 1
        return int(s, 0)

    def parse_strings(self):
        start = self.cur()
        values = []
        any_f = False
        any_b = False
        any_s = False
        k = 0
        while self.at('STRING') or self.at('FSTRING_START'):
            if self.at('STRING'):
                t = self.advance()
                prefix, body, ql, raw, is_b, is_u = _split_string_token(t.string)
                if is_b:
                    any_b = True
                else:
                    any_s = True
                    if is_u:
                        kind = 'u'
                    else:
                        kind = None
                    if any_f:
                        values.append(self.mk('Constant', [_unescape(body, raw, False), kind], t))
                        continue
                val = _unescape(body, raw, is_b)
                values.append(self.mk('Constant', [val, kind_v(is_u, is_b)], t))
            else:
                any_f = True
                js = self.parse_fstring()
                k2 = 0
                while k2 < len(js.values):
                    values.append(js.values[k2])
                    k2 += 1
        if any_f:
            if any_b:
                raise ParseError('ailparse: bytes f-string not supported')
            combined = _merge_constants(values)
            merged = []
            k = 0
            while k < len(combined):
                v = combined[k]
                if not (isinstance(v, ailast.Constant) and isinstance(v.value, str) and v.value == ''):
                    merged.append(v)
                k += 1
            end = self.prev
            return ailast.JoinedStr(merged, start.srow, start.scol, end.erow, end.ecol)
        if len(values) == 1:
            v = values[0]
            return ailast.Constant(v.value, v.kind, start.srow, start.scol,
                                   self.prev.erow, self.prev.ecol)
        if any_b and any_s:
            raise ParseError('ailparse: cannot mix bytes and nonbytes literals not supported')
        val = values[0].value
        k = 1
        while k < len(values):
            val = val + values[k].value
            k += 1
        return ailast.Constant(val, values[0].kind, start.srow, start.scol,
                               self.prev.erow, self.prev.ecol)

    def parse_fstring(self):
        start = self.cur()
        prefix = start.string
        low = prefix[:len(prefix) - 1].lower()
        raw = 'r' in low
        self.advance()
        values = []
        while True:
            t = self.cur()
            if t.type == 'FSTRING_MIDDLE':
                self.advance()
                txt = _unescape(t.string, raw, False)
                if txt != '':
                    values.append(ailast.Constant(txt, None, t.srow, t.scol, t.erow, t.ecol))
            elif t.type == 'LBRACE':
                got = self.parse_replacement_field(raw)
                k = 0
                while k < len(got):
                    values.append(got[k])
                    k += 1
            elif t.type == 'FSTRING_END':
                self.advance()
                break
            else:
                raise ParseError('ailparse: f-string token ' + t.type + ' not supported')
        merged = _merge_constants(values)
        end = self.prev
        return ailast.JoinedStr(merged, start.srow, start.scol, end.erow, end.ecol)

    def parse_replacement_field(self, raw):
        self.advance()
        self._skip()
        first = self.cur()
        brace = self.prev
        expr_start = self.offset(brace) + len(brace.string)
        value = self.parse_namedexpr_test(True)
        conversion = -1
        debug = None
        if self.at('EQUAL'):
            eq = self.cur()
            self.advance()
            nxt = self.cur()
            debug = _normalize_newlines(self.text[expr_start:self.offset(nxt)])
            if self.at('EXCLAMATION'):
                self.advance()
                if not self.at('NAME'):
                    raise ParseError('ailparse: f-string conversion not supported')
                c = self.advance()
                conversion = ord(c.string[0])
            elif not self.at('COLON'):
                conversion = 114
        elif self.at('EXCLAMATION'):
            self.advance()
            if not self.at('NAME'):
                raise ParseError('ailparse: f-string conversion not supported')
            c = self.advance()
            conversion = ord(c.string[0])
        fmt = None
        if self.at('COLON'):
            self.advance()
            fmt = self.parse_format_spec(raw)
        else:
            self.expect('RBRACE', '}')
        out = []
        if debug is not None:
            cnode = ailast.Constant(debug, None, first.srow, first.scol, first.erow, first.ecol)
            out.append(cnode)
        out.append(self.mk('FormattedValue', [value, conversion, fmt], first))
        return out

    def parse_format_spec(self, raw):
        start = self.prev
        values = []
        while True:
            t = self.cur()
            if t.type == 'LBRACE' and self.i + 1 < len(self.toks):
                nxt = self.toks[self.i + 1]
                if (nxt.type == 'LBRACE' and self.prev.type != 'FSTRING_MIDDLE'
                        and self.offset(nxt) == self.offset(t) + len(t.string)):
                    values.append(ailast.Constant('', None, t.srow, t.scol, t.srow, t.scol))
            if t.type == 'FSTRING_MIDDLE':
                self.advance()
                txt = _unescape(t.string, raw, False)
                if txt != '' or len(values) > 0:
                    values.append(ailast.Constant(txt, None, t.srow, t.scol, t.erow, t.ecol))
            elif t.type == 'LBRACE':
                got = self.parse_replacement_field(raw)
                k = 0
                while k < len(got):
                    values.append(got[k])
                    k += 1
            elif t.type == 'RBRACE':
                self.advance()
                break
            else:
                raise ParseError('ailparse: format spec not supported')
        merged = _merge_constants(values)
        end = self.prev
        return ailast.JoinedStr(merged, start.srow, start.scol, end.erow, end.ecol)

    def parse_group(self, start):
        self.advance()
        if self.at('RPAR'):
            self.advance()
            return self.mk('Tuple', [[], ailast.Load()], start)
        if self.is_name('yield'):
            raise ParseError('ailparse: yield not supported')
        if self.at('STAR'):
            items = []
            saw_comma = False
            while True:
                items.append(self.parse_list_item())
                if self.at('COMMA'):
                    saw_comma = True
                    self.advance()
                    if self.at('RPAR'):
                        break
                    continue
                break
            self.expect('RPAR', ')')
            if not saw_comma:
                raise ParseError('ailparse: cannot use starred expression here not supported')
            return self.mk('Tuple', [items, ailast.Load()], start)
        first = self.parse_namedexpr_test(True)
        if self.is_name('for') or (self.is_name('async') and self._next_name() == 'for'):
            gens = self.parse_comp_clauses()
            self.expect('RPAR', ')')
            return self.mk('GeneratorExp', [first, gens], start)
        if self.at('COMMA'):
            items = [first]
            while self.at('COMMA'):
                self.advance()
                if self.at('RPAR'):
                    break
                if self.at('STAR'):
                    st = self.cur()
                    self.advance()
                    v = self.parse_test()
                    items.append(self.mk('Starred', [v, ailast.Load()], st))
                else:
                    items.append(self.parse_namedexpr_test(True))
            self.expect('RPAR', ')')
            return self.mk('Tuple', [items, ailast.Load()], start)
        self.expect('RPAR', ')')
        return first

    def parse_list_display(self, start):
        self.advance()
        if self.at('RSQB'):
            self.advance()
            return self.mk('List', [[], ailast.Load()], start)
        first = self.parse_list_item()
        if self.is_name('for') or (self.is_name('async') and self._next_name() == 'for'):
            gens = self.parse_comp_clauses()
            self.expect('RSQB', ']')
            return self.mk('ListComp', [first, gens], start)
        items = [first]
        while self.at('COMMA'):
            self.advance()
            if self.at('RSQB'):
                break
            items.append(self.parse_list_item())
        self.expect('RSQB', ']')
        return self.mk('List', [items, ailast.Load()], start)

    def parse_list_item(self):
        start = self.cur()
        if self.at('STAR'):
            self.advance()
            v = self.parse_test()
            return self.mk('Starred', [v, ailast.Load()], start)
        return self.parse_namedexpr_test(True)

    def parse_brace_display(self, start):
        self.advance()
        if self.at('RBRACE'):
            self.advance()
            return self.mk('Dict', [[], []], start)
        if self.at('DOUBLESTAR'):
            keys = []
            vals = []
            while True:
                if self.at('DOUBLESTAR'):
                    st = self.cur()
                    self.advance()
                    keys.append(None)
                    vals.append(self.parse_test())
                else:
                    kexpr = self.parse_namedexpr_test(True)
                    self.expect('COLON', ':')
                    vexpr = self.parse_test()
                    keys.append(kexpr)
                    vals.append(vexpr)
                if self.at('COMMA'):
                    self.advance()
                    if self.at('RBRACE'):
                        break
                    continue
                break
            self.expect('RBRACE', '}')
            return self.mk('Dict', [keys, vals], start)
        first = self.parse_list_item()
        if self.at('COLON'):
            self.advance()
            vexpr = self.parse_test()
            if self.is_name('for') or (self.is_name('async') and self._next_name() == 'for'):
                gens = self.parse_comp_clauses()
                self.expect('RBRACE', '}')
                return self.mk('DictComp', [first, vexpr, gens], start)
            keys = [first]
            vals = [vexpr]
            while self.at('COMMA'):
                self.advance()
                if self.at('RBRACE'):
                    break
                if self.at('DOUBLESTAR'):
                    self.advance()
                    keys.append(None)
                    vals.append(self.parse_test())
                else:
                    keys.append(self.parse_namedexpr_test(True))
                    self.expect('COLON', ':')
                    vals.append(self.parse_test())
            self.expect('RBRACE', '}')
            return self.mk('Dict', [keys, vals], start)
        if self.is_name('for') or (self.is_name('async') and self._next_name() == 'for'):
            gens = self.parse_comp_clauses()
            self.expect('RBRACE', '}')
            return self.mk('SetComp', [first, gens], start)
        items = [first]
        while self.at('COMMA'):
            self.advance()
            if self.at('RBRACE'):
                break
            items.append(self.parse_list_item())
        self.expect('RBRACE', '}')
        return self.mk('Set', [items], start)

    def parse_comp_clauses(self):
        out = []
        while True:
            is_async = 0
            if self.is_name('async'):
                self.advance()
                is_async = 1
            if not self.is_name('for'):
                if is_async:
                    raise ParseError('ailparse: async not supported')
                break
            self.advance()
            target = self.parse_comp_target()
            self.expect_name('in')
            iterable = self.parse_or_test()
            ifs = []
            while self.is_name('if'):
                self.advance()
                ifs.append(self.parse_or_test())
            out.append(self.plain('comprehension', [target, iterable, ifs, is_async]))
            if not self.is_name('for') and not self.is_name('async'):
                break
        return out

    def parse_comp_target(self):
        start = self.cur()
        items = []
        trailing = False
        while True:
            if self.is_name('in'):
                break
            if self.at('STAR'):
                st = self.cur()
                self.advance()
                v = self.parse_primary()
                items.append(self.mk('Starred', [self.store_ctx(v), ailast.Store()], st))
            else:
                v = self.parse_primary()
                items.append(self.store_ctx(v))
            trailing = False
            if self.at('COMMA'):
                self.advance()
                trailing = True
                continue
            break
        if len(items) == 1 and not trailing:
            return items[0]
        return self.mk('Tuple', [items, ailast.Store()], start)

    def store_ctx(self, node):
        if isinstance(node, ailast.Name):
            node.ctx = ailast.Store()
            return node
        if isinstance(node, ailast.Attribute):
            node.ctx = ailast.Store()
            return node
        if isinstance(node, ailast.Subscript):
            node.ctx = ailast.Store()
            return node
        if isinstance(node, ailast.Tuple):
            node.ctx = ailast.Store()
            k = 0
            while k < len(node.elts):
                self.store_ctx(node.elts[k])
                k += 1
            return node
        if isinstance(node, ailast.List):
            node.ctx = ailast.Store()
            k = 0
            while k < len(node.elts):
                self.store_ctx(node.elts[k])
                k += 1
            return node
        if isinstance(node, ailast.Starred):
            node.ctx = ailast.Store()
            self.store_ctx(node.value)
            return node
        raise ParseError('ailparse: assignment target not supported')


def kind_v(is_u, is_b):
    if is_b:
        return None
    if is_u:
        return 'u'
    return None




def parse_expr(text):
    p = Parser(text)
    start = p.cur()
    first = p.parse_namedexpr_test(False)
    if p.at('COMMA'):
        items = [first]
        trailing = False
        while p.at('COMMA'):
            p.advance()
            trailing = True
            if p.at('ENDMARKER') or p.i >= len(p.toks):
                break
            items.append(p.parse_test())
            trailing = False
        first = p.mk('Tuple', [items, ailast.Load()], start)
    if not p.at('ENDMARKER'):
        raise ParseError('ailparse: trailing tokens not supported')
    return first
