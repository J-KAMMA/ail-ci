"""The textual form of the IR: a printer and a parser. `print_program(parse_program(t)) == t`
for every `t` the printer produced (values are renumbered %0, %1, ... in definition order).

    func @collatz(%0: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "collatz"}
        effects {raises = ["OverflowError"]} {
      %1 = local.alloc {name = "steps"} : place<i64>
      %2 = const {value = 0} : i64
      store %1, %2
      loop {
        ...
        %7 = cmp.ne %5, %6 : i1
        if %7 {
          yield
        } {
          break
        }
        ...
        continue
      }
      ...
      return %12
    }

An instruction is `[results =] op [operands] [{attrs}] [: result types] [regions]`; a region is
`{ [^(%a: T, ...):] instructions }`. Attribute values are ints, floats (repr; `inf`, `-inf`,
`nan`), JSON strings, `true`/`false` and lists of those.
"""
import json
import math
import re

from . import ir as I
from .effects import Effects

# --------------------------------------------------------------------------------------------
# Printer
# --------------------------------------------------------------------------------------------


def _fmt_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return 'nan'
        if math.isinf(v):
            return 'inf' if v > 0 else '-inf'
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        return '[%s]' % ', '.join(_fmt_value(x) for x in v)
    raise I.IRError('unprintable attribute value %r' % (v,))


def _fmt_attrs(attrs):
    return '{%s}' % ', '.join('%s = %s' % (k, _fmt_value(attrs[k])) for k in sorted(attrs))


def _fmt_effects(e):
    parts = []
    for f in ('reads', 'writes', 'allocs', 'raises'):
        s = getattr(e, f)
        if s:
            parts.append('%s = %s' % (f, _fmt_value(sorted(s))))
    for f in ('io', 'unknown'):
        if getattr(e, f):
            parts.append('%s = true' % f)
    return '{%s}' % ', '.join(parts)


class _Namer(object):
    def __init__(self):
        self.names = {}

    def define(self, v):
        if v in self.names:
            raise I.IRError('value defined twice: %r' % (v,))
        self.names[v] = '%%%d' % len(self.names)
        return self.names[v]

    def use(self, v):
        try:
            return self.names[v]
        except KeyError:
            return '%%undefined<%s>' % (v.hint or '?')


def print_function(fn):
    namer = _Namer()
    params = ', '.join('%s: %s' % (namer.define(p), p.type) for p in fn.params)
    attrs = dict(fn.attrs)
    attrs['names'] = list(fn.param_names)
    head = 'func @%s(%s) -> (%s) attrs %s' % (fn.name, params, ', '.join(map(str, fn.results)),
                                             _fmt_attrs(attrs))
    if fn.effects is not None:
        head += ' effects ' + _fmt_effects(fn.effects)
    lines = [head + ' {']
    _print_region_body(fn.body, namer, lines, 1)
    lines.append('}')
    return '\n'.join(lines) + '\n'


def _print_region_body(region, namer, lines, depth):
    pad = '  ' * depth
    if region.args:
        lines.append(pad[:-2] + '^(%s):' % ', '.join('%s: %s' % (namer.define(a), a.type)
                                                     for a in region.args))
    for ins in region.instrs:
        _print_instr(ins, namer, lines, depth)


def _print_instr(ins, namer, lines, depth):
    pad = '  ' * depth
    text = ''
    operands = ', '.join(namer.use(v) for v in ins.operands)
    results = [namer.define(r) for r in ins.results]
    if results:
        text += ', '.join(results) + ' = '
    text += ins.op
    if operands:
        text += ' ' + operands
    if ins.attrs:
        text += ' ' + _fmt_attrs(ins.attrs)
    if ins.results:
        text += ' : ' + ', '.join(str(r.type) for r in ins.results)
    if not ins.regions:
        lines.append(pad + text)
        return
    lines.append(pad + text + ' {')
    for k, region in enumerate(ins.regions):
        _print_region_body(region, namer, lines, depth + 1)
        lines.append(pad + ('} {' if k + 1 < len(ins.regions) else '}'))


def print_program(program):
    return '\n'.join(print_function(program.functions[s]) for s in sorted(program.functions))


# --------------------------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------------------------

_TOKEN = re.compile(r'''
    (?P<ws>\s+|;[^\n]*)
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<arrow>->)
  | (?P<num>[-+]?(?:\d+\.\d*(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+|\d+|inf\b|nan\b))
  | (?P<val>%[A-Za-z0-9_.$]+)
  | (?P<sym>@[A-Za-z0-9_.$]+)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<punct>[(){}\[\]<>,:=^])
''', re.VERBOSE)


class ParseError(I.IRError):
    pass


def _tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError('bad character %r at offset %d' % (text[pos], pos))
        pos = m.end()
        kind = m.lastgroup
        if kind == 'ws':
            continue
        out.append((kind, m.group(kind)))
    out.append(('eof', ''))
    return out


