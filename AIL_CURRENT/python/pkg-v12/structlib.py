"""structlib.py -- `struct.pack` / `struct.unpack` / `struct.calcsize` lowered onto int.to_bytes / int.from_bytes.

A source-to-source pass in the manner of stdlib4.rewrite_text: ail_syntax.python_surface runs it on the program text
before the other source passes, so both compile paths see the lowered code and the same helper functions. A program
that imports none of the module is returned as it was written (the same string).

Supported: pack, unpack and calcsize with a string/bytes LITERAL format whose first character names the byte order
('>', '<', '!', or '=' for the native order with standard sizes). The codes are b B h H i I l L q Q (1, 2, 4, 8
byte integers with CPython's range check and message), ? (one byte, truth value), c (one byte, one bytes argument),
s (a bytes field of the repeat count) and x (padding), with a repeat count before any of them. The format is parsed
at compile time, so the field sizes and offsets are constants and every value is evaluated once, left to right.

Not built, refused by name at compile time (never a wrong result): the native-aligned '@' mode (a format with no
prefix is '@' in CPython; write '>' or '<'), the float codes e f d, the native-size codes n N P, the Pascal string
'p', a format that is not a literal, a function used as a value (pack_into, unpack_from, iter_unpack, Struct, error),
a dynamic/starred argument list, and a buffer for unpack that cannot be read twice safely (a call or comprehension:
assign it to a name first). The exception (RuntimeError here; struct.error in CPython) and the message are
CPython's, so `str(e)` matches; `except struct.error` cannot be written and is refused.

The helpers this pass appends run under CPython too (they are plain Python in the subset both paths build), which
is how the C side can be compared with CPython without the pass itself: see test_ail_stdlib2.py.
"""
import ast
import sys

import stdlib5
from stdlib4 import Refused, refuse

HANDLED = {'pack', 'unpack', 'calcsize'}
UNKNOWN = 'pack, unpack and calcsize are built'

# code -> (byte size, signed) for the standard-size integer codes
INTEGERS = {
    'b': (1, True), 'B': (1, False),
    'h': (2, True), 'H': (2, False),
    'i': (4, True), 'I': (4, False),
    'l': (4, True), 'L': (4, False),
    'q': (8, True), 'Q': (8, False),
}
FLOATS = {'e', 'f', 'd'}
NATIVE_SIZES = {'n', 'N', 'P'}
MAX_FIELDS = 65536

HELPERS = r'''
def _ail_struct_check(buf: bytes, n: int) -> bytes:
    if len(buf) != n:
        raise RuntimeError("unpack requires a buffer of " + str(n) + " bytes")
    return buf


def _ail_struct_pack_int(value: int, size: int, signed: bool, big: bool, code: str) -> bytes:
    if signed:
        if size < 8:
            lo = -(1 << (size * 8 - 1))
            hi = (1 << (size * 8 - 1)) - 1
            if value < lo or value > hi:
                raise RuntimeError("'" + code + "' format requires " + str(lo) + " <= number <= " + str(hi))
    else:
        if size < 8:
            hi = (1 << (size * 8)) - 1
            if value < 0 or value > hi:
                raise RuntimeError("'" + code + "' format requires 0 <= number <= " + str(hi))
        elif value < 0:
            raise RuntimeError("'" + code + "' format requires 0 <= number <= 18446744073709551615")
    if big:
        return value.to_bytes(size, "big", signed=signed)
    return value.to_bytes(size, "little", signed=signed)


def _ail_struct_unpack_int(buf: bytes, start: int, size: int, signed: bool, big: bool) -> int:
    part = buf[start:start + size]
    if big:
        return int.from_bytes(part, "big", signed=signed)
    return int.from_bytes(part, "little", signed=signed)


def _ail_struct_pack_s(value: bytes, n: int) -> bytes:
    if len(value) >= n:
        return value[0:n]
    return value + b"\x00" * (n - len(value))


def _ail_struct_pack_c(value: bytes) -> bytes:
    if len(value) != 1:
        raise RuntimeError("char format requires a bytes object of length 1")
    return value


def _ail_struct_pack_bool(value: int) -> bytes:
    if value:
        return (1).to_bytes(1, "big")
    return (0).to_bytes(1, "big")
'''


HELPER_NAMES = frozenset(('_ail_struct_check', '_ail_struct_pack_int', '_ail_struct_unpack_int',
                          '_ail_struct_pack_s', '_ail_struct_pack_c', '_ail_struct_pack_bool'))


def _number(value):
    return ast.Constant(value=value)


