"""Library batch: `struct` (pack / unpack / unpack_from / calcsize) lowered onto bytes.

`rewrite_text(source, notes)` runs from ail_syntax.python_surface on the program text.  A format is
parsed here, at compile time, with the host's own `struct.calcsize`, so offsets, native alignment and
the standard/native sizes match CPython 3.12 exactly; a literal format then becomes nested calls to
the helpers in prelude_struct.py (pack) or a tuple of helper calls (unpack / unpack_from).  A program
that imports none of the module is returned as written.  Every use this does not build is refused here
by name (a note naming the use), and the import the compiler then meets is reported by it:

* a format that is not a string literal (the format cannot be checked at compile time);
* a float format ('e', 'f', 'd') and the 'p' Pascal-string format;
* a call with a starred argument, `struct.error` used as a value, and every other name of the module;
* `pack` with the wrong number of values, `unpack` of a format with no values, and `unpack_from` with
  more than one offset.

`struct.error` is the prelude's own class; an `except struct.error` clause names it.
"""
import ast
import hashlib
import struct as _struct

import stdlib5

HANDLED = {'pack', 'unpack', 'unpack_from', 'calcsize', 'error'}
SIGNED = 'bhilqn'
UNSIGNED = 'BHILQNP'
SCALAR = SIGNED + UNSIGNED


class Elem:
    __slots__ = ('code', 'size', 'offset', 'total')

    def __init__(self, code, size, offset):
        self.code, self.size, self.offset = code, size, offset


def _literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def parse_format(fmt, node):
    """(elements, total bytes, big-endian) for the literal format `fmt`, or a named refusal."""
    try:
        total = _struct.calcsize(fmt)
    except _struct.error:
        stdlib5.refuse(node, 'struct: bad char in struct format %r' % fmt)
    prefix = fmt[0] if fmt[:1] in ('@', '=', '<', '>', '!') else '@'
    native = prefix == '@'
    big = prefix in ('>', '!')
    i = 1 if fmt[:1] in ('@', '=', '<', '>', '!') else 0
    elems = []
    while i < len(fmt):
        start = i
        while i < len(fmt) and fmt[i].isdigit():
            i += 1
        if i >= len(fmt):
            stdlib5.refuse(node, 'struct: bad char in struct format %r' % fmt)
        code = fmt[i]
        i += 1
        count = int(fmt[start:i - 1]) if i - 1 > start else 1
        if code in 'efd':
            stdlib5.refuse(node, "struct: the float format %r is not built; only the integer, '?', 'c', "
                                 "'s' and 'x' formats are" % code)
        if code == 'p':
            stdlib5.refuse(node, "struct: the 'p' (Pascal string) format is not built; use 's'")
        if code in 'nNP' and not native:
            stdlib5.refuse(node, "struct: %r is only valid in the native ('@') byte order" % code)
        try:
            before = _struct.calcsize(fmt[:start])
            after = _struct.calcsize(fmt[:i])
        except _struct.error:
            stdlib5.refuse(node, 'struct: bad char in struct format %r' % fmt)
        if code == 'x':
            if count:
                elems.append(Elem(code, count, before))
            continue
        if code == 's':
            elems.append(Elem(code, count, before))
            continue
        unit = _struct.calcsize(prefix + '1' + code)
        pad = (after - before) - count * unit
        offset = before + pad
        for _ in range(count):
            elems.append(Elem(code, unit, offset))
            offset += unit
    return elems, total, big


