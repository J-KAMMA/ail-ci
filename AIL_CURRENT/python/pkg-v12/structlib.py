"""`struct` on the Python surface (library batch 22): pack / unpack / calcsize over integer formats.

A source-to-source pass in the manner of stdlib4/stdlib5, run by ail_syntax.python_surface before the
other source passes. A literal format string is parsed here, at compile time, and each call is lowered
to a small helper written in the Python subset the compiler builds: `int.to_bytes` and
`int.from_bytes` do the conversion, so the bytes are exactly CPython's.

Built: `struct.pack`, `struct.unpack`, `struct.calcsize` and `struct.error` (spelt ValueError, like
csv.Error) for the standard-size integer formats `b B h H i I l L q Q` and the pad `x`, with a
leading `<` (little), `>` (big) or `!` (big) byte order and an optional repeat count (`4I`).
Everything else -- floats, chars, strings, bools, `@` / native alignment, the `Struct` class,
`unpack_from`, `pack_into`, `iter_unpack` and a format known only at run time -- is refused by name.
"""
import ast

import stdlib5
from stdlib4 import Refused, refuse

SIZES = {'b': 1, 'B': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4, 'q': 8, 'Q': 8}
SIGNED = {'b', 'h', 'i', 'l', 'q'}
HANDLED = {'pack', 'unpack', 'calcsize', 'error'}
MAX_REPEAT = 4096
BUILT = 'struct.pack, struct.unpack, struct.calcsize and struct.error are built for the integer formats b B h H i I l L q Q and x, with < > or ! and an optional repeat count'


def parse_format(fmt, node=None):
    """(byte order, [(code, width)]) for a supported literal format, else refuse."""
    order = None
    index = 0
    if fmt:
        first = fmt[0]
        if first in '<>!':
            order = 'big' if first in '>!' else 'little'
            index = 1
        elif first in '=@':
            refuse(node, 'struct format %r: native alignment (%s) is not built; write <, > or !' % (fmt, first))
        else:
            refuse(node, 'struct format %r: a byte order of <, > or ! is required; native alignment is not built' % fmt)
    units = []
    while index < len(fmt):
        start = index
        while index < len(fmt) and fmt[index].isdigit():
            index += 1
        count = int(fmt[start:index]) if index > start else 1
        if index >= len(fmt):
            refuse(node, 'struct format %r ends with a repeat count' % fmt)
        code = fmt[index]
        index += 1
        if code in SIZES:
            if count > MAX_REPEAT:
                refuse(node, 'struct format %r: a repeat count over %d is not built' % (fmt, MAX_REPEAT))
            units.extend((code, SIZES[code]) for _ in range(count))
        elif code == 'x':
            if count > MAX_REPEAT:
                refuse(node, 'struct format %r: a repeat count over %d is not built' % (fmt, MAX_REPEAT))
            units.append(('x', count))
        else:
            refuse(node, 'struct format %r: %r is not built (only b B h H i I l L q Q and x are)' % (fmt, code))
    return order, units


def literal_format(node, what):
    if not isinstance(node, ast.Constant) or type(node.value) is not str:
        refuse(node, 'struct.%s: the format has to be a string literal' % what)
    return node.value


