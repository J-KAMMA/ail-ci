"""S-expression surface for AIL: one canonical prefix form, converted to and from block syntax.

An S-expression source is translated to ordinary AIL block syntax and then compiled by the same
checked path, so both surfaces have exactly one meaning. `to_sexpr` goes the other way (block
source -> S-expression), so any AIL program can be shown in either form. Comments are not kept.

    (use checked_integer)
    (const LIMIT 10)
    (struct Point (x int) (y int))
    (impl Point (fn norm1 (self) int (return (+ (abs self.x) (abs self.y)))))
    (fn isqrt ((n int)) int
      (requires (>= n 0))
      (ensures (<= (* result result) n))
      (let r int 0)
      (while (<= (* (+ r 1) (+ r 1)) n) (+= r 1))
      (return r))

Statements: (let x T e) (= target e) (+= target e) and the other augmented forms, (return e?),
(if c (do ...) (do ...)?) with `elif` as an `if` alone in the else body, (while c ...),
(for x it ...), (try (do ...) (except E name|_ (do ...))... (finally (do ...))?), (raise e?),
(break) (continue) (pass), (requires c) (ensures c), or an expression.
Expressions: literals (1, -2, 1.5, "s", b"\\x00", true, false, none), names and dotted names
(sys.argv), (f a b :kw v) calls with (call f ...) when f is a form word, (x.m a) method calls on a
dotted receiver and (.m recv a) otherwise, (. e attr), (@ e i) and (@ e (: lo hi step)) with `_`
for an absent bound, operators (+ - * / // % ** << >> & | ^), comparisons (== != < <= > >= in
not-in is is-not) and (cmp a < b <= c) for chains, (and ...) (or ...) (not x) (neg x) (~ x),
(? c a b), (#list ...) (#tuple ...) (#set ...) (#dict k v ...), (#listcomp elt (for t it cond...)...)
and #setcomp/#dictcomp/#gen likewise, (lambda (a b) body).
Types: int float str bytes void and struct names, (list T), (dict K V), (tuple T ...),
(Callable (A ...) R).
"""
import ast
import io
import re
import tokenize

import ail_syntax


class SexprError(ValueError):
    pass


# ---------------------------------------------------------------- reading and writing atoms

_TOKEN = re.compile(r'''\s+|;[^\n]*|(?P<open>\()|(?P<close>\))|(?P<str>b?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))|(?P<atom>[^\s()"';]+)''', re.S)


def _tokens(text):
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if not match:
            raise SexprError('unreadable S-expression text at offset %d' % position)
        position = match.end()
        if match.group('open'):
            yield '('
        elif match.group('close'):
            yield ')'
        elif match.group('str'):
            yield ('str', match.group('str'))
        elif match.group('atom'):
            yield match.group('atom')


def parse(text):
    """Text -> nested Python lists; string literals stay as ('str', source) tuples."""
    stack = [[]]
    for token in _tokens(text):
        if token == '(':
            stack.append([])
        elif token == ')':
            if len(stack) == 1:
                raise SexprError('unbalanced )')
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token)
    if len(stack) != 1:
        raise SexprError('unbalanced (')
    return stack[0]


def _quote(value):
    """A Python string/bytes literal in double quotes."""
    body = repr(value)
    prefix = ''
    if body[0] == 'b':
        prefix, body = 'b', body[1:]
    if body[0] == "'":
        inner = body[1:-1].replace("\\'", "'").replace('"', '\\"')
        body = '"' + inner + '"'
    return prefix + body


def write(form, indent=0):
    """Nested lists -> text; a form wider than one line puts each argument on its own line."""
    flat = _flat(form)
    if len(flat) + indent <= 100 or not isinstance(form, list) or len(form) < 2:
        return flat
    head, rest = form[0], form[1:]
    pad = ' ' * (indent + 2)
    first = _flat(head)
    keep = 1 if head in ('fn', 'struct', 'impl', 'if', 'while', 'for', 'let', 'except', 'lambda') else 0
    if head == 'fn':
        keep = 3
    elif head == 'for':
        keep = 2
    elif head == 'except':
        keep = 2
    lead = ' '.join([first] + [_flat(x) for x in rest[:keep]])
    tail = [pad + write(x, indent + 2) for x in rest[keep:]]
    return '(' + lead + ('\n' + '\n'.join(tail) if tail else '') + ')'


