"""Library batch 6: `struct` lowered onto int.to_bytes / int.from_bytes and plain bytes.

`rewrite_text(source, notes)` runs from ail_syntax.python_surface before the tuple pass. A program that
does not import struct is returned unchanged, so its C does not change. Every supported use is lowered to
a helper written in Python syntax; a use outside the built surface leaves the program as written and adds
a `note:` line, and the import the compiler then meets is reported by that note (a named compile-time
refusal), exactly as stdlib4/stdlib5 do.

Built: `struct.pack`, `struct.unpack`, `struct.unpack_from`, `struct.pack_into`, `struct.calcsize` and
`struct.error`, with a string-literal format that starts with `<`, `>` or `!` (explicit byte order) and
uses the standard sizes. Format codes: x, b, B, h, H, i, I, l, L, q, s, c and ?. The error messages
and the buffer checks are CPython 3.12's.

Not built (refused by name): the native `@`/`=`/no-prefix layouts (alignment and native sizes), the float
codes e/f/d, the pointer codes n/N/P, the p code, the unsigned 64-bit Q (it can exceed int64), `struct.Struct`,
`struct.iter_unpack`, a format that is not a string literal, and any other attribute of the module.
"""
import ast

from stdlib4 import Refused, refuse

FUNCS = ('pack', 'unpack', 'unpack_from', 'pack_into', 'calcsize')
PREFIXES = {'<': 'little', '>': 'big', '!': 'big'}
SIZES = {'b': (1, True), 'B': (1, False), 'h': (2, True), 'H': (2, False),
         'i': (4, True), 'I': (4, False), 'l': (4, True), 'L': (4, False),
         'q': (8, True)}
BOUNDS = {'b': (-128, 127), 'B': (0, 255), 'h': (-32768, 32767), 'H': (0, 65535),
          'i': (-2147483648, 2147483647), 'I': (0, 4294967295),
          'l': (-2147483648, 2147483647), 'L': (0, 4294967295),
          'q': (-9223372036854775808, 9223372036854775807)}
FLOATS = frozenset('efd')
POINTERS = frozenset('nNP')
ERROR = '_AilStructError'

SHARED = '''class _AilStructError(Exception):
    pass


def _ail_struct_zeros(n: int) -> bytes:
    out = b""
    i = 0
    while i < n:
        out += b"\\x00"
        i += 1
    return out


def _ail_struct_int(value: int, n: int, order: str, signed: bool, lo: int, hi: int, msg: str) -> bytes:
    if not isinstance(value, int):
        raise _AilStructError("required argument is not an integer")
    if value < lo or value > hi:
        raise _AilStructError(msg)
    return int(value).to_bytes(n, order, signed=signed)


def _ail_struct_read(data: bytes, off: int, n: int, order: str, signed: bool) -> int:
    return int.from_bytes(data[off:off + n], order, signed=signed)


def _ail_struct_s(value: bytes, n: int) -> bytes:
    if not isinstance(value, bytes):
        raise _AilStructError("argument for 's' must be a bytes object")
    if len(value) >= n:
        return value[0:n]
    return value + _ail_struct_zeros(n - len(value))


def _ail_struct_c(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != 1:
        raise _AilStructError("char format requires a bytes object of length 1")
    return value


def _ail_struct_bool(value: int) -> bytes:
    if value:
        return b"\\x01"
    return b"\\x00"


def _ail_struct_check_unpack(data: bytes, size: int) -> None:
    if len(data) != size:
        raise _AilStructError("unpack requires a buffer of " + str(size) + " bytes")


def _ail_struct_check_unpack_from(data: bytes, off: int, size: int) -> None:
    if off < 0:
        raise _AilStructError("not enough data to unpack " + str(size) + " bytes at offset " + str(off))
    if off + size > len(data):
        raise _AilStructError("unpack_from requires a buffer of at least " + str(off + size)
                              + " bytes for unpacking " + str(size) + " bytes at offset " + str(off)
                              + " (actual buffer size is " + str(len(data)) + ")")


def _ail_struct_write(buf: bytearray, off: int, raw: bytes, size: int) -> None:
    if off < 0:
        raise _AilStructError("no space to pack " + str(size) + " bytes at offset " + str(off))
    if off + size > len(buf):
        raise _AilStructError("pack_into requires a buffer of at least " + str(off + size)
                              + " bytes for packing " + str(size) + " bytes at offset " + str(off)
                              + " (actual buffer size is " + str(len(buf)) + ")")
    i = 0
    while i < size:
        buf[off + i] = raw[i]
        i += 1
'''


