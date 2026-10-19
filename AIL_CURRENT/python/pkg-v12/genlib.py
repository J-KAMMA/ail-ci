"""Library names of the general (boxed) path (branch genlib).

The general path has no table of library functions of its own (NAMES_library.json is not part of this tree), so a
program that calls `json.dumps`, `itertools.product`, `functools.partial`, `statistics.stdev` ... was refused with
"(not yet published in NAMES_library.json)". `rewrite(tree)` is run by pyboxed2.Compiler.compile on the general path
only: it renames each use of a name of TABLE (`json.dumps(x)`, `from json import dumps; dumps(x)`,
`itertools.chain.from_iterable(xs)`) to a function or class of prelude_genlib.py (and prelude_random.py), and adds
the source of exactly the pieces that are reached, after the program's imports. A program that uses none of the
names is returned untouched, so its C does not change. The pieces are ordinary Python, compared with the library by
tests/test_ail_genlib.py (the file imports under CPython); generator functions among them use the general path's
generators (safetyrt.GEN_PRELUDE), which the compiler adds after this pass.

A name the program binds itself (`def partial`, a parameter called `date`) is not renamed, and the use is refused as
it was. Calls with an argument the pieces do not take (`json.dumps(cls=...)`) are refused here by name.
"""
import ast
import copy
import os
import re

from pyfront import Unsupported

HERE = os.path.dirname(os.path.abspath(__file__))

# 'module.attr[.attr]' -> the name in the prelude
TABLE = {
    'json.dumps': '_ail_json_dumps',
    'json.loads': '_ail_json_loads',
    'json.JSONDecodeError': 'JSONDecodeError',
    'json.decoder.JSONDecodeError': 'JSONDecodeError',
    'itertools.chain': '_ail_chain',
    'itertools.chain.from_iterable': '_ail_chain_from_iterable',
    'itertools.islice': '_ail_islice',
    'itertools.cycle': '_ail_cycle',
    'itertools.product': '_ail_product',
    'itertools.count': '_ail_count',
    'itertools.repeat': '_ail_repeat',
    'itertools.pairwise': '_ail_pairwise',
    'itertools.compress': '_ail_compress',
    'itertools.filterfalse': '_ail_filterfalse',
    'itertools.batched': '_ail_batched',
    'math.isclose': '_ail_isclose',
    'statistics.mean': '_ail_st_mean',
    'statistics.fmean': '_ail_st_fmean',
    'statistics.median': '_ail_st_median',
    'statistics.median_low': '_ail_st_median_low',
    'statistics.median_high': '_ail_st_median_high',
    'statistics.mode': '_ail_st_mode',
    'statistics.multimode': '_ail_st_multimode',
    'statistics.variance': '_ail_st_variance',
    'statistics.pvariance': '_ail_st_pvariance',
    'statistics.stdev': '_ail_st_stdev',
    'statistics.pstdev': '_ail_st_pstdev',
    'statistics.geometric_mean': '_ail_st_geometric_mean',
    'statistics.harmonic_mean': '_ail_st_harmonic_mean',
    'statistics.StatisticsError': 'StatisticsError',
    'datetime.date': 'date',
    'datetime.datetime': 'datetime',
    'datetime.timedelta': 'timedelta',
    'datetime.date.fromisoformat': '_ail_date_fromisoformat',
    'datetime.date.fromordinal': '_ail_date_fromordinal',
    'datetime.datetime.fromisoformat': '_ail_datetime_fromisoformat',
    'datetime.datetime.strptime': '_ail_datetime_strptime',
}
for _name in ('seed', 'random', 'randint', 'randrange', 'uniform', 'gauss', 'choice', 'shuffle',
              'sample', 'getrandbits', 'choices', 'expovariate', 'triangular'):
    TABLE['random.' + _name] = '_ail_rng.' + _name