def _flat(form):
    if isinstance(form, list):
        return '(' + ' '.join(_flat(x) for x in form) + ')'
    if isinstance(form, tuple):
        return form[1]
    return form


# ---------------------------------------------------------------- Python AST -> S-expression

_BINOPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.FloorDiv: '//', ast.Mod: '%',
           ast.Pow: '**', ast.LShift: '<<', ast.RShift: '>>', ast.BitAnd: '&', ast.BitOr: '|',
           ast.BitXor: '^'}
_CMPOPS = {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=',
           ast.In: 'in', ast.NotIn: 'not-in', ast.Is: 'is', ast.IsNot: 'is-not'}
_BINOP_OF = {v: k for k, v in _BINOPS.items()}
_CMPOP_OF = {v: k for k, v in _CMPOPS.items()}
_FORM_WORDS = ({'call', 'cmp', 'and', 'or', 'not', 'neg', '?', '@', ':', '.', 'lambda', 'let', '=',
                'if', 'do', 'while', 'for', 'return', 'break', 'continue', 'pass', 'try', 'except',
                'finally', 'raise', 'requires', 'ensures', 'fn', 'struct', 'impl', 'use', 'const', '~',
                'true', 'false', 'none', '_', 'del'}
               | set(_BINOP_OF) | set(_CMPOP_OF) | {op + '=' for op in _BINOP_OF})


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return None if base is None else base + '.' + node.attr
    return None


def expr(node):
    if isinstance(node, ast.Constant):
        value = node.value
        if value is True:
            return 'true'
        if value is False:
            return 'false'
        if value is None:
            return 'none'
        if isinstance(value, (str, bytes)):
            return ('str', _quote(value))
        if isinstance(value, (int, float)):
            return repr(value)
        raise SexprError('unsupported constant %r' % (value,))
    if isinstance(node, ast.Name):
        if node.id in _FORM_WORDS or not re.fullmatch(r'[A-Za-z_]\w*', node.id):
            raise SexprError('name %r collides with an S-expression form word' % node.id)
        return node.id
    if isinstance(node, ast.Attribute):
        dotted = _dotted(node)
        return dotted if dotted is not None else ['.', expr(node.value), node.attr]
    if isinstance(node, ast.Subscript):
        return ['@', expr(node.value), expr(node.slice)]
    if isinstance(node, ast.Slice):
        return [':', *(expr(x) if x is not None else '_' for x in (node.lower, node.upper))] + (
            [expr(node.step)] if node.step is not None else [])
    if isinstance(node, ast.Call):
        args = [expr(a) for a in node.args]
        for keyword in node.keywords:
            if keyword.arg is None:
                raise SexprError('**kwargs is unsupported')
            args += [':' + keyword.arg, expr(keyword.value)]
        if any(isinstance(a, ast.Starred) for a in node.args):
            raise SexprError('*args is unsupported')
        dotted = _dotted(node.func)
        if isinstance(node.func, ast.Name):
            head = node.func.id
            return (['call', head] if head in _FORM_WORDS else [head]) + args
        if dotted is not None:
            return [dotted] + args
        if isinstance(node.func, ast.Attribute):
            return ['.' + node.func.attr, expr(node.func.value)] + args
        return ['call', expr(node.func)] + args
    if isinstance(node, ast.BinOp):
        return [_BINOPS[type(node.op)], expr(node.left), expr(node.right)]
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float):
                return '-' + repr(node.operand.value)
            return ['neg', expr(node.operand)]
        if isinstance(node.op, ast.Not):
            return ['not', expr(node.operand)]
        if isinstance(node.op, ast.Invert):
            return ['~', expr(node.operand)]
        raise SexprError('unary + is unsupported')
    if isinstance(node, ast.BoolOp):
        return ['and' if isinstance(node.op, ast.And) else 'or'] + [expr(v) for v in node.values]
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1:
            return [_CMPOPS[type(node.ops[0])], expr(node.left), expr(node.comparators[0])]
        chain = ['cmp', expr(node.left)]
        for op, right in zip(node.ops, node.comparators):
            chain += [_CMPOPS[type(op)], expr(right)]
        return chain
    if isinstance(node, ast.IfExp):
        return ['?', expr(node.test), expr(node.body), expr(node.orelse)]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return ['#' + type(node).__name__.lower()] + [expr(e) for e in node.elts]
    if isinstance(node, ast.Dict):
        if any(k is None for k in node.keys):
            raise SexprError('**mapping in a dict literal is unsupported')
        return ['#dict'] + [x for k, v in zip(node.keys, node.values) for x in (expr(k), expr(v))]
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        head = {ast.ListComp: '#listcomp', ast.SetComp: '#setcomp', ast.GeneratorExp: '#gen',
                ast.DictComp: '#dictcomp'}[type(node)]
        elements = [expr(node.key), expr(node.value)] if isinstance(node, ast.DictComp) else [expr(node.elt)]
        generators = []
        for gen in node.generators:
            if gen.is_async:
                raise SexprError('async comprehension is unsupported')
            generators.append(['for', expr(gen.target), expr(gen.iter)] + [expr(c) for c in gen.ifs])
        return [head] + elements + generators
    if isinstance(node, ast.Lambda):
        a = node.args
        if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults:
            raise SexprError('only plain lambda parameters are supported')
        return ['lambda', [p.arg for p in a.args], expr(node.body)]
    raise SexprError('unsupported expression %s' % type(node).__name__)


