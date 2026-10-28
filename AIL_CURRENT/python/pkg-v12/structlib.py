"""Library batch 24: `struct` over int.to_bytes / int.from_bytes.

`struct.pack` is variadic and `unpack` returns a tuple of mixed types, so a bundled Python module cannot be
written for it in the subset. Instead the format string is read here, at compile time, and each call becomes
calls to the small helpers in prelude_struct.py (integer, bool, char, fixed-string and pascal-string fields).
Float formats are refused by name: their IEEE-754 conversion would need a float bit-cast the compiler does not
build. A program that imports none of the module is returned as it was written, so its C does not change.
"""
import ast
import struct as _cpython
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib3
import stdlib5
from stdlib4 import Refused, refuse

HANDLED = ('pack', 'unpack', 'unpack_from', 'pack_into', 'calcsize', 'error')
NOTE = ('struct is built for literal format strings over the integer (b B h H i I l L q Q n N P), bool (?), '
        'char (c), fixed-string (s) and pascal-string (p) codes; float codes e f d are not built')
CODES = 'xcbB?hHiIlLqQnNefdspP'


def _unit(code, order):
    if code in 'sp':
        return 1
    if order == '@':
        return _cpython.calcsize('@' + code)
    return _cpython.calcsize('=' + code)


def _align(code, order):
    if order != '@' or code in 'xcbB?sp':
        return 1
    return _cpython.calcsize('@b' + code) - _cpython.calcsize('@' + code)


class Field:
    def __init__(self, code, count, unit, total, offset, order):
        self.code, self.count, self.unit, self.total = code, count, unit, total
        self.offset, self.order = offset, order
        self.signed = code in 'bhilqn'
        self.byteorder = (sys.byteorder if order in '@=' else 'little' if order == '<' else 'big')


class BadFormat(Exception):
    pass


def _format(text):
    """The fields of a format string and its size, as CPython 3.12 reads them for the native/standard modes."""
    try:
        raw = text.encode('ascii')
    except (UnicodeEncodeError, AttributeError):
        raise BadFormat('bad char in struct format')
    fmt = raw.decode('ascii')
    index = 0
    order = '@'
    if fmt[:1] in ('@', '=', '<', '>', '!'):
        order = fmt[0]
        index = 1
    offset = 0
    fields = []
    while index < len(fmt):
        if fmt[index].isspace():
            index += 1
            continue
        count = 0
        digits = False
        while index < len(fmt) and fmt[index].isdigit():
            digits = True
            count = count * 10 + int(fmt[index])
            index += 1
        if digits and index >= len(fmt):
            raise BadFormat('repeat count given without format specifier')
        if not digits:
            count = 1
        if index >= len(fmt):
            raise BadFormat('bad char in struct format')
        code = fmt[index]
        index += 1
        if code not in CODES or (code in 'nNP' and order != '@'):
            raise BadFormat('bad char in struct format')
        unit = _unit(code, order)
        total = count if code in 'sp' else count * unit
        offset = (offset + _align(code, order) - 1) // _align(code, order) * _align(code, order)
        fields.append(Field(code, count, unit, total, offset, order))
        offset += total
    return fields, offset


def _literal(node, what):
    value = getattr(node, 'value', None)
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode('ascii')
        except UnicodeDecodeError:
            refuse(node, '%s: bad char in struct format' % what)
    refuse(node, '%s needs a literal format string; write the format as a string literal' % what)


def _args(node, what, low, high=None):
    if node.keywords:
        refuse(node, '%s takes positional arguments only' % what)
    if len(node.args) < low or (high is not None and len(node.args) > high):
        if high == low:
            refuse(node, '%s takes %d arguments' % (what, low))
        refuse(node, '%s takes at least %d arguments' % (what, low))
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            refuse(node, '%s with *arguments is not built' % what)
    return node.args


def _simple(node, what):
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Constant, ast.Slice)):
        return
    refuse(node, '%s needs the buffer in a name or a simple expression; assign it to a name first' % what)