# names whose calls take only these keyword arguments (others are refused by name)
KEYWORDS = {
    '_ail_json_dumps': {'skipkeys', 'ensure_ascii', 'check_circular', 'allow_nan', 'indent', 'separators',
                        'default', 'sort_keys'},
    '_ail_json_loads': {'object_hook', 'parse_float', 'parse_int', 'parse_constant', 'object_pairs_hook'},
    '_ail_product': {'repeat'},
    '_ail_count': {'start', 'step'},
    '_ail_repeat': {'times'},
    '_ail_isclose': {'rel_tol', 'abs_tol'},
    '_ail_islice': set(),
    '_ail_st_variance': {'xbar'},
    '_ail_st_stdev': {'xbar'},
    '_ail_st_pvariance': {'mu'},
    '_ail_st_pstdev': {'mu'},
    '_ail_st_mean': set(),
    '_ail_st_fmean': set(),
    '_ail_st_median': set(),
    '_ail_st_median_low': set(),
    '_ail_st_median_high': set(),
    '_ail_st_mode': set(),
    '_ail_st_multimode': set(),
    '_ail_st_geometric_mean': set(),
    '_ail_st_harmonic_mean': set(),
    'date': {'year', 'month', 'day'},
    'datetime': {'year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond'},
    'timedelta': {'days', 'seconds', 'microseconds', 'milliseconds', 'minutes', 'hours', 'weeks'},
}
# the pieces that take *args: a call may pass `*rows`
VARARGS = {'_ail_product', '_ail_chain', '_ail_islice'}
# attributes of these classes that are not built (a class method that reads the clock, tzinfo ...)
NOT_BUILT = {
    'datetime.date': 'date.today(), date.fromtimestamp() and the class attributes min / max / resolution',
    'datetime.datetime': 'datetime.now(), utcnow(), today(), fromtimestamp(), combine(), tzinfo and the class attributes',
    'datetime.timedelta': 'the class attributes min / max / resolution',
}

# prelude files by the prelude name's family
_cache = {}


def _source():
    if 'src' not in _cache:
        with open(os.path.join(HERE, 'prelude_genlib.py'), 'r', encoding='utf-8') as f:
            text = f.read()
        _cache['src'] = text
    return _cache['src']


def _random_source():
    """prelude_random.py with its math calls lowered the way the program's own are (ail_syntax.python_surface):
    `math.log` -> `_ail_math_log` and the helper definitions it needs, which pyboxed2 adds unless the program has them."""
    import sys
    import stdlib5
    top = os.path.dirname(os.path.dirname(HERE))
    if top not in sys.path:
        sys.path.append(top)
    import ail_syntax
    return ail_syntax.python_surface('import math\n' + stdlib5.prelude('random'))


MODULES = frozenset(k.split('.')[0] for k in TABLE) | {'functools'}