def _type(node):
    """An annotation -> type form."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and node.value is None:
        return 'none'
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = node.value.id
        parts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if name == 'Callable':
            params, result = parts
            return ['Callable', [_type(p) for p in params.elts], _type(result)]
        return [name] + [_type(p) for p in parts]
    raise SexprError('unsupported type annotation %s' % ast.unparse(node))


def _result_type(node):
    """A translated return annotation (with the checked-marker wrapping) -> type form."""
    if node is None:
        return '_'
    if isinstance(node, ast.Name):
        match = re.fullmatch(r'__ail_checked_(.+)__', node.id)
        if match:
            return ['list', 'float'] if match[1] == 'flist' else match[1]
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == '__ail_checked_list':
        return ['list', _type(node.slice)]
    return _type(node)


def _body(statements):
    return [s for node in statements for s in [stmt(node)]]


def stmt(node):
    if isinstance(node, ast.Expr):
        call = node.value
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in ('__ail_requires__', '__ail_ensures__') and len(call.args) == 1):
            return [call.func.id[6:-2], expr(call.args[0])]
        return expr(node.value)
    if isinstance(node, ast.AnnAssign):
        return ['let', expr(node.target), _type(node.annotation), expr(node.value)]
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            raise SexprError('chained assignment is unsupported')
        return ['=', expr(node.targets[0]), expr(node.value)]
    if isinstance(node, ast.AugAssign):
        return [_BINOPS[type(node.op)] + '=', expr(node.target), expr(node.value)]
    if isinstance(node, ast.Return):
        return ['return'] + ([expr(node.value)] if node.value is not None else [])
    if isinstance(node, ast.If):
        form = ['if', expr(node.test), ['do'] + _body(node.body)]
        if node.orelse:
            form.append(['do'] + _body(node.orelse))
        return form
    if isinstance(node, ast.While):
        if node.orelse:
            raise SexprError('while-else is unsupported')
        return ['while', expr(node.test)] + _body(node.body)
    if isinstance(node, ast.For):
        if node.orelse:
            raise SexprError('for-else is unsupported')
        return ['for', expr(node.target), expr(node.iter)] + _body(node.body)
    if isinstance(node, ast.Try):
        if node.orelse:
            raise SexprError('try-else is unsupported')
        form = ['try', ['do'] + _body(node.body)]
        for handler in node.handlers:
            kind = expr(handler.type) if handler.type is not None else '_'
            form.append(['except', kind, handler.name or '_', ['do'] + _body(handler.body)])
        if node.finalbody:
            form.append(['finally', ['do'] + _body(node.finalbody)])
        return form
    if isinstance(node, ast.Raise):
        if node.cause is not None:
            raise SexprError('raise ... from is unsupported')
        return ['raise'] + ([expr(node.exc)] if node.exc is not None else [])
    if isinstance(node, ast.Break):
        return ['break']
    if isinstance(node, ast.Continue):
        return ['continue']
    if isinstance(node, ast.Pass):
        return ['pass']
    if isinstance(node, ast.Delete):
        return ['del'] + [expr(t) for t in node.targets]
    raise SexprError('unsupported statement %s' % type(node).__name__)


def _function(node):
    a = node.args
    if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults:
        raise SexprError('only plain positional parameters are supported')
    params = [p.arg if p.annotation is None else [p.arg, _type(p.annotation)] for p in a.args]
    return ['fn', node.name, params, _result_type(node.returns)] + _body(node.body)


def to_sexpr(source):
    """Block-syntax AIL source -> S-expression text."""
    imports = []
    entry = re.search(r'^\s*fn\s+main\s*\(', source, re.M) is not None
    text = ail_syntax.translate(source, module=not entry, imports=imports, keep_contracts=True)
    tree = ast.parse(text)
    forms = [['use', name] for name in imports]
    for node in tree.body:
        if isinstance(node, ast.Import) or (isinstance(node, ast.Expr) and ast.unparse(node) == 'sys.exit(main())'):
            continue
        if isinstance(node, ast.Assign):
            forms.append(['const', expr(node.targets[0]), expr(node.value)])
        elif isinstance(node, ast.ClassDef):
            init = node.body[0]
            forms.append(['struct', node.name] + [[p.arg, _type(p.annotation)] for p in init.args.args[1:]])
            methods = [_function(m) for m in node.body[1:]]
            if methods:
                forms.append(['impl', node.name] + methods)
        elif isinstance(node, ast.FunctionDef):
            forms.append(_function(node))
        else:
            raise SexprError('unsupported top-level %s' % type(node).__name__)
    return '\n\n'.join(write(form) for form in forms) + '\n'


# ---------------------------------------------------------------- S-expression -> block syntax

def _atom_expr(token):
    if isinstance(token, tuple):
        return ast.Constant(ast.literal_eval(token[1]))
    if token == 'true':
        return ast.Constant(True)
    if token == 'false':
        return ast.Constant(False)
    if token == 'none':
        return ast.Constant(None)
    if re.fullmatch(r'-?\d[\d_]*', token):
        value = int(token)
        return ast.UnaryOp(ast.USub(), ast.Constant(-value)) if token.startswith('-') else ast.Constant(value)
    if re.fullmatch(r'-?(\d[\d_]*\.\d*(e[-+]?\d+)?|\d[\d_]*e[-+]?\d+|inf|nan)', token, re.I) and token not in ('inf', 'nan'):
        value = float(token)
        return ast.UnaryOp(ast.USub(), ast.Constant(-value)) if token.startswith('-') else ast.Constant(value)
    if re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*', token):
        parts = token.split('.')
        node = ast.Name(parts[0])
        for attr in parts[1:]:
            node = ast.Attribute(node, attr)
        return node
    raise SexprError('unexpected atom %r' % (token,))


def _call_args(items):
    args, keywords, i = [], [], 0
    while i < len(items):
        item = items[i]
        if isinstance(item, str) and item.startswith(':') and len(item) > 1 and re.fullmatch(r':[A-Za-z_]\w*', item):
            if i + 1 >= len(items):
                raise SexprError('keyword %s needs a value' % item)
            keywords.append(ast.keyword(item[1:], to_expr(items[i + 1])))
            i += 2
        else:
            args.append(to_expr(item))
            i += 1
    return args, keywords


def to_expr(form):
    if not isinstance(form, list):
        return _atom_expr(form)
    if not form:
        raise SexprError('empty form')
    head, rest = form[0], form[1:]
    if isinstance(head, list):
        raise SexprError('a call head must be a name; use (call ...)')
    if head == 'call':
        args, keywords = _call_args(rest[1:])
        return ast.Call(to_expr(rest[0]), args, keywords)
    if head in _BINOP_OF and len(rest) == 2:
        return ast.BinOp(to_expr(rest[0]), _BINOP_OF[head](), to_expr(rest[1]))
    if head in _CMPOP_OF and len(rest) == 2:
        return ast.Compare(to_expr(rest[0]), [_CMPOP_OF[head]()], [to_expr(rest[1])])
    if head == 'cmp':
        left = to_expr(rest[0])
        ops = [_CMPOP_OF[op]() for op in rest[1::2]]
        return ast.Compare(left, ops, [to_expr(x) for x in rest[2::2]])
    if head in ('and', 'or'):
        return ast.BoolOp(ast.And() if head == 'and' else ast.Or(), [to_expr(x) for x in rest])
    if head == 'not':
        return ast.UnaryOp(ast.Not(), to_expr(rest[0]))
    if head == 'neg':
        return ast.UnaryOp(ast.USub(), to_expr(rest[0]))
    if head == '~':
        return ast.UnaryOp(ast.Invert(), to_expr(rest[0]))
    if head == '?':
        return ast.IfExp(to_expr(rest[0]), to_expr(rest[1]), to_expr(rest[2]))
    if head == '@':
        return ast.Subscript(to_expr(rest[0]), to_expr(rest[1]))
    if head == ':':
        bounds = [None if x == '_' else to_expr(x) for x in rest]
        return ast.Slice(*bounds)
    if head == '.':
        return ast.Attribute(to_expr(rest[0]), rest[1])
    if isinstance(head, str) and head.startswith('.') and len(head) > 1:
        args, keywords = _call_args(rest[1:])
        return ast.Call(ast.Attribute(to_expr(rest[0]), head[1:]), args, keywords)
    if head in ('#list', '#tuple', '#set'):
        kind = {'#list': ast.List, '#tuple': ast.Tuple, '#set': ast.Set}[head]
        return kind([to_expr(x) for x in rest])
    if head == '#dict':
        return ast.Dict([to_expr(k) for k in rest[0::2]], [to_expr(v) for v in rest[1::2]])
    if head in ('#listcomp', '#setcomp', '#gen', '#dictcomp'):
        count = 2 if head == '#dictcomp' else 1
        elements = [to_expr(x) for x in rest[:count]]
        generators = [ast.comprehension(to_expr(g[1]), to_expr(g[2]), [to_expr(c) for c in g[3:]], 0)
                      for g in rest[count:]]
        if head == '#dictcomp':
            return ast.DictComp(elements[0], elements[1], generators)
        kind = {'#listcomp': ast.ListComp, '#setcomp': ast.SetComp, '#gen': ast.GeneratorExp}[head]
        return kind(elements[0], generators)
    if head == 'lambda':
        params = ast.arguments([], [ast.arg(p) for p in rest[0]], None, [], [], None, [])
        return ast.Lambda(params, to_expr(rest[1]))
    if head in _FORM_WORDS:
        raise SexprError('%s is not an expression form here' % head)
    args, keywords = _call_args(rest)
    return ast.Call(_atom_expr(head), args, keywords)


def _block_expr(form):
    """Expression form -> block-syntax expression text (true/false spelled as AIL does)."""
    text = ast.unparse(ast.fix_missing_locations(to_expr(form)))
    out = []
    for part in tokenize.generate_tokens(io.StringIO(text).readline):
        value = part.string
        if part.type == tokenize.NAME and value in ('True', 'False'):
            value = value.lower()
        out.append((part.type, value))
    return tokenize.untokenize(out).strip()


def _type_text(form):
    if isinstance(form, str):
        return form
    head = form[0]
    if head == 'Callable':
        return 'Callable[[%s], %s]' % (', '.join(_type_text(p) for p in form[1]), _type_text(form[2]))
    return '%s[%s]' % (head, ', '.join(_type_text(p) for p in form[1:]))


def _block_stmts(forms, depth):
    return [line for form in forms for line in _block_stmt(form, depth)]


def _do(form):
    if not (isinstance(form, list) and form and form[0] == 'do'):
        raise SexprError('expected a (do ...) body')
    return form[1:]


def _block_stmt(form, depth):
    pad = '    ' * depth
    head = form[0] if isinstance(form, list) and form else None
    if head == 'let':
        return [pad + 'let %s: %s = %s;' % (form[1], _type_text(form[2]), _block_expr(form[3]))]
    if head == '=':
        return [pad + '%s = %s;' % (_block_expr(form[1]), _block_expr(form[2]))]
    if isinstance(head, str) and head.endswith('=') and head[:-1] in _BINOP_OF:
        return [pad + '%s %s %s;' % (_block_expr(form[1]), head, _block_expr(form[2]))]
    if head == 'return':
        return [pad + ('return %s;' % _block_expr(form[1]) if len(form) > 1 else 'return;')]
    if head in ('break', 'continue', 'pass'):
        return [pad + head + ';']
    if head == 'raise':
        return [pad + ('raise %s;' % _block_expr(form[1]) if len(form) > 1 else 'raise;')]
    if head == 'del':
        return [pad + 'del %s;' % ', '.join(_block_expr(t) for t in form[1:])]
    if head in ('requires', 'ensures'):
        return [pad + '%s %s;' % (head, _block_expr(form[1]))]
    if head == 'if':
        lines = [pad + 'if %s {' % _block_expr(form[1])] + _block_stmts(_do(form[2]), depth + 1)
        orelse = _do(form[3]) if len(form) > 3 else []
        while len(orelse) == 1 and isinstance(orelse[0], list) and orelse[0] and orelse[0][0] == 'if':
            nested = orelse[0]
            lines += [pad + '} elif %s {' % _block_expr(nested[1])] + _block_stmts(_do(nested[2]), depth + 1)
            orelse = _do(nested[3]) if len(nested) > 3 else []
        if orelse:
            lines += [pad + '} else {'] + _block_stmts(orelse, depth + 1)
        return lines + [pad + '}']
    if head == 'while':
        return [pad + 'while %s {' % _block_expr(form[1])] + _block_stmts(form[2:], depth + 1) + [pad + '}']
    if head == 'for':
        return ([pad + 'for %s in %s {' % (_block_expr(form[1]), _block_expr(form[2]))]
                + _block_stmts(form[3:], depth + 1) + [pad + '}'])
    if head == 'try':
        lines = [pad + 'try {'] + _block_stmts(_do(form[1]), depth + 1)
        for part in form[2:]:
            if part[0] == 'except':
                kind = '' if part[1] == '_' else ' ' + _block_expr(part[1])
                name = '' if part[2] == '_' else ' as ' + part[2]
                lines += [pad + '} except%s%s {' % (kind, name)] + _block_stmts(_do(part[3]), depth + 1)
            elif part[0] == 'finally':
                lines += [pad + '} finally {'] + _block_stmts(_do(part[1]), depth + 1)
            else:
                raise SexprError('try takes except and finally parts')
        return lines + [pad + '}']
    return [pad + _block_expr(form) + ';']


def _params_text(params):
    return ', '.join(p if isinstance(p, str) else '%s: %s' % (p[0], _type_text(p[1])) for p in params)


def _block_fn(form, depth):
    _, name, params, result, *body = form
    header = 'fn %s(%s)' % (name, _params_text(params)) + ('' if result == '_' else ' -> %s' % _type_text(result))
    pad = '    ' * depth
    return [pad + header + ' {'] + _block_stmts(body, depth + 1) + [pad + '}']


def to_block(text):
    """S-expression text -> block-syntax AIL source."""
    lines = []
    for form in parse(text):
        if not isinstance(form, list) or not form:
            raise SexprError('top level holds only forms')
        head = form[0]
        if head == 'use':
            lines.append('use %s;' % form[1])
        elif head == 'const':
            lines.append('const %s = %s;' % (form[1], _block_expr(form[2])))
        elif head == 'struct':
            lines.append('struct %s { %s }' % (form[1], ' '.join('%s: %s;' % (f, _type_text(t)) for f, t in form[2:])))
        elif head == 'impl':
            lines.append('impl %s {' % form[1])
            for method in form[2:]:
                lines += _block_fn(method, 1)
            lines.append('}')
        elif head == 'fn':
            lines += _block_fn(form, 0)
        else:
            raise SexprError('unknown top-level form %r' % (head,))
    return '\n'.join(lines) + '\n'


def detect(text):
    """An S-expression source starts (after blank lines and ; comments) with an open paren."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(';'):
            return stripped.startswith('(')
    return False


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('usage: python ail_sexpr.py FILE.ail  (block -> S-expression, or S-expression -> block)')
    source = open(sys.argv[1], encoding='utf-8').read()
    sys.stdout.write(to_block(source) if detect(source) else to_sexpr(source))