def _call(name, args):
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[])


def _pad(size):
    return _call('_ail_struct_pad', [ast.Constant(size)])


def _join(parts):
    return _call('_ail_struct_join', [ast.List(elts=parts, ctx=ast.Load())])


def _bounds(unit, signed):
    if unit >= 8:
        if signed and unit == 8:
            return -(1 << 63), (1 << 63) - 1
        return 0, 0
    bits = 8 * unit
    if signed:
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def _format_at(node, what, arg):
    try:
        return _format(_literal(arg, what))
    except BadFormat as exc:
        refuse(node, '%s: %s; %s' % (what, exc, NOTE))


def _leftovers(tree, binder):
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute) and isinstance(each.value, ast.Name) and each.value.id in binder.aliases:
            if each.attr == 'error':
                refuse(each, 'struct.error is built only as the type of an except clause: struct.error is '
                             'spelt ValueError there; %s' % NOTE)
            refuse(each, 'struct.%s is not built: %s' % (each.attr, NOTE))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in binder.names:
            if binder.names[each.id] == 'error':
                refuse(each, 'struct.error is built only as the type of an except clause: struct.error is '
                             'spelt ValueError there; %s' % NOTE)
            refuse(each, 'struct.%s is not built: %s' % (binder.names[each.id], NOTE))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in binder.aliases:
            refuse(each, 'struct used as a value is not built: %s' % NOTE)


def _pack_data(fields, values, what, node):
    parts = []
    index = 0
    at = 0
    for field in fields:
        if field.code in 'efd':
            refuse(node, '%s: float format \'%s\' is not built; %s' % (what, field.code, NOTE))
        if field.offset > at:
            parts.append(_pad(field.offset - at))
        at = field.offset
        if field.code == 'x':
            if field.total:
                parts.append(_pad(field.total))
            at += field.total
            continue
        if field.code in 'sp':
            if field.code == 'p' and field.total == 0:
                refuse(node, "%s: a '0p' pascal-string field has no room for its length byte (CPython "
                             "raises SystemError); give the field at least one byte" % what)
            if index >= len(values):
                refuse(node, '%s: format requires more arguments' % what)
            parts.append(_call('_ail_struct_pack_' + field.code,
                               [values[index], ast.Constant(field.total)]))
            index += 1
            at += field.total
            continue
        for _ in range(field.count):
            if index >= len(values):
                refuse(node, '%s: format requires more arguments' % what)
            value = values[index]
            index += 1
            if field.code == '?':
                parts.append(_call('_ail_struct_pack_bool', [value]))
            elif field.code == 'c':
                parts.append(_call('_ail_struct_pack_char', [value]))
            else:
                low, high = _bounds(field.unit, field.signed)
                parts.append(_call('_ail_struct_pack_int',
                                   [value, ast.Constant(field.unit), ast.Constant(field.signed),
                                    ast.Constant(field.byteorder), ast.Constant(low), ast.Constant(high),
                                    ast.Constant(field.code)]))
            at += field.unit
    if index != len(values):
        refuse(node, '%s: too many arguments for the format' % what)
    if not parts:
        return ast.Constant(b'')
    return _join(parts)


def _offset(base, add):
    if add == 0:
        return base
    if isinstance(base, ast.Constant) and base.value == 0:
        return ast.Constant(add)
    return ast.BinOp(left=base, op=ast.Add(), right=ast.Constant(add))