def number_check(code, name):
    """The statements that give CPython's struct.error text for a value outside the format's range."""
    bits = SIZES[code] * 8
    if code in SIGNED:
        low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        low_text = '-9223372036854775807 - 1' if low < -(1 << 63) else str(low)
        condition = '%s < %s or %s > %d' % (name, low_text, name, high)
        wanted = '%d <= number <= %d' % (low, high)
    else:
        high = (1 << bits) - 1
        condition = '%s < 0 or %s.bit_length() > %d' % (name, name, bits)
        wanted = '0 <= number <= %d' % high
    return ("    if %s:\n"
            "        raise ValueError(\"'%s' format requires %s\")\n"
            % (condition, code, wanted))


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    helpers = []
    count = [0]
    try:
        binder = stdlib5.take_imports(tree, 'struct', HANDLED, unknown=BUILT)

        if not binder:
            return source

        def fresh(kind):
            count[0] += 1
            return '_ail_struct_%s_%d' % (kind, count[0])

        def pack_call(call, fmt, as_list=False):
            if call.keywords:
                refuse(call, 'struct.pack(%r, ...) takes positional values only' % fmt)
            order, units = parse_format(fmt, call)
            values = list(call.args[1:])
            wanted = [code for code, _ in units if code != 'x']
            if len(values) != len(wanted):
                refuse(call, 'struct.pack(%r, ...): expected %d value(s), got %d' % (fmt, len(wanted), len(values)))
            name = fresh('pack_list' if as_list else 'pack')
            params = ', '.join('v%d: int' % i for i in range(len(values)))
            body = []
            for i, value in enumerate(values):
                body.append(number_check(wanted[i], 'v%d' % i))
            chunks = []
            vi = 0
            for code, width in units:
                if code == 'x':
                    chunks.append('b"\\x00" * %d' % width)
                else:
                    signed = 'True' if code in SIGNED else 'False'
                    chunks.append('v%d.to_bytes(%d, "%s", signed=%s)' % (vi, width, order, signed))
                    vi += 1
            expression = ' + '.join(chunks) if chunks else 'b""'
            if as_list:
                helpers.append('def %s(%s) -> list[int]:\n%s    data = %s\n    return list(data)\n'
                               % (name, params, ''.join(body), expression))
            else:
                helpers.append('def %s(%s) -> bytes:\n%s    return %s\n'
                               % (name, params, ''.join(body), expression))
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=values, keywords=[])

        def unpack_call(call, fmt):
            order, units = parse_format(fmt, call)
            if len(call.args) != 2 or call.keywords:
                refuse(call, 'struct.unpack(%r, data) takes exactly a format and one buffer' % fmt)
            size = sum(width for _, width in units)
            items = [code for code, _ in units if code != 'x']
            if not items:
                refuse(call, 'struct.unpack(%r, data): an empty result is not built' % fmt)
            name = fresh('unpack')
            body = ['    if len(data) != %d:\n        raise ValueError("unpack requires a buffer of %d bytes")\n'
                    % (size, size)]
            names = []
            offset = 0
            i = 0
            for code, width in units:
                if code == 'x':
                    offset += width
                    continue
                signed = 'True' if code in SIGNED else 'False'
                body.append('    v%d: int = int.from_bytes(data[%d:%d], "%s", signed=%s)\n'
                            % (i, offset, offset + width, order, signed))
                names.append('v%d' % i)
                offset += width
                i += 1
            result = '(' + ', '.join(names) + (',' if len(names) == 1 else '') + ')'
            helpers.append('def %s(data: bytes) -> tuple[%s]:\n%s    return %s\n'
                           % (name, ', '.join('int' for _ in names), ''.join(body), result))
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[call.args[1]], keywords=[])

        def calcsize_call(call, fmt):
            if len(call.args) != 1 or call.keywords:
                refuse(call, 'struct.calcsize(%r) takes exactly one format' % fmt)
            _, units = parse_format(fmt, call)
            return ast.Constant(value=sum(width for _, width in units))

        def fix(node):
            found = binder.attr(node)
            if found == 'error':
                return ast.Name(id='ValueError', ctx=ast.Load())
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'list'
                    and len(node.args) == 1 and not node.keywords):
                inner = node.args[0]
                if isinstance(inner, ast.Call) and binder.attr(inner.func) == 'pack':
                    args = [stdlib5.Replace(fix).visit(argument) for argument in inner.args]
                    inner = ast.copy_location(ast.Call(func=inner.func, args=args, keywords=[]), inner)
                    if not inner.args:
                        refuse(inner, 'struct.pack() needs a format string')
                    return pack_call(inner, literal_format(inner.args[0], 'pack'), as_list=True)
            if isinstance(node, ast.Call):
                found = binder.attr(node.func)
                if found in ('pack', 'unpack', 'calcsize'):
                    args = [stdlib5.Replace(fix).visit(argument) for argument in node.args]
                    keywords = [ast.keyword(arg=word.arg, value=stdlib5.Replace(fix).visit(word.value))
                                for word in node.keywords]
                    node = ast.copy_location(ast.Call(func=node.func, args=args, keywords=keywords), node)
                    if not node.args:
                        refuse(node, 'struct.%s() needs a format string' % found)
                    fmt = literal_format(node.args[0], found)
                    if found == 'pack':
                        return pack_call(node, fmt)
                    if found == 'unpack':
                        return unpack_call(node, fmt)
                    return calcsize_call(node, fmt)
            return None

        before = ast.dump(tree)
        tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
        for each in ast.walk(tree):
            found = binder.attr(each)
            if found is not None:
                refuse(each, 'struct.%s used here is not built: %s' % (found, BUILT))
        if helpers:
            stdlib5.insert_after_imports(tree, '\n\n'.join(helpers))
        if ast.dump(tree) == before:
            return source
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line or 1, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or report it'
                          % (type(exc).__name__, exc)))
        return source