class Binder:
    """What the program calls struct: `import struct [as a]` and `from struct import x [as y]`."""

    def __init__(self):
        self.aliases = set()
        self.names = {}
        self.first = None

    def __bool__(self):
        return bool(self.aliases or self.names)

    def attr(self, node):
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.aliases:
            return node.attr
        return None


def take_imports(tree):
    binder = Binder()
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
            rest = []
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, 'from struct import *: name what you use')
                if alias.name in FUNCS or alias.name == 'error':
                    binder.names[alias.asname or alias.name] = alias.name
                    binder.first = binder.first or node
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        body.append(node)
    tree.body = body
    return binder


def bound_names(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
    return out


def parse_format(node, fmt):
    if not isinstance(fmt, str):
        refuse(node, 'struct: the format must be a string literal, so the size and the codes are known here')
    if not fmt:
        return 'big', [], 0, 0
    if fmt[0] not in PREFIXES:
        refuse(node, 'struct: only the explicit byte orders <, > and ! are built; the native layout '
                     '(no prefix, @ or =) has alignment and native sizes, which are not')
    order = PREFIXES[fmt[0]]
    tokens = []
    size = 0
    values = 0
    i = 1
    while i < len(fmt):
        if fmt[i].isdigit():
            j = i
            while j < len(fmt) and fmt[j].isdigit():
                j += 1
            count = int(fmt[i:j])
            i = j
            if i >= len(fmt):
                refuse(node, 'struct: a repeat count at the end of the format names no code')
            code = fmt[i]
            i += 1
        else:
            count = 1
            code = fmt[i]
            i += 1
        if code == 'x':
            tokens.append(('x', count, count, None))
            size += count
        elif code == 's':
            tokens.append(('s', count, count, None))
            size += count
            values += 1
        elif code == 'c':
            tokens.append(('c', count, count, None))
            size += count
            values += count
        elif code == '?':
            tokens.append(('?', count, count, None))
            size += count
            values += count
        elif code in SIZES:
            width, signed = SIZES[code]
            tokens.append(('int', count, count * width, (code, width, signed)))
            size += count * width
            values += count
        elif code in FLOATS:
            refuse(node, "struct: the float format %r is not built; pack the value by hand or use an int format" % code)
        elif code in POINTERS:
            refuse(node, "struct: the pointer format %r is not built; its size depends on the target" % code)
        elif code == 'Q':
            refuse(node, "struct: the unsigned 64-bit format 'Q' can exceed int64, which is not built here")
        else:
            refuse(node, 'struct: format code %r is not built (built: x b B h H i I l L q s c ?)' % code)
    return order, tokens, size, values


class Calls(ast.NodeTransformer):
    def __init__(self, binder, builder):
        self.binder = binder
        self.builder = builder

    def visit_Attribute(self, node):
        node = self.generic_visit(node)
        if self.binder.attr(node) == 'error':
            return ast.copy_location(ast.Name(id=ERROR, ctx=ast.Load()), node)
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.binder.names and self.binder.names[node.id] == 'error':
            return ast.copy_location(ast.Name(id=ERROR, ctx=ast.Load()), node)
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        what = self.binder.attr(node.func)
        if what is None:
            return node
        if what not in FUNCS:
            refuse(node, 'struct.%s is not built' % what)
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            refuse(node, 'struct.%s with a starred argument is not built; pass the values one by one' % what)
        if node.keywords:
            refuse(node, 'struct.%s with a keyword argument is not built; pass the arguments in order' % what)
        if what == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize takes one format')
            fmt = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
            order, tokens, size, values = parse_format(node, fmt)
            return ast.copy_location(ast.Constant(value=size), node)
        if not node.args:
            refuse(node, 'struct.%s needs a format' % what)
        fmt = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
        order, tokens, size, values = parse_format(node, fmt)
        if what == 'pack':
            if len(node.args) - 1 != values:
                refuse(node, 'struct.pack for this format takes %d values, not %d' % (values, len(node.args) - 1))
            helper = self.builder.pack(fmt, order, tokens, size, values)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=node.args[1:], keywords=[]), node)
        if what == 'unpack':
            if len(node.args) != 2:
                refuse(node, 'struct.unpack takes a format and a buffer')
            helper = self.builder.unpack(fmt, order, tokens, size)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=[node.args[1]], keywords=[]), node)
        if what == 'unpack_from':
            if len(node.args) not in (2, 3):
                refuse(node, 'struct.unpack_from takes a format, a buffer and an optional offset')
            helper = self.builder.unpack_from(fmt, order, tokens, size)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=node.args[1:], keywords=[]), node)
        if what == 'pack_into':
            if len(node.args) - 3 != values:
                refuse(node, 'struct.pack_into for this format takes %d values, not %d'
                       % (values, len(node.args) - 3))
            helper = self.builder.pack_into(fmt, order, tokens, size, values)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=node.args[1:], keywords=[]), node)
        return node