def _unpack_tuple(fields, total, buffer, base, exact, what, node):
    parts = []
    for field in fields:
        if field.code in 'efd':
            refuse(node, '%s: float format \'%s\' is not built; %s' % (what, field.code, NOTE))
        if field.code == 'x':
            continue
        if field.code in 'sp':
            if field.code == 'p' and field.total == 0:
                refuse(node, "%s: a '0p' pascal-string field has no room for its length byte (CPython "
                             "raises SystemError); give the field at least one byte" % what)
            parts.append(_call('_ail_struct_unpack_' + field.code,
                               [buffer, _offset(base, field.offset), ast.Constant(field.total),
                                base, ast.Constant(total), ast.Constant(exact)]))
            continue
        for index in range(field.count):
            offset = _offset(base, field.offset + index * field.unit)
            if field.code == '?':
                parts.append(_call('_ail_struct_unpack_bool',
                                   [buffer, offset, base, ast.Constant(total), ast.Constant(exact)]))
            elif field.code == 'c':
                parts.append(_call('_ail_struct_unpack_char',
                                   [buffer, offset, base, ast.Constant(total), ast.Constant(exact)]))
            else:
                parts.append(_call('_ail_struct_unpack_int',
                                   [buffer, offset, ast.Constant(field.unit), ast.Constant(field.signed),
                                    ast.Constant(field.byteorder), base, ast.Constant(total),
                                    ast.Constant(exact)]))
    if not parts:
        refuse(node, '%s of a format with no values is not built' % what)
    return ast.Tuple(elts=parts, ctx=ast.Load())


class Lib(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder

    def _name(self, node):
        return self.binder.attr(node)

    def _is_error(self, node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and \
                node.value.id in self.binder.aliases and node.attr == 'error':
            return True
        return isinstance(node, ast.Name) and self.binder.names.get(node.id) == 'error'

    def _error_type(self, node):
        if self._is_error(node):
            return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        if isinstance(node, ast.Tuple):
            return ast.Tuple(elts=[self._error_type(each) for each in node.elts], ctx=node.ctx)
        return node

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if node.type is not None:
            node.type = self._error_type(node.type)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        name = self._name(node.func)
        if name is None:
            return node
        what = 'struct.' + name
        if name == 'calcsize':
            args = _args(node, what, 1, 1)
            fields, size = _format_at(node, what, args[0])
            return ast.copy_location(ast.Constant(size), node)
        if name == 'pack':
            args = _args(node, what, 1)
            fields, _ = _format_at(node, what, args[0])
            return ast.copy_location(_pack_data(fields, args[1:], what, node), node)
        if name == 'pack_into':
            args = _args(node, what, 3)
            fields, _ = _format_at(node, what, args[0])
            data = _pack_data(fields, args[3:], what, node)
            return ast.copy_location(_call('_ail_struct_pack_into', [args[1], args[2], data]), node)
        if name == 'unpack':
            args = _args(node, what, 2, 2)
            fields, size = _format_at(node, what, args[0])
            _simple(args[1], what)
            return ast.copy_location(_unpack_tuple(fields, size, args[1], ast.Constant(0), True, what, node), node)
        if name == 'unpack_from':
            args = _args(node, what, 2, 3)
            fields, size = _format_at(node, what, args[0])
            _simple(args[1], what)
            base = args[2] if len(args) == 3 else ast.Constant(0)
            _simple(base, what)
            return ast.copy_location(_unpack_tuple(fields, size, args[1], base, False, what, node), node)
        refuse(node, '%s is not built: %s' % (what, NOTE))


def _helpers(tree):
    text = stdlib5.prelude('struct')
    module = ast.parse(text)
    index = 0
    while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
            isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
        index += 1
    tree.body[index:index] = module.body


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return source
    binder = stdlib5.peek_imports(tree, 'struct')
    if not binder:
        return source
    try:
        binder = stdlib5.take_imports(tree, 'struct', HANDLED, whole=True, unknown=NOTE)
        for alias in sorted(binder.aliases) + sorted(binder.names):
            if stdlib3.binds(tree, alias):
                refuse(tree.body[0] if tree.body else tree,
                       '%s is also bound by the program itself; rename it (the name stands for an imported '
                       'module here)' % alias)
        Lib(binder).visit(tree)
        _leftovers(tree, binder)
        _helpers(tree)
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except BadFormat as exc:
        if notes is not None:
            notes.append((1, 'struct: %s; %s' % (exc, NOTE)))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return text.rstrip('\n') + '\n'