def _range(code, size):
    """(low, high actually checked, message high) for pack, as CPython spells its error."""
    if code in SIGNED:
        low, high = -(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1
        return low, high, high
    text_high = (1 << (8 * size)) - 1
    return 0, min(text_high, 9223372036854775807), text_high


def _name(identifier):
    return ast.Name(id=identifier, ctx=ast.Load())


def _const(value):
    return ast.Constant(value=value)


def _call(func, args):
    return ast.Call(func=_name(func), args=list(args), keywords=[])


def _value_type(elem):
    if elem.code in SCALAR:
        return 'int'
    if elem.code == '?':
        return 'bool'
    return 'bytes'


def _helper_name(tag, counter):
    counter[0] += 1
    return '_ail_struct_%s_%d' % (tag, counter[0])


def _add_helper(helpers, name, params, returns, body):
    """A generated function with typed parameters: the arguments are evaluated once, at the call
    site and in CPython's order, before any range check or buffer check runs."""
    arguments = ast.arguments(posonlyargs=[], args=[ast.arg(arg=each, annotation=_name(kind))
                                                    for each, kind in params],
                              vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    fn = ast.FunctionDef(name=name, args=arguments, body=[ast.Return(value=body)],
                         decorator_list=[], returns=ast.parse(returns, mode='eval').body)
    ast.fix_missing_locations(fn)
    helpers.append(ast.unparse(fn))


def _pack_chain(node, fmt, elems, total, big, values):
    expr = _const(b'')
    position = 0
    value = 0
    for elem in elems:
        gap = elem.offset - position
        if gap < 0:
            stdlib5.refuse(node, 'struct: cannot lay out the format %r' % fmt)
        if gap:
            expr = _call('_ail_struct_zeros', [expr, _const(gap)])
        if elem.code == 'x':
            if elem.size:
                expr = _call('_ail_struct_zeros', [expr, _const(elem.size)])
            position = elem.offset + elem.size
            continue
        argument = values[value]
        value += 1
        if elem.code in SCALAR:
            if isinstance(argument, ast.Constant) and type(argument.value) is bool:
                argument = _const(int(argument.value))
            low, high, text_high = _range(elem.code, elem.size)
            message = "'%s' format requires %d <= number <= %d" % (elem.code, low, text_high)
            expr = _call('_ail_struct_num', [expr, argument, _const(elem.size), _const(elem.code in SIGNED),
                                             _const(big), _const(low), _const(high), _const(message)])
        elif elem.code == '?':
            expr = _call('_ail_struct_bool', [expr, argument])
        elif elem.code == 'c':
            expr = _call('_ail_struct_char', [expr, argument])
        else:
            expr = _call('_ail_struct_str', [expr, argument, _const(elem.size)])
        position = elem.offset + elem.size
    if position != total:
        stdlib5.refuse(node, 'struct: cannot lay out the format %r' % fmt)
    return expr


def pack_expr(node, fmt, args, helpers, tag, counter):
    elems, total, big = parse_format(fmt, node)
    if any(isinstance(a, ast.Starred) for a in args) or node.keywords:
        stdlib5.refuse(node, 'struct.pack() with a starred or keyword argument is not built; pass the '
                             'values positionally')
    values = [e for e in elems if e.code != 'x']
    if len(args) != len(values):
        stdlib5.refuse(node, 'struct.pack(): the format %r takes %d values, not %d' %
                       (fmt, len(values), len(args)))
    # '?' takes any truthy value in CPython; a bool literal in an integer slot is 0 or 1.
    nodes = []
    for elem, argument in zip(values, args):
        if elem.code in SCALAR and isinstance(argument, ast.Constant) and type(argument.value) is bool:
            argument = _const(int(argument.value))
        elif elem.code == '?':
            argument = _call('bool', [argument])
        nodes.append(argument)
    if len(values) == 1:
        return _pack_chain(node, fmt, elems, total, big, nodes)
    name = _helper_name(tag, counter)
    body = _pack_chain(node, fmt, elems, total, big, [_name('v%d' % i) for i in range(len(values))])
    _add_helper(helpers, name, [('v%d' % i, _value_type(elem)) for i, elem in enumerate(values)], 'bytes', body)
    return _call(name, nodes)


def _unpack_elements(node, elems, total, big, data, base, mode):
    elements = []
    for elem in elems:
        if elem.code == 'x':
            continue
        if elem.code in SCALAR:
            elements.append(_call('_ail_struct_get_int',
                                  [data, base, _const(elem.offset), _const(elem.size),
                                   _const(elem.code in SIGNED), _const(big), _const(total), _const(mode)]))
        elif elem.code == '?':
            elements.append(_call('_ail_struct_get_bool', [data, base, _const(elem.offset), _const(total),
                                                           _const(mode)]))
        elif elem.code == 'c':
            elements.append(_call('_ail_struct_get_char', [data, base, _const(elem.offset), _const(total),
                                                           _const(mode)]))
        else:
            elements.append(_call('_ail_struct_get_str', [data, base, _const(elem.offset), _const(elem.size),
                                                          _const(total), _const(mode)]))
    return elements


def unpack_expr(node, fmt, data, base, mode, helpers, tag, counter):
    elems, total, big = parse_format(fmt, node)
    values = [e for e in elems if e.code != 'x']
    if not values:
        stdlib5.refuse(node, 'struct: unpacking a format with no values is not built')
    for elem in values:
        if elem.size == 8 and elem.code in UNSIGNED:
            stdlib5.refuse(node, "struct: unpacking the unsigned 64-bit format %r is not built: "
                                 "a value from 2**63 to 2**64 - 1 does not fit the int subset" % elem.code)
    with_base = base is not None
    if len(values) == 1:
        return ast.Tuple(elts=_unpack_elements(node, elems, total, big, data,
                                               base if with_base else _const(0), mode), ctx=ast.Load())
    name = _helper_name(tag, counter)
    params = [('data', 'bytes')] + ([('base', 'int')] if with_base else [])
    body = ast.Tuple(elts=_unpack_elements(node, elems, total, big, _name('data'),
                                           _name('base') if with_base else _const(0), mode), ctx=ast.Load())
    _add_helper(helpers, name, params, 'tuple[' + ', '.join(_value_type(e) for e in values) + ']', body)
    return _call(name, [data, base] if with_base else [data])



def lower(node, attr, helpers, tag, counter):
    args = node.args
    if attr == 'calcsize':
        if len(args) != 1 or node.keywords or not _literal(args[0]):
            stdlib5.refuse(node, 'struct.calcsize() with a format that is not a string literal is not built')
        elems, total, _ = parse_format(args[0].value, node)
        return _const(total)
    if not args or not _literal(args[0]):
        stdlib5.refuse(node, 'struct.%s() with a format that is not a string literal is not built: the '
                             'format is checked at compile time' % attr)
    fmt = args[0].value
    if attr == 'pack':
        return pack_expr(node, fmt, args[1:], helpers, tag, counter)
    if attr == 'unpack':
        if len(args) != 2 or node.keywords:
            stdlib5.refuse(node, 'struct.unpack() takes a format and one buffer here')
        return unpack_expr(node, fmt, args[1], None, 0, helpers, tag, counter)
    if len(args) not in (2, 3) or node.keywords:
        stdlib5.refuse(node, 'struct.unpack_from() takes a format, a buffer and an optional offset here')
    base = args[2] if len(args) == 3 else None
    return unpack_expr(node, fmt, args[1], base, 1, helpers, tag, counter)


class _Lower(ast.NodeTransformer):
    """Rewrite the innermost call first: `struct.unpack(fmt, struct.pack(fmt2, x))`."""

    def __init__(self, fix):
        self.fix = fix

    def visit(self, node):
        node = self.generic_visit(node)
        if isinstance(node, ast.expr):
            new = self.fix(node)
            if new is not None:
                return ast.copy_location(new, node)
        return node


def run(tree, text, source):
    binder = stdlib5.take_imports(tree, 'struct', HANDLED,
                                  unknown='pack, unpack, unpack_from, calcsize and error are the built names')
    if not binder:
        return
    tag = hashlib.sha1(source.encode('utf-8')).hexdigest()[:10]
    helpers = []
    counter = [0]

    def fix(node):
        if isinstance(node, ast.Call):
            attr = binder.attr(node.func)
            if attr in ('pack', 'unpack', 'unpack_from', 'calcsize'):
                return lower(node, attr, helpers, tag, counter)
        if binder.attr(node) == 'error':
            return _name('_ail_struct_error')
        return None
    transform = _Lower(fix)
    tree.body = [transform.visit(stmt) for stmt in tree.body]
    stdlib5.leftover(tree, binder, 'pack / unpack / unpack_from / calcsize / error are the built names')
    text.extend(helpers)
    text.append(stdlib5.prelude('struct'))


def rewrite_text(source, notes=None):
    """The program text with struct lowered; the source as written (and `notes` filled) when a use
    is not built."""
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    from stdlib5 import imported_modules
    if 'struct' not in imported_modules(tree):
        return source
    text = []
    try:
        before = ast.dump(tree)
        run(tree, text, source)
        if ast.dump(tree) == before and not text:
            return source
        stdlib5.insert_after_imports(tree, '\n\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except stdlib5.Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use '
                             'or report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