def _call(func, args):
    return ast.Call(func=ast.Name(id=func, ctx=ast.Load()), args=list(args), keywords=[])


def _format_text(node, what):
    """The literal format string of a call, or a named refusal."""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
        refuse(node, 'struct.%s: the format must be a string or bytes literal (it is parsed at compile time); '
                     'write the format where the call is' % what)
    value = node.value
    if isinstance(value, bytes):
        try:
            value = value.decode('ascii')
        except UnicodeDecodeError:
            refuse(node, 'struct.%s: the format bytes are not ASCII' % what)
    return value


def parse(fmt, node, what):
    """`(fields, total, big)` for a literal format; a named refusal for anything not built."""
    text = fmt
    if text[:1] in ('>', '<', '!', '='):
        prefix, text = text[0], text[1:]
    else:
        prefix = '@'
    if prefix == '@':
        refuse(node, 'struct.%s: format %r uses the native byte order and alignment, which is not built; '
                     "write a byte-order prefix ('>' big, '<' little, '=' native order with standard sizes)"
               % (what, fmt))
    big = (sys.byteorder == 'big') if prefix == '=' else prefix in ('>', '!')
    fields = []
    total = 0
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and text[j].isdigit():
            j += 1
        if j >= len(text):
            refuse(node, 'struct.%s: format %r: repeat count given without a format specifier' % (what, fmt))
        count = int(text[i:j]) if j > i else 1
        code = text[j]
        i = j + 1
        if count < 0:
            refuse(node, 'struct.%s: format %r: a negative repeat count' % (what, fmt))
        if total + count > MAX_FIELDS:
            refuse(node, 'struct.%s: format %r has more than %d fields, which is not built' % (what, fmt, MAX_FIELDS))
        if code in INTEGERS:
            size, signed = INTEGERS[code]
            for _ in range(count):
                fields.append(('int', size, signed, code))
                total += size
        elif code == '?':
            for _ in range(count):
                fields.append(('bool',))
                total += 1
        elif code == 'c':
            for _ in range(count):
                fields.append(('c',))
                total += 1
        elif code == 's':
            fields.append(('s', count))
            total += count
        elif code == 'x':
            if count:
                fields.append(('pad', count))
            total += count
        elif code in FLOATS:
            refuse(node, 'struct.%s: the float format %r is not built (use int/bytes codes: b B h H i I l L q Q '
                         '? c s x)' % (what, code))
        elif code in NATIVE_SIZES:
            refuse(node, 'struct.%s: the native-size format %r is not built (use the standard-size integer '
                         'codes b B h H i I l L q Q)' % (what, code))
        elif code == 'p':
            refuse(node, "struct.%s: the Pascal string format 'p' is not built (use 's')" % what)
        else:
            refuse(node, 'struct.%s: format %r: bad char in struct format' % (what, fmt))
    return fields, total, big


def _repeatable(node):
    """A buffer expression that may be read once per field without a second side effect."""
    for each in ast.walk(node):
        if isinstance(each, (ast.Call, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Await,
                             ast.Yield, ast.YieldFrom, ast.NamedExpr)):
            return False
    return True


