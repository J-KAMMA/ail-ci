"""Standard-library imports that real programs use most and the compiler used to refuse: `decimal`,
`unicodedata`, `ipaddress`, `html` (and `textwrap.shorten`, `heapq.merge`, `itertools.tee`-free helpers are not
here: see the census in the pull request).

One entry point, `run(tree, text, mods)`, called from stdlib5.rewrite_text. Every use is either lowered onto an
ordinary Python-source prelude (prelude_*.py: plain Python in the subset the general path builds, and importable by
CPython, which is how the tests compare it with the real module) or refused here by name, as
`module.name is not supported; write instead: ...` with the line of the use. A refusal leaves the program as written
(stdlib5 returns the source and the `note:` line), and the import the compiler then meets is reported by that note.

* decimal: `Decimal` (str, int, float, tuple, Decimal arguments; + - * / // % divmod ** with an integer exponent,
  unary operators, comparisons with int / float / Decimal, quantize, sqrt, normalize, to_integral*, max / min,
  round / int / float / format / str / repr / hash, the is_* tests), `getcontext` / `setcontext` / `localcontext`
  with prec, rounding, Emin, Emax and capitals, `Context(...)`, the eight ROUND_* modes and the exceptions.
  Not built, refused by name: the traps and flags of a context, `clamp`, BasicContext / ExtendedContext /
  DefaultContext, as_tuple, ln / exp / log10 / logb, fma, scaleb, rotate, shift, the logical_* and next_* methods,
  three-argument pow, a non-integer exponent (`Decimal ** Decimal("0.5")`).
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib5
from stdlib4 import refuse

DEC_CONSTS = ('ROUND_UP', 'ROUND_DOWN', 'ROUND_CEILING', 'ROUND_FLOOR', 'ROUND_HALF_UP', 'ROUND_HALF_DOWN',
              'ROUND_HALF_EVEN', 'ROUND_05UP', 'MAX_PREC', 'MAX_EMAX', 'MIN_EMIN', 'MIN_ETINY')
DEC_EXC = ('DecimalException', 'InvalidOperation', 'ConversionSyntax', 'DivisionImpossible', 'DivisionUndefined',
           'InvalidContext', 'DivisionByZero', 'Overflow', 'Inexact', 'Rounded', 'Subnormal', 'Underflow', 'Clamped',
           'FloatOperation')
DEC_NAMES = frozenset(('Decimal', 'Context', 'getcontext', 'setcontext', 'localcontext') + DEC_CONSTS + DEC_EXC)
# every top-level name the prelude defines that a program must not bind itself
DEC_TOP = DEC_NAMES
CTX_ATTRS = ('prec', 'rounding', 'Emin', 'Emax', 'capitals')
# zero-argument method calls only Decimal has; attribute names only a context has
DEC_METHODS0 = ('as_tuple', 'exp', 'ln', 'log10', 'logb', 'canonical', 'is_canonical', 'number_class')
DEC_METHODS = ('compare_signal', 'compare_total', 'compare_total_mag', 'fma', 'logical_and', 'logical_invert',
               'logical_or', 'logical_xor', 'max_mag', 'min_mag', 'next_minus', 'next_plus', 'next_toward',
               'remainder_near', 'rotate', 'scaleb', 'shift')
DEC_CTX_ATTRS = ('traps', 'flags', 'clear_flags', 'clear_traps', 'clamp')
DEC_WRITE = {
    'traps': 'catch the exception (try / except InvalidOperation, DivisionByZero, Overflow) or test the operands first',
    'flags': 'compare the result with the value you expect; the status flags of a context are not kept',
    'clear_flags': 'drop the call; the status flags of a context are not kept',
    'clear_traps': 'catch the exception instead of switching the traps off',
    'clamp': 'leave clamp at its default 0',
}


def names_bound(tree):
    """The names a program binds at its top level, and every attribute / method name it defines itself."""
    top = set()
    attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            attrs.add(node.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            attrs.add(node.attr)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            attrs.add(node.target.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for each in ast.walk(target):
                    if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
                        attrs.add(each.id)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            top.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for each in ast.walk(target):
                    if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
                        top.add(each.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            top.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                top.add((alias.asname or alias.name).split('.')[0])
    return top, attrs


def call_name(node):
    return node.id if isinstance(node, ast.Name) else None


def run(tree, text, mods):
    if 'decimal' in mods:
        run_decimal(tree, text)
    if 'unicodedata' in mods:
        run_unicodedata(tree, text)
    if 'ipaddress' in mods:
        run_ipaddress(tree, text)
    if 'html' in mods:
        run_html(tree, text)


# ---------------------------------------------------------------------------------------------------------------
# decimal
# ---------------------------------------------------------------------------------------------------------------
def run_decimal(tree, text):
    check_from_imports(tree, 'decimal', DEC_NAMES, lambda name: 'Decimal, Context(prec=N, rounding=ROUND_HALF_EVEN), '
                       'getcontext(), localcontext() and the ROUND_* modes are built; BasicContext / ExtendedContext / '
                       'DefaultContext are not')
    refuse_module_values(tree, stdlib5.peek_imports(tree, 'decimal'), 'decimal')
    b = stdlib5.take_imports(tree, 'decimal', DEC_NAMES)
    if not b:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in b.aliases and not isinstance(node.ctx, ast.Load):
            refuse(node, 'decimal.%s is not supported; write instead: do not rebind the module name' % node.id)
    top, attrs = names_bound(tree)
    for clash in sorted(top & DEC_TOP):
        refuse(b.first, 'the program binds the name %s itself and also uses decimal; write instead: rename your %s' % (clash, clash))
    used = set()

    def fix(node):
        found = b.attr(node)
        if found is not None:
            if found == 'Decimal' or found in DEC_NAMES:
                used.add(found)
                return stdlib5.name(found)
            refuse(node, 'decimal.%s is not supported; write instead: Decimal, Context(prec=N, rounding=...), '
                         'getcontext(), localcontext()' % found)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and b.attr(node.func.value) == 'Decimal':
            if node.func.attr == 'from_float' and len(node.args) == 1 and not node.keywords:
                used.add('_ail_dec_from_float_fn')
                return stdlib5.call(stdlib5.name('_ail_dec_from_float_fn'), [stdlib5.Replace(fix).visit(node.args[0])])
            refuse(node, 'decimal.Decimal.%s is not supported; write instead: Decimal(x) (a str, an int, a float or a '
                         'Decimal), Decimal.from_float(x)' % node.func.attr)
        return None
    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    for local in [k for k, v in b.names.items() if k == v]:
        del b.names[local]                       # the name is now the class / function of the prelude itself
    stdlib5.leftover(tree, b, 'use the names Decimal, Context, getcontext, setcontext, localcontext, ROUND_* and the exceptions')
    b.names.clear()
    b.aliases.clear()
    ctx_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and is_ctx_call(node.value):
            ctx_names.add(node.targets[0].id)
        elif isinstance(node, ast.withitem) and isinstance(node.optional_vars, ast.Name) and is_ctx_call(node.context_expr):
            ctx_names.add(node.optional_vars.id)

    def is_ctx(obj):
        return is_ctx_call(obj) or (isinstance(obj, ast.Name) and obj.id in ctx_names)

    # attribute names / calls that are not built
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in DEC_CTX_ATTRS and (node.attr not in attrs or is_ctx(node.value)):
                refuse(node, 'decimal.Context.%s is not supported; write instead: %s' % (node.attr, DEC_WRITE[node.attr]))
            if node.attr in DEC_METHODS and node.attr not in attrs:
                refuse(node, 'decimal.Decimal.%s is not supported; write instead: compute it with + - * / // %% ** (integer '
                             'exponent), quantize and comparisons' % node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in DEC_METHODS0 and not node.args and not node.keywords and node.func.attr not in attrs \
                    and not (isinstance(node.func.value, ast.Name) and node.func.value.id in ('math', 'np', 'numpy')):
                refuse(node, 'decimal.Decimal.%s is not supported; write instead: sqrt() is built, ln / exp / log10 / as_tuple '
                             'are not: use math.log / math.exp on float(d), or str(d) and split the digits' % node.func.attr)
        if isinstance(node, ast.keyword) and node.arg in ('traps', 'flags', 'clamp'):
            refuse(node.value, 'decimal.Context(%s=...) is not supported; write instead: %s' % (node.arg, DEC_WRITE[node.arg]))
        if isinstance(node, ast.Call) and call_name(node.func) == 'pow' and len(node.args) == 3:
            refuse(node, 'decimal.Decimal three-argument pow is not supported; write instead: '
                         'Decimal ** n % m with plain operators')
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            right = node.right
            if isinstance(right, ast.Constant) and isinstance(right.value, float):
                refuse(node, 'decimal.Decimal ** float is not supported (CPython raises TypeError; a Decimal exponent that is not '
                             'an integer is not built); write instead: Decimal ** n with an int n')
            if isinstance(right, ast.Call) and call_name(right.func) == 'Decimal' and len(right.args) == 1 \
                    and isinstance(right.args[0], ast.Constant) and isinstance(right.args[0].value, str) \
                    and not text_is_integer(right.args[0].value):
                refuse(node, 'decimal.Decimal ** Decimal(%r) with a non-integer exponent is not supported; write instead: '
                             'an integer exponent, or math.sqrt / math.pow on floats' % right.args[0].value)
    # the exceptions: `except DecimalException` also catches DivisionByZero (a ZeroDivisionError here)
    if True:
        both = (stdlib5.name('DecimalException'), stdlib5.name('DivisionByZero'))

        def widen(elt):
            if isinstance(elt, ast.Name) and elt.id == 'DecimalException':
                used.add('DivisionByZero')
                return list(both)
            return [elt]
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                if isinstance(node.type, ast.Name):
                    new = widen(node.type)
                    if len(new) > 1:
                        node.type = ast.Tuple(elts=new, ctx=ast.Load())
                elif isinstance(node.type, ast.Tuple):
                    elts = []
                    for elt in node.type.elts:
                        elts.extend(widen(elt))
                    node.type.elts = elts
            elif isinstance(node, ast.Call) and call_name(node.func) == 'isinstance' and len(node.args) == 2:
                second = node.args[1]
                if isinstance(second, ast.Name):
                    new = widen(second)
                    if len(new) > 1:
                        node.args[1] = ast.Tuple(elts=new, ctx=ast.Load())
                elif isinstance(second, ast.Tuple):
                    elts = []
                    for elt in second.elts:
                        elts.extend(widen(elt))
                    second.elts = elts
    # `ctx.prec = 5` and friends are checked by the C module: route them through the checking function
    class SetAttr(ast.NodeTransformer):
        def visit_Assign(self, node):
            self.generic_visit(node)
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute) \
                    and node.targets[0].attr in CTX_ATTRS and is_ctx(node.targets[0].value):
                used.add('_ail_dec_set')
                return ast.copy_location(ast.Expr(value=stdlib5.call(stdlib5.name('_ail_dec_set'), [
                    node.targets[0].value, ast.Constant(value=node.targets[0].attr), node.value])), node)
            return node

        def visit_AugAssign(self, node):
            self.generic_visit(node)
            if isinstance(node.target, ast.Attribute) and node.target.attr in CTX_ATTRS and is_ctx(node.target.value):
                used.add('_ail_dec_set')
                current = ast.Attribute(value=node.target.value, attr=node.target.attr, ctx=ast.Load())
                return ast.copy_location(ast.Expr(value=stdlib5.call(stdlib5.name('_ail_dec_set'), [
                    node.target.value, ast.Constant(value=node.target.attr),
                    ast.BinOp(left=current, op=node.op, right=node.value)])), node)
            return node
    tree.body = [SetAttr().visit(stmt) for stmt in tree.body]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in ('Decimal', 'Context'):
                    refuse(node, 'decimal: a subclass of %s is not supported; write instead: a class that holds a Decimal in a '
                                 'field and forwards the operations you use' % base.id)
    for module in ('statistics',):
        # the compiled statistics runtime reads its values as int / float / Fraction: a Decimal would stop it with its own
        # TypeError, where CPython computes a Decimal result
        sb = stdlib5.peek_imports(tree, module)
        if sb:
            for node in ast.walk(tree):
                if sb.attr(node) is not None:
                    refuse(node, 'decimal with statistics.%s is not supported; write instead: sum(xs, Decimal(0)) / len(xs) '
                                 'for a mean, and sorted(xs) indexed in the middle for a median' % sb.attr(node))
    extra = []
    lower_math_calls(tree, used, extra)
    ast.fix_missing_locations(tree)
    roots = set(used)
    if not roots:
        roots.add('Decimal')
    stdlib5.add_once(text, stdlib5.shake(prune_decimal(stdlib5.prelude('decimal'), tree, text), roots))
    for chunk in extra:
        stdlib5.add_once(text, chunk)
    # Fraction(Decimal(...)) when the program also uses fractions: the Fraction class takes the exact ratio
    for index, chunk in enumerate(text):
        if 'class Fraction' in chunk and 'class Decimal' in ''.join(text):
            old = ('            else:\n                raise TypeError("argument should be a string or a Rational instance")')
            new = ('            elif isinstance(numerator, Decimal):\n'
                   '                parts = numerator.as_integer_ratio()\n'
                   '                n = parts[0]\n'
                   '                d = parts[1]\n' + old)
            text[index] = chunk.replace(old, new, 1)


# the methods of Decimal that cost much code and that a program often does not use: the group a method is in
DEC_GROUPS = {'pow': ('__pow__', '__rpow__'), 'format': ('__format__',),
              'divide': ('__floordiv__', '__rfloordiv__', '__mod__', '__rmod__', '__divmod__', '__rdivmod__')}
DEC_ALWAYS = frozenset(('__init__', '__repr__', '__str__', '__bool__', '__hash__', '__neg__', '__pos__', '__abs__', '__float__',
                        '__int__', '__eq__', '__lt__', '__le__', '__gt__', '__ge__', '__add__', '__radd__', '__sub__',
                        '__rsub__', '__mul__', '__rmul__', '__truediv__', '__rtruediv__', '__trunc__'))


def prune_decimal(source, tree, text):
    """The prelude without the Decimal methods the program cannot reach: operator methods by the operators the
    program writes, the format hook by a format spec, the named methods by their name. A program that imports
    `operator` (or text that needs the whole class: Fraction(Decimal)) keeps everything."""
    mods = stdlib5.imported_modules(tree)
    if 'operator' in mods or any('class Fraction' in chunk for chunk in text):
        return source
    attrs = set()
    ops = set()
    spec = False
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attrs.add(node.attr)
            if node.attr in ('format', 'format_map'):
                spec = True
        elif isinstance(node, (ast.BinOp, ast.AugAssign)):
            ops.add(type(node.op))
        elif isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            spec = True
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    keep_group = {'pow': ast.Pow in ops or 'pow' in calls,
                  'format': spec or 'format' in calls,
                  'divide': bool(ops & {ast.Mod, ast.FloorDiv}) or 'divmod' in calls}
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Decimal':
            body = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    name = item.name
                    group = next((g for g, names in DEC_GROUPS.items() if name in names), None)
                    if group is not None:
                        if not keep_group[group]:
                            continue
                    elif name not in DEC_ALWAYS and not name.startswith('__') and name not in attrs:
                        continue
                    elif name in ('__round__', '__floor__', '__ceil__') and not (
                            name == '__round__' and 'round' in calls
                            or name == '__floor__' and bool({'floor', '_ail_dec_floor'} & (attrs | calls))
                            or name == '__ceil__' and bool({'ceil', '_ail_dec_ceil'} & (attrs | calls))):
                        continue
                body.append(item)
            node.body = body
    return ast.unparse(module) + '\n'


# math functions that take their arguments through float(): CPython converts a Decimal; the compiled math runtime does
# not for every one of them (log10, pow, isnan, ... read the object as a number), so the arguments are converted here
MATH_FLOATS = frozenset(('sqrt', 'exp', 'expm1', 'log', 'log2', 'log10', 'log1p', 'pow', 'sin', 'cos', 'tan', 'asin', 'acos',
                         'atan', 'atan2', 'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh', 'hypot', 'fabs', 'fmod', 'copysign',
                         'degrees', 'radians', 'isnan', 'isinf', 'isfinite', 'isclose', 'erf', 'erfc', 'gamma', 'lgamma', 'cbrt',
                         'exp2', 'remainder', 'ldexp', 'frexp', 'modf', 'nextafter', 'ulp'))


def lower_math_calls(tree, used, extra):
    """math.floor / math.ceil of a Decimal use its __floor__ / __ceil__ (the compiled math runtime floors with `//`, which
    truncates a Decimal), and the float functions of math get float(Decimal) for a Decimal argument."""
    mb = stdlib5.peek_imports(tree, 'math')
    if not mb:
        return
    helpers = {}

    class Calls(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            found = mb.attr(node.func)
            if found is None:
                return node
            if found in ('floor', 'ceil') and len(node.args) == 1 and not node.keywords:
                name = '_ail_dec_' + found
                helpers[name] = (found, ast.unparse(node.func))
                return ast.copy_location(stdlib5.call(stdlib5.name(name), node.args), node)
            if found in MATH_FLOATS and not any(isinstance(arg, ast.Starred) for arg in node.args):
                used.add('_ail_dec_num')
                node.args = [stdlib5.call(stdlib5.name('_ail_dec_num'), [arg]) for arg in node.args]
                for kw in node.keywords:
                    if kw.arg is not None:
                        kw.value = stdlib5.call(stdlib5.name('_ail_dec_num'), [kw.value])
            return node
    tree.body = [Calls().visit(stmt) for stmt in tree.body]
    for name, (found, original) in sorted(helpers.items()):
        extra.append('def %s(x):\n    if isinstance(x, Decimal):\n        return x.__%s__()\n    return %s(x)\n' % (name, found, original))


def is_ctx_call(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
        'getcontext', 'Context', 'localcontext')


def text_is_integer(s):
    try:
        import decimal
        d = decimal.Decimal(s)
        return d.is_finite() and d == d.to_integral_value()
    except Exception:
        return True


# ---------------------------------------------------------------------------------------------------------------
# unicodedata, ipaddress, html: a few names each, lowered the same way
# ---------------------------------------------------------------------------------------------------------------
def check_from_imports(tree, module, handled, hint):
    """`from module import name` for a name that is not built is refused by name, with what to write instead."""
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == module:
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, '%s: from %s import * is not supported; write instead: name what you use' % (module, module))
                if alias.name not in handled:
                    refuse(node, '%s.%s is not supported; write instead: %s' % (module, alias.name, hint(alias.name)))


def refuse_module_values(tree, binder, module):
    """`m = decimal` / `f(decimal)`: the module used as a value, not through an attribute."""
    under_attribute = {id(each.value) for each in ast.walk(tree) if isinstance(each, ast.Attribute)}
    for each in ast.walk(tree):
        if isinstance(each, ast.Name) and each.id in binder.aliases and id(each) not in under_attribute:
            refuse(each, '%s used as a value is not supported; write instead: name what you use (%s.name)' % (module, module))


def lower_module(tree, text, module, handled, hint, prelude_name, prelude_roots, constants=None, forbidden_attrs=None):
    """Lower the names of `module` the program uses: `handled` maps a module attribute to the name of the prelude
    function / class that stands for it, `constants` maps an attribute to a constant value. The prelude chunk is
    added once, shaken to the names reached from `prelude_roots`."""
    constants = constants or {}
    everything = set(handled) | set(constants)
    check_from_imports(tree, module, everything, hint)
    b = stdlib5.peek_imports(tree, module)
    refuse_module_values(tree, b, module)
    b = stdlib5.take_imports(tree, module, everything)
    if not b:
        return
    top, attrs = names_bound(tree)
    used = set()
    for clash in sorted(top & (set(handled.values()) | set(prelude_roots))):
        refuse(b.first, 'the program binds the name %s itself and also uses %s; write instead: rename your %s'
               % (clash, module, clash))

    def fix(node):
        found = b.attr(node)
        if found is None:
            return None
        if found in constants:
            return ast.Constant(value=constants[found])
        if found in handled:
            used.add(handled[found])
            return stdlib5.name(handled[found])
        refuse(node, '%s.%s is not supported; write instead: %s' % (module, found, hint(found)))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if b.attr(base) in ('IPv4Address', 'AddressValueError') and module == 'ipaddress' and b.attr(base) == 'IPv4Address':
                    refuse(node, 'ipaddress: a subclass of IPv4Address is not supported; write instead: a class that holds the '
                                 'address in a field')
    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    for local in [k for k, v in b.names.items() if handled.get(v) == k]:
        del b.names[local]
    stdlib5.leftover(tree, b, 'use %s' % ', '.join(sorted(everything)))
    b.names.clear()
    b.aliases.clear()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and forbidden_attrs and node.attr in forbidden_attrs and node.attr not in attrs:
            refuse(node, '%s.%s is not supported; write instead: %s' % (module, node.attr, forbidden_attrs[node.attr]))
    ast.fix_missing_locations(tree)
    stdlib5.add_once(text, stdlib5.shake(stdlib5.prelude(prelude_name), used | set(prelude_roots)))


UD_HINT = ('use the str methods (isalpha, isdigit, isspace, isupper, islower, isalnum, isprintable), ord() / chr(), '
           'or unicodedata.category(ch), which is built')


def run_unicodedata(tree, text):
    lower_module(tree, text, 'unicodedata', {'category': '_ail_ud_category'}, lambda name: UD_HINT, 'unicodedata', (),
                 constants={'unidata_version': '15.0.0'})


IP_HINTS = {
    'ip_address': 'ipaddress.IPv4Address(text), which is built for IPv4 addresses',
    'ip_network': 'int(IPv4Address(a)) with shifts and masks: (int(ip) & mask) == (int(net) & mask)',
    'ip_interface': 'int(IPv4Address(a)) with shifts and masks',
    'IPv4Network': 'int(IPv4Address(a)) with shifts and masks: (int(ip) & mask) == (int(net) & mask)',
    'IPv4Interface': 'IPv4Address(text.split("/")[0]) and the prefix length as an int',
    'IPv6Address': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
    'IPv6Network': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
    'IPv6Interface': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
    'NetmaskValueError': 'ValueError, which AddressValueError also is',
    'collapse_addresses': 'sort the int(IPv4Address(a)) values and merge the ranges by hand',
    'summarize_address_range': 'loop over int(IPv4Address(a)) values',
}
IP_ATTRS = {
    'is_private': 'int(ip) with the ranges you mean (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16); the lists of '
                  'is_private / is_global differ between 3.12 patch releases',
    'is_global': 'int(ip) with the ranges you mean; the lists of is_private / is_global differ between 3.12 patch releases',
    'ipv4_mapped': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
    'ipv6_mapped': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
    'is_site_local': 'ipaddress.IPv4Address for IPv4 addresses; IPv6 is not built',
}


def run_ipaddress(tree, text):
    lower_module(tree, text, 'ipaddress', {'IPv4Address': 'IPv4Address', 'AddressValueError': 'AddressValueError'},
                 lambda name: IP_HINTS.get(name, 'ipaddress.IPv4Address(text)'), 'ipaddress', ('IPv4Address',),
                 forbidden_attrs=IP_ATTRS)


HTML_HINTS = {
    'unescape': 'str.replace for the few entities you need (&lt; &gt; &quot; and &amp; last), which is exact for those',
}


def run_html(tree, text):
    b = stdlib5.peek_imports(tree, 'html')
    roots = []

    class Calls(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if b.attr(node.func) != 'escape':
                return node
            if any(isinstance(arg, ast.Starred) for arg in node.args) or any(kw.arg is None for kw in node.keywords):
                refuse(node, 'html.escape(*args / **kwargs) is not supported; write instead: html.escape(s, quote=True)')
            for kw in node.keywords:
                if kw.arg != 'quote':
                    refuse(node, 'html.escape(%s=...) is not supported; write instead: html.escape(s, quote=True)' % kw.arg)
            given = list(node.args) + [kw.value for kw in node.keywords]
            if len(given) == 2 and len(node.keywords) <= 1 and not (node.keywords and len(node.args) == 2):
                roots.append('_ail_html_escape_q')
                return ast.copy_location(stdlib5.call(stdlib5.name('_ail_html_escape_q'), given), node)
            if len(given) != 1 or node.keywords:
                refuse(node, 'html.escape with %d arguments is not supported; write instead: html.escape(s, quote=True)'
                       % len(given))
            return node
    if b:
        tree.body = [Calls().visit(stmt) for stmt in tree.body]
    lower_module(tree, text, 'html', {'escape': '_ail_html_escape'},
                 lambda name: HTML_HINTS.get(name, 'html.escape(s, quote=True), which is built, or str.replace'), 'html',
                 tuple(roots))