def _bound_names(tree):
    """Every name the program itself binds (assignments, parameters, defs, classes, imports, loop and with targets)."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.Global):
            out.update(n.names)
    return out


_STRFTIME = re.compile(r'%[-_0]?[A-Za-z]')


def _simple(v):
    """A value that may be read again each time a lambda runs: a constant, a (signed) number, a name."""
    if isinstance(v, ast.UnaryOp) and isinstance(v.op, (ast.USub, ast.UAdd)):
        v = v.operand
    return isinstance(v, ast.Constant) or (isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load))


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return parts
    return None


class _Renamer(ast.NodeTransformer):
    def __init__(self, aliases, names, defs):
        self.aliases = aliases     # local name -> module (import m [as a])
        self.names = names         # local name -> 'module.attr' (from m import attr [as b])
        self.defs = defs           # top-level def name -> its parameter names (plain parameters only)
        self.used = set()
        self.partials = 0
        self.dates = any(v.split('.')[0] == 'datetime' for v in list(aliases.values()) + list(names.values()))

    def _key(self, node):
        parts = _dotted(node)
        if not parts:
            return None
        head = parts[0]
        if head in self.names:
            full = self.names[head].split('.') + parts[1:]
        elif head in self.aliases:
            full = self.aliases[head].split('.') + parts[1:]
        else:
            return None
        return '.'.join(full)

    def _swap(self, node):
        key = self._key(node)
        if key is not None and key in TABLE:
            target = TABLE[key]
            if '.' in target:
                head, attr = target.split('.')
                self.used.add(head)
                return ast.copy_location(ast.Attribute(value=ast.Name(id=head, ctx=ast.Load()), attr=attr,
                                                       ctx=ast.Load()), node)
            self.used.add(target)
            return ast.copy_location(ast.Name(id=target, ctx=node.ctx), node)
        return None

    def visit_Attribute(self, node):
        new = self._swap(node)
        if new is not None:
            return new
        key = self._key(node)
        if key is not None:
            for cls, what in NOT_BUILT.items():
                if key.startswith(cls + '.') and key not in TABLE:
                    raise Unsupported('%s.%s is not built on the general path (%s)' % (cls, key[len(cls) + 1:].split('.')[0], what))
        self.generic_visit(node)
        return node

    def visit_FormattedValue(self, node):
        """f"{when:%Y-%m-%d}" with a date / datetime: its strftime (the general path has no __format__)."""
        self.generic_visit(node)
        spec = node.format_spec
        if (self.dates and isinstance(spec, ast.JoinedStr) and len(spec.values) == 1
                and isinstance(spec.values[0], ast.Constant) and isinstance(spec.values[0].value, str)
                and _STRFTIME.search(spec.values[0].value)):
            self.used.add('_ail_dt_format')
            node.value = ast.copy_location(ast.Call(func=ast.Name(id='_ail_dt_format', ctx=ast.Load()),
                                                    args=[node.value, ast.Constant(value=spec.values[0].value)],
                                                    keywords=[]), node.value)
            node.format_spec = None
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.names:
            new = self._swap(node)
            if new is not None:
                return new
        return node

    def _partial(self, node):
        """functools.partial(f, a, b, k=v) of a def or lambda of the program, whose parameters are all plain: a closure
        built where partial() was called (the general path has no callable instances), `(lambda _b0: lambda _p0: f(_b0,
        _p0))(a)`. As the function argument of map / filter / sorted(key=) ... with bound values that are constants or
        names it is the plain lambda those calls take."""
        if not node.args or any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            raise Unsupported('functools.partial() with no function or with *args / **kwargs is not built on the general path')
        fn = self.visit(node.args[0])
        if isinstance(fn, ast.Name) and fn.id in self.defs:
            params = self.defs[fn.id]
        elif isinstance(fn, ast.Lambda) and not (fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.defaults
                                                 or fn.args.posonlyargs):
            params = [a.arg for a in fn.args.args]
        else:
            raise Unsupported('functools.partial() of anything but a def or lambda of the program with plain parameters '
                              '(its number of parameters must be known; no callable instances on the general path)')
        bound = [self.visit(a) for a in node.args[1:]]
        kws = [(k.arg, self.visit(k.value)) for k in node.keywords]
        if len(bound) + len(kws) > len(params):
            raise Unsupported('functools.partial() binds more arguments than the function has parameters')
        if kws and [n for n, _ in kws] != params[len(params) - len(kws):]:
            raise Unsupported('functools.partial() with keyword arguments is built only for the last parameters of the '
                              'function, in order')
        self.partials += 1
        tag = self.partials
        bnames = ['_pb%d_%d' % (tag, i) for i in range(len(bound) + len(kws))]
        rest = len(params) - len(bound) - len(kws)
        pnames = ['_pa%d_%d' % (tag, i) for i in range(rest)]

        def build(values, free):
            call = ast.Call(func=copy.deepcopy(fn),
                            args=[ast.Name(id=v, ctx=ast.Load()) if free else v for v in values[:len(bound)]]
                            + [ast.Name(id=n, ctx=ast.Load()) for n in pnames],
                            keywords=[ast.keyword(arg=n, value=(ast.Name(id=bnames[len(bound) + i], ctx=ast.Load())
                                                                 if free else v))
                                      for i, (n, v) in enumerate(kws)])
            return ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in pnames], kwonlyargs=[],
                                                 kw_defaults=[], defaults=[]), body=call)
        values = bound + [v for _, v in kws]
        if not values:
            out = build([], False)
            out._ail_inline = out
            return ast.copy_location(out, node)
        inner = build(bnames, True)
        outer = ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in bnames], kwonlyargs=[],
                                              kw_defaults=[], defaults=[]), body=inner)
        out = ast.Call(func=outer, args=values, keywords=[])
        if all(_simple(v) for v in values):
            out._ail_inline = build(values, False)
        return ast.copy_location(out, node)

    def visit_Call(self, node):
        if self._key(node.func) == 'functools.partial':
            return self._partial(node)
        self.generic_visit(node)
        f = node.func
        if (self.dates and isinstance(f, ast.Name) and f.id == 'format' and len(node.args) == 2 and not node.keywords
                and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)
                and _STRFTIME.search(node.args[1].value)):
            self.used.add('_ail_dt_format')
            node.func = ast.Name(id='_ail_dt_format', ctx=ast.Load())
            return node
        # a partial() given straight to map / filter / sorted(key=) ...: the plain lambda
        if isinstance(f, ast.Name) and f.id in ('map', 'filter', 'sorted', 'min', 'max', 'sort'):
            node.args = [getattr(a, '_ail_inline', a) if i == 0 and f.id in ('map', 'filter') else a
                         for i, a in enumerate(node.args)]
            for k in node.keywords:
                if k.arg == 'key':
                    k.value = getattr(k.value, '_ail_inline', k.value)
        elif isinstance(f, ast.Attribute) and f.attr == 'sort':
            for k in node.keywords:
                if k.arg == 'key':
                    k.value = getattr(k.value, '_ail_inline', k.value)
        if (isinstance(f, ast.Attribute) and f.attr == 'seed' and isinstance(f.value, ast.Name) and f.value.id == '_ail_rng'):
            if (len(node.args) != 1 or node.keywords or isinstance(node.args[0], ast.Starred)
                    or (isinstance(node.args[0], ast.Constant) and not isinstance(node.args[0].value, int))):
                raise Unsupported('random.seed() needs one int seed here: a str, float, bytes or None seed is hashed by '
                                  'CPython and is not reproduced')
        if isinstance(f, ast.Name) and f.id == '_ail_product' and node.keywords:
            if len(node.keywords) != 1 or node.keywords[0].arg != 'repeat':
                raise Unsupported('itertools.product() with a keyword argument other than repeat= is not built')
            node.func = ast.Name(id='_ail_product_rep', ctx=ast.Load())
            node.args = [node.keywords[0].value, ast.List(elts=node.args, ctx=ast.Load())]
            node.keywords = []
            self.used.add('_ail_product_rep')
            return node
        if isinstance(f, ast.Name) and f.id in KEYWORDS:
            allowed = KEYWORDS[f.id]
            for k in node.keywords:
                if k.arg is None or k.arg not in allowed:
                    raise Unsupported('%s() with the keyword argument %s is not built on the general path'
                                      % (_pretty(f.id), k.arg if k.arg else '**'))
            if f.id not in VARARGS and any(isinstance(a, ast.Starred) for a in node.args):
                raise Unsupported('%s() with a *args argument is not built on the general path' % _pretty(f.id))
        return node


def _pretty(name):
    for key, value in TABLE.items():
        if value == name or value.split('.')[0] == name:
            return key
    return name


def _imports(tree):
    aliases = {}
    names = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split('.')[0]
                if a.asname:
                    aliases[a.asname] = a.name
                elif top in MODULES:
                    aliases[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level and node.module.split('.')[0] in MODULES:
            for a in node.names:
                if a.name != '*':
                    names[a.asname or a.name] = node.module + '.' + a.name
    return aliases, names


def _drop_imports(tree, aliases, names, used):
    """Remove the imports whose names the program no longer reads (every use was renamed), so the compiler does not
    see a from-import alias such as `dt` where one of the added pieces has a local variable of that name."""
    reads = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

    def gone(local, handled):
        return local in handled and (local in used or local not in reads)
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            node.names = [a for a in node.names if not gone(a.asname or a.name.split('.')[0], aliases)]
            if not node.names:
                continue
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            node.names = [a for a in node.names if not gone(a.asname or a.name, names)]
            if not node.names:
                continue
        body.append(node)
    tree.body = body


def rewrite(tree):
    """Rename the library names of TABLE in `tree` (in place). Returns (prelude source text or '', names added)."""
    aliases, names = _imports(tree)
    if not aliases and not names:
        return '', set()
    bound = _bound_names(tree)
    # a name that the program binds anywhere (a parameter, a local ...) as well as importing it is left alone: the
    # general path reads a local that has the name of a module-level class as that class
    aliases = {a: m for a, m in aliases.items() if a not in bound}
    names = {a: m for a, m in names.items() if a not in bound}
    if not aliases and not names:
        return '', set()
    defs = {}
    for n in tree.body:
        if (isinstance(n, ast.FunctionDef) and not n.decorator_list and not (
                n.args.vararg or n.args.kwarg or n.args.kwonlyargs or n.args.defaults or n.args.posonlyargs)):
            defs[n.name] = [a.arg for a in n.args.args]
    r = _Renamer(aliases, names, defs)
    tree.body = [r.visit(n) for n in tree.body]
    if not r.used:
        return '', set()
    for each in ast.walk(tree):
        # `import datetime` next to the class datetime: a use of the module that was not renamed would read the class
        if (isinstance(each, ast.Attribute) and isinstance(each.value, ast.Name) and each.value.id in aliases
                and each.value.id in r.used):
            raise Unsupported('%s.%s is not built on the general path' % (aliases[each.value.id], each.attr))
    own ={n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | bound
    clash = sorted(n for n in r.used if n in own)
    if clash:
        raise Unsupported('the program binds the name %s that the library piece for %s needs; rename it'
                          % (clash[0], _pretty(clash[0])))
    _drop_imports(tree, aliases, names, r.used)
    import stdlib5
    src = _source()
    if '_ail_rng' in r.used:
        src += '\n' + _random_source() + '\n_ail_rng = Random(0)\n'
    text = stdlib5.shake(src, sorted(r.used))
    return text, r.used