class _Parser(object):
    def __init__(self, text):
        self.toks = _tokenize(text)
        self.i = 0
        self.scope = {}

    # -- token helpers
    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def accept(self, value):
        if self.peek()[1] == value and self.peek()[0] in ('punct', 'ident', 'arrow'):
            self.i += 1
            return True
        return False

    def expect(self, value):
        tok = self.next()
        if tok[1] != value:
            raise ParseError('expected %r, found %r' % (value, tok[1]))
        return tok

    def expect_kind(self, kind):
        tok = self.next()
        if tok[0] != kind:
            raise ParseError('expected %s, found %r' % (kind, tok[1]))
        return tok[1]

    # -- types
    def parse_type(self):
        kind, word = self.next()
        if kind != 'ident':
            raise ParseError('expected a type, found %r' % word)
        if word in ('fn', 'closure'):
            self.expect('<')
            params = self._type_list_paren()
            self.expect('->')
            results = self._type_list_paren()
            self.expect('>')
            return I.fn_type(params, results, closure=word == 'closure')
        if word not in I.HEADS:
            return I.class_type(word)
        args = []
        if self.accept('<'):
            if not self.accept('>'):
                args.append(self.parse_type())
                while self.accept(','):
                    args.append(self.parse_type())
                self.expect('>')
        return I.Type(word, args)

    def _type_list_paren(self):
        self.expect('(')
        out = []
        if not self.accept(')'):
            out.append(self.parse_type())
            while self.accept(','):
                out.append(self.parse_type())
            self.expect(')')
        return out

    # -- attributes
    def parse_value_literal(self):
        kind, word = self.next()
        if kind == 'num':
            if word.lstrip('+-') in ('inf', 'nan') or any(c in word for c in '.eE'):
                return float(word)
            return int(word)
        if kind == 'str':
            return json.loads(word)
        if kind == 'ident' and word in ('true', 'false'):
            return word == 'true'
        if kind == 'ident' and word in ('inf', 'nan'):
            return float(word)
        if word == '[':
            items = []
            if not self.accept(']'):
                items.append(self.parse_value_literal())
                while self.accept(','):
                    items.append(self.parse_value_literal())
                self.expect(']')
            return items
        raise ParseError('bad attribute value %r' % word)

    def parse_attrs(self):
        self.expect('{')
        attrs = {}
        if self.accept('}'):
            return attrs
        while True:
            key = self.expect_kind('ident')
            self.expect('=')
            attrs[key] = self.parse_value_literal()
            if self.accept('}'):
                return attrs
            self.expect(',')

    def at_attrs(self):
        return (self.peek()[1] == '{' and self.peek(1)[0] == 'ident' and self.peek(2)[1] == '=')

    # -- values
    def define(self, name, type):
        if name in self.scope:
            raise ParseError('value %s defined twice' % name)
        v = I.Value(type, hint=name[1:])
        self.scope[name] = v
        return v

    def use(self, name):
        try:
            return self.scope[name]
        except KeyError:
            raise ParseError('use of undefined value %s' % name)

    # -- structure
    def parse_program(self):
        program = I.Program()
        pending = []
        while self.peek()[0] != 'eof':
            pending.append(self.parse_function())
        for fn in pending:
            program.add(fn)
        return program

    def parse_function(self):
        self.scope = {}
        self.expect('func')
        name = self.expect_kind('sym')[1:]
        self.expect('(')
        params = []
        if not self.accept(')'):
            while True:
                pname = self.expect_kind('val')
                self.expect(':')
                params.append(self.define(pname, self.parse_type()))
                if self.accept(')'):
                    break
                self.expect(',')
        self.expect('->')
        results = self._type_list_paren()
        attrs = {}
        if self.accept('attrs'):
            attrs = self.parse_attrs()
        names = attrs.pop('names', [p.hint for p in params])
        effects = None
        if self.accept('effects'):
            e = self.parse_attrs()
            effects = Effects(e.get('reads', ()), e.get('writes', ()), e.get('allocs', ()),
                              e.get('raises', ()), e.get('io', False), e.get('unknown', False))
        body = self.parse_region()
        return I.Function(name, params, names, results, body, attrs, effects)

    def parse_region(self):
        self.expect('{')
        region = I.Region()
        if self.accept('^'):
            self.expect('(')
            if not self.accept(')'):
                while True:
                    aname = self.expect_kind('val')
                    self.expect(':')
                    region.args.append(self.define(aname, self.parse_type()))
                    if self.accept(')'):
                        break
                    self.expect(',')
            self.expect(':')
        while not self.accept('}'):
            region.instrs.append(self.parse_instr())
        return region

    def parse_instr(self):
        result_names = []
        if self.peek()[0] == 'val':
            result_names.append(self.next()[1])
            while self.accept(','):
                result_names.append(self.expect_kind('val'))
            self.expect('=')
        kind, op = self.next()
        if kind != 'ident':
            raise ParseError('expected an op name, found %r' % op)
        if not I.is_known_op(op):
            raise ParseError('unknown op %r' % op)
        operands = []
        if self.peek()[0] == 'val':
            operands.append(self.use(self.next()[1]))
            while self.accept(','):
                operands.append(self.use(self.expect_kind('val')))
        attrs = self.parse_attrs() if self.at_attrs() else {}
        types = []
        if self.accept(':'):
            types.append(self.parse_type())
            while self.accept(','):
                types.append(self.parse_type())
        if len(types) != len(result_names):
            raise ParseError('%s: %d result name(s) but %d type(s)' % (op, len(result_names), len(types)))
        regions = []
        while self.peek()[1] == '{' and not self.at_attrs():
            regions.append(self.parse_region())
        results = [self.define(n, t) for n, t in zip(result_names, types)]
        return I.Instr(op, operands, results, attrs, regions)


def parse_program(text):
    return _Parser(text).parse_program()


def parse_function(text):
    p = _Parser(text)
    fn = p.parse_function()
    if p.peek()[0] != 'eof':
        raise ParseError('trailing text after the function')
    return fn