class Lower(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.used = False

    def visit_Call(self, node):
        self.generic_visit(node)
        what = self.binder.attr(node.func)
        if what not in HANDLED:
            return node
        if any(isinstance(a, ast.Starred) for a in node.args):
            refuse(node, 'struct.%s: a starred argument is not built (the argument count is checked at compile '
                         'time)' % what)
        if node.keywords:
            refuse(node, 'struct.%s: keyword arguments are not built (CPython takes none)' % what)
        if what == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize: expected one format argument')
            fields, total, big = parse(_format_text(node.args[0], 'calcsize'), node, 'calcsize')
            return ast.copy_location(_number(total), node)
        if what == 'pack':
            if not node.args:
                refuse(node, 'struct.pack: expected a format argument')
            fields, total, big = parse(_format_text(node.args[0], 'pack'), node, 'pack')
            values = node.args[1:]
            expected = sum(1 for f in fields if f[0] != 'pad')
            if len(values) != expected:
                refuse(node, 'struct.pack: the format takes %d value(s), and the call passes %d'
                             % (expected, len(values)))
            parts = []
            index = 0
            for field in fields:
                if field[0] == 'pad':
                    parts.append(ast.BinOp(left=ast.Constant(value=b'\x00'), op=ast.Mult(),
                                           right=_number(field[1])))
                    continue
                value = values[index]
                index += 1
                if field[0] == 'int':
                    _, size, signed, code = field
                    parts.append(_call('_ail_struct_pack_int', [value, _number(size), ast.Constant(value=signed),
                                                                ast.Constant(value=big), ast.Constant(value=code)]))
                elif field[0] == 's':
                    parts.append(_call('_ail_struct_pack_s', [value, _number(field[1])]))
                elif field[0] == 'c':
                    parts.append(_call('_ail_struct_pack_c', [value]))
                else:
                    parts.append(_call('_ail_struct_pack_bool', [value]))
            self.used = True
            if not parts:
                return ast.copy_location(ast.Constant(value=b''), node)
            out = parts[0]
            for part in parts[1:]:
                out = ast.BinOp(left=out, op=ast.Add(), right=part)
            return ast.copy_location(out, node)
        # unpack
        if len(node.args) != 2:
            refuse(node, 'struct.unpack: expected a format and a buffer argument')
        fields, total, big = parse(_format_text(node.args[0], 'unpack'), node, 'unpack')
        if not fields:
            refuse(node, "struct.unpack: a format with no fields is not built")
        buf = node.args[1]
        if not _repeatable(buf):
            refuse(node, 'struct.unpack: the buffer is read once per field, so a call or comprehension cannot be '
                         'the buffer; assign it to a name first')
        self.used = True
        checked = _call('_ail_struct_check', [buf, _number(total)])
        elements = []
        offset = 0
        for field in fields:
            if field[0] == 'int':
                _, size, signed, code = field
                elements.append(_call('_ail_struct_unpack_int', [checked, _number(offset), _number(size),
                                                                 ast.Constant(value=signed), ast.Constant(value=big)]))
                offset += size
            elif field[0] == 's':
                n = field[1]
                elements.append(ast.Subscript(value=checked, slice=ast.Slice(lower=_number(offset),
                                                                             upper=_number(offset + n)), ctx=ast.Load()))
                offset += n
            elif field[0] == 'c':
                elements.append(ast.Subscript(value=checked, slice=ast.Slice(lower=_number(offset),
                                                                             upper=_number(offset + 1)), ctx=ast.Load()))
                offset += 1
            elif field[0] == 'bool':
                elements.append(ast.Compare(left=ast.Subscript(value=checked, slice=_number(offset), ctx=ast.Load()),
                                            ops=[ast.NotEq()], comparators=[_number(0)]))
                offset += 1
            else:
                offset += field[1]
        return ast.copy_location(ast.Tuple(elts=elements, ctx=ast.Load()), node)


def collect(tree):
    """Remove the module's imports; the Binder of the names they bind."""
    binder = stdlib5.Binder('struct')
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            rest = []
            for alias in node.names:
                if alias.name == 'struct':
                    binder.aliases.add(alias.asname or alias.name)
                    binder.first = binder.first or node
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'struct':
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, "from 'struct' import *: name what you use")
                if alias.name not in HANDLED:
                    refuse(node, "from 'struct': %s is not built (%s)" % (alias.name, UNKNOWN))
                binder.names[alias.asname or alias.name] = alias.name
                binder.first = binder.first or node
            continue
        body.append(node)
    tree.body = body
    return binder


def leftover(tree, binder):
    for each in ast.walk(tree):
        found = binder.attr(each)
        if found is not None:
            if found in HANDLED:
                refuse(each, 'struct.%s used as a value is not built; call it where it is used' % found)
            refuse(each, 'struct.%s is not built (%s)' % (found, UNKNOWN))
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in binder.aliases:
            refuse(each, "'struct' used as a value is not built")


def rewrite_text(source, notes=None):
    """The program text with `struct` lowered; the source as written (and `notes` filled) when a use is not built."""
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return source
    binder = None
    try:
        binder = collect(tree)
        if not binder:
            return source
        for each in ast.walk(tree):
            if isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name in HELPER_NAMES:
                refuse(each, "'%s' is defined by the program and is also the name of a struct helper; rename it"
                       % each.name)
            if isinstance(each, ast.Name) and isinstance(each.ctx, (ast.Store, ast.Del)) and each.id in HELPER_NAMES:
                refuse(each, "'%s' is bound by the program and is also the name of a struct helper; rename it"
                       % each.id)
        lower = Lower(binder)
        tree.body = [lower.visit(stmt) for stmt in tree.body]
        leftover(tree, binder)
        ast.fix_missing_locations(tree)
        if lower.used:
            stdlib5.insert_after_imports(tree, HELPERS)
            ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct library rewrite could not handle this program (%s: %s); simplify the use '
                             'or report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