class Builder:
    def __init__(self):
        self.sources = []
        self.seen = {}
        self.counter = 0

    def suffix(self, fmt):
        if fmt not in self.seen:
            self.seen[fmt] = self.counter
            self.counter += 1
        return self.seen[fmt]

    def params(self, tokens, values, start=0):
        kinds = []
        for kind, count, width, info in tokens:
            if kind == 'int':
                kinds.extend(['int'] * count)
            elif kind in ('s', 'c'):
                kinds.extend(['bytes'] * count if kind == 'c' else ['bytes'])
            elif kind == '?':
                kinds.extend(['int'] * count)
        return ', '.join('v%d: %s' % (start + i, kinds[i]) for i in range(values))

    def args(self, values, start=0):
        return ', '.join('v%d' % (start + i) for i in range(values))

    def add(self, key, text):
        if key not in self.seen:
            self.sources.append(text)

    def pack(self, fmt, order, tokens, size, values):
        name = '_ail_struct_pack_%d' % self.suffix(fmt)
        key = ('pack', fmt)
        if key in self.seen:
            return name
        self.seen[key] = True
        lines = ['def %s(%s) -> bytes:' % (name, self.params(tokens, values)), '    out = b""']
        index = 0
        for kind, count, width, info in tokens:
            if kind == 'int':
                code, n, signed = info
                lo, hi = BOUNDS[code]
                msg = "'%s' format requires %d <= number <= %d" % (code, lo, hi)
                for _ in range(count):
                    lines.append('    out += _ail_struct_int(v%d, %d, "%s", %s, %d, %d, %r)'
                                 % (index, n, order, signed, lo, hi, msg))
                    index += 1
            elif kind == 's':
                lines.append('    out += _ail_struct_s(v%d, %d)' % (index, count))
                index += 1
            elif kind == 'c':
                for _ in range(count):
                    lines.append('    out += _ail_struct_c(v%d)' % index)
                    index += 1
            elif kind == '?':
                for _ in range(count):
                    lines.append('    out += _ail_struct_bool(v%d)' % index)
                    index += 1
            elif kind == 'x' and count:
                lines.append('    out += _ail_struct_zeros(%d)' % count)
        lines.append('    return out')
        self.sources.append('\n'.join(lines) + '\n')
        return name

    def elements(self, tokens, base, for_from):
        out = []
        off = base
        for kind, count, width, info in tokens:
            if kind == 'int':
                code, n, signed = info
                for _ in range(count):
                    out.append('_ail_struct_read(data, %s + %d, %d, "%s", %s)'
                               % (off, 0, n, self.order, signed))
                    off = '%s + %d' % (off, n)
                # the expression above is rebuilt below; keep offsets numeric in the caller
            elif kind == 's':
                out.append('data[%s:%s + %d]' % (off, off, count))
                off = '%s + %d' % (off, count)
            elif kind == 'c':
                for _ in range(count):
                    out.append('data[%s:%s + 1]' % (off, off))
                    off = '%s + 1' % off
            elif kind == '?':
                for _ in range(count):
                    out.append('data[%s] != 0' % off)
                    off = '%s + 1' % off
            elif kind == 'x':
                off = '%s + %d' % (off, count)
        return out

    def unpack(self, fmt, order, tokens, size):
        name = '_ail_struct_unpack_%d' % self.suffix(fmt)
        key = ('unpack', fmt)
        if key in self.seen:
            return name
        self.seen[key] = True
        self.order = order
        types = []
        for kind, count, width, info in tokens:
            if kind == 'int':
                types.extend(['int'] * count)
            elif kind in ('s', 'c'):
                types.extend(['bytes'] * count if kind == 'c' else ['bytes'])
            elif kind == '?':
                types.extend(['bool'] * count)
        annotation = 'tuple[%s]' % ', '.join(types) if types else 'tuple[()]'
        elems = self.elements(tokens, '0', False)
        ret = '(' + ', '.join(elems) + (',' if len(elems) == 1 else '') + ')'
        text = ('def %s(data: bytes) -> %s:\n    _ail_struct_check_unpack(data, %d)\n    return %s\n'
                % (name, annotation, size, ret))
        self.sources.append(text)
        return name

    def unpack_from(self, fmt, order, tokens, size):
        name = '_ail_struct_unpack_from_%d' % self.suffix(fmt)
        key = ('unpack_from', fmt)
        if key in self.seen:
            return name
        self.seen[key] = True
        self.order = order
        types = []
        for kind, count, width, info in tokens:
            if kind == 'int':
                types.extend(['int'] * count)
            elif kind in ('s', 'c'):
                types.extend(['bytes'] * count if kind == 'c' else ['bytes'])
            elif kind == '?':
                types.extend(['bool'] * count)
        annotation = 'tuple[%s]' % ', '.join(types) if types else 'tuple[()]'
        elems = self.elements(tokens, 'off', True)
        ret = '(' + ', '.join(elems) + (',' if len(elems) == 1 else '') + ')'
        text = ('def %s(data: bytes, off: int = 0) -> %s:\n'
                '    _ail_struct_check_unpack_from(data, off, %d)\n    return %s\n'
                % (name, annotation, size, ret))
        self.sources.append(text)
        return name

    def pack_into(self, fmt, order, tokens, size, values):
        name = '_ail_struct_pack_into_%d' % self.suffix(fmt)
        key = ('pack_into', fmt)
        if key in self.seen:
            return name
        self.seen[key] = True
        pack = self.pack(fmt, order, tokens, size, values)
        params = self.params(tokens, values, start=0)
        args = self.args(values)
        text = ('def %s(buf: bytearray, off: int%s) -> None:\n'
                '    raw = %s(%s)\n    _ail_struct_write(buf, off, raw, %d)\n'
                % (name, (', ' + params) if params else '', pack, args, size))
        self.sources.append(text)
        return name


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return source
    try:
        binder = take_imports(tree)
        if not binder:
            return source
        rebound = bound_names(tree)
        for name in list(binder.aliases) + list(binder.names):
            if name in rebound:
                refuse(binder.first, '%s is also bound by the program itself; rename it (the name stands '
                                     'for the imported module here)' % name)
        builder = Builder()
        tree = Calls(binder, builder).visit(tree)
        ast.fix_missing_locations(tree)
        for each in ast.walk(tree):
            found = binder.attr(each)
            if found is not None:
                refuse(each, 'struct.%s used here is not built' % found)
            if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load):
                if each.id in binder.names or each.id in binder.aliases:
                    refuse(each, '%s used as a value is not built' % each.id)
        added = ast.parse(SHARED).body
        for chunk in builder.sources:
            added.extend(ast.parse(chunk).body)
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body[index:index] = added
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                             'report it' % (type(exc).__name__, exc)))
        return source
