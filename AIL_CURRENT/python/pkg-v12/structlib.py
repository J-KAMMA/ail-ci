"""Library batch 46: `struct` lowered onto bytes and int.to_bytes / int.from_bytes.

`rewrite_text(source, notes)` runs from ail_syntax.python_surface before the other source passes.
A program that imports no `struct` is returned as it was written. Every use is either lowered to
ordinary Python code or refused here by name, as the other library batches do.

Built: `struct.pack`, `struct.unpack` and `struct.calcsize` with a literal format string and the
standard byte orders `<` (little), `>` / `!` (big) and `=` (native byte order, standard sizes).
The format characters built are `x c b B ? h H i I l L q Q s p`; native `@` / no prefix and the
remaining characters (`e f d n N P u w`) are refused by name. `pack_into`, `unpack_from`,
`iter_unpack`, `Struct` and `struct.error` are refused by name too.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from stdlib4 import Refused, refuse
from stdlib5 import Binder, imported_modules, insert_after_imports, leftover, name, take_imports

HANDLED = frozenset(('pack', 'unpack', 'calcsize', 'error'))
FORMAT_CHARS = frozenset('xcbB?hHiIlLqQsp')
REFUSED_CHARS = frozenset('efdnNPu w'.replace(' ', ''))

SIZES = {'b': 1, 'B': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4, 'q': 8, 'Q': 8}
SIGNED = {'b': True, 'B': False, 'h': True, 'H': False, 'i': True, 'I': False,
          'l': True, 'L': False, 'q': True, 'Q': False}

PRELUDE = '''
class error(Exception):
    pass


def _ail_struct_bool(v):
    if v:
        return b"\\x01"
    return b"\\x00"


def _ail_struct_char(v):
    if not isinstance(v, bytes):
        raise error("char format requires a bytes object of length 1")
    if len(v) != 1:
        raise error("char format requires a bytes object of length 1")
    return v


def _ail_struct_str(v: bytes, width: int) -> bytes:
    if isinstance(v, bytearray):
        v = bytes(v)
    if not isinstance(v, bytes):
        raise error("argument for 's' must be a bytes object")
    n = len(v)
    if n >= width:
        return v[:width]
    return v + b"\\x00" * (width - n)


def _ail_struct_pascal(v: bytes, width: int) -> bytes:
    if isinstance(v, bytearray):
        v = bytes(v)
    if not isinstance(v, bytes):
        raise error("argument for 'p' must be a bytes object")
    n = len(v)
    if n > width - 1:
        n = width - 1
    head = n.to_bytes(1, "big")
    return head + v[:n] + b"\\x00" * (width - 1 - n)


def _ail_struct_unpascal(data: bytes, offset: int, width: int) -> bytes:
    n = data[offset]
    if n > width - 1:
        n = width - 1
    return data[offset + 1:offset + 1 + n]
'''


ERROR_CLASS = 'class error(Exception):\n    pass'


class UnsupportedFormat(Exception):
    pass


class Field:
    def __init__(self, kind, size, signed=False, width=0, offset=0, ch=''):
        self.kind, self.size, self.signed, self.width, self.offset, self.ch = kind, size, signed, width, offset, ch


def byte_order(prefix):
    if prefix == '<':
        return 'little', 0
    if prefix in ('>', '!'):
        return 'big', 1
    if sys.byteorder == 'little':
        return 'little', 0
    return 'big', 1


def parse_format(fmt):
    """(order, layouts, fields, size) for a literal standard-size struct format."""
    i, n = 0, len(fmt)
    if n and fmt[0].isspace():
        raise UnsupportedFormat('struct: invalid format character %r' % fmt[0])
    prefix = None
    if i < n and fmt[i] in '@=<>!':
        prefix = fmt[i]
        i += 1
    order, _order_num = byte_order(prefix)
    native = prefix is None or prefix == '@'
    layouts, fields = [], []
    offset = 0
    while i < n:
        if fmt[i].isspace():
            i += 1
            continue
        start = i
        while i < n and fmt[i].isdigit():
            i += 1
        if i > start:
            count = int(fmt[start:i])
        else:
            count = 1
        if i >= n:
            raise UnsupportedFormat('struct: the format ends after a repeat count')
        ch = fmt[i]
        i += 1
        if ch in REFUSED_CHARS:
            raise UnsupportedFormat("struct: format character %r is not built; built here: x c b B ? h H i I l L q Q s p"
                                    % ch)
        if ch not in FORMAT_CHARS:
            raise UnsupportedFormat('struct: invalid format character %r' % ch)
        if native and ch != 'x':
            raise UnsupportedFormat("struct: native byte order (prefix '@' or none) is not built; write '<', '>', "
                                    "'=' or '!'")
        if ch == 'x':
            if count:
                layouts.append(('pad', count))
                offset += count
            continue
        if ch in ('s', 'p'):
            if count == 0:
                raise UnsupportedFormat("struct: a zero-length %r field is not built" % ch)
            field = Field(ch, count, width=count, offset=offset, ch=ch)
            fields.append(field)
            layouts.append(('field', field))
            offset += count
            continue
        if ch == 'c':
            for _ in range(count):
                field = Field('c', 1, offset=offset, ch=ch)
                fields.append(field)
                layouts.append(('field', field))
                offset += 1
            continue
        size = 1 if ch == '?' else SIZES[ch]
        for _ in range(count):
            field = Field('bool' if ch == '?' else 'int', size,
                          signed=SIGNED.get(ch, False), offset=offset, ch=ch)
            fields.append(field)
            layouts.append(('field', field))
            offset += size
    return order, layouts, fields, offset


def _range_lines(var, size, signed, ch):
    if signed:
        low, high = -(1 << (size * 8 - 1)), (1 << (size * 8 - 1)) - 1
    else:
        low, high = 0, (1 << (size * 8)) - 1
    return ['    if %s < %d or %s > %d:\n        raise error("\'%s\' format requires %d <= number <= %d")\n'
            % (var, low, var, high, ch, low, high)]


class Run:
    def __init__(self):
        self.count = 0
        self.helpers = []
        self.base = set()
        self.changed = False

    def helper_name(self, what):
        self.count += 1
        return '_ail_struct_%s_%d' % (what, self.count)

    def pack(self, node, fmt):
        try:
            order, layouts, fields, _size = parse_format(fmt)
        except UnsupportedFormat as exc:
            refuse(node, str(exc))
        if any(isinstance(arg, ast.Starred) for arg in node.args) or node.keywords:
            refuse(node, 'struct.pack: positional values are the form built')
        if len(node.args) != len(fields):
            refuse(node, 'struct.pack: format %r needs %d values, got %d' % (fmt, len(fields), len(node.args)))
        helper = self.helper_name('pack')
        params = []
        for index, field in enumerate(fields):
            if field.kind == 'int':
                params.append('v%d: int' % index)
            elif field.kind in ('s', 'p'):
                params.append('v%d: bytes' % index)
            else:
                params.append('v%d' % index)
        lines = ['def %s(%s) -> bytes:\n' % (helper, ', '.join(params))] if params else \
                ['def %s() -> bytes:\n' % helper]
        chunks = []
        arg = 0
        for index, (kind, item) in enumerate(layouts):
            target = '_b%d' % index
            if kind == 'pad':
                lines.append('    %s = b"\\x00" * %d\n' % (target, item))
                chunks.append(target)
                continue
            field = item
            source = 'v%d' % arg
            arg += 1
            if field.kind == 'int':
                lines.append('    if not isinstance(%s, int):\n'
                             '        raise error("required argument is not an integer")\n' % source)
                lines.extend(_range_lines(source, field.size, field.signed, field.ch))
                lines.append('    %s = %s.to_bytes(%d, "%s", signed=%s)\n'
                             % (target, source, field.size, order, field.signed))
            elif field.kind == 'bool':
                self.base.add('bool')
                lines.append('    %s = _ail_struct_bool(%s)\n' % (target, source))
            elif field.kind == 'c':
                self.base.add('char')
                lines.append('    %s = _ail_struct_char(%s)\n' % (target, source))
            elif field.kind == 's':
                self.base.add('str')
                lines.append('    %s = _ail_struct_str(%s, %d)\n' % (target, source, field.width))
            else:
                self.base.add('pascal')
                lines.append('    %s = _ail_struct_pascal(%s, %d)\n' % (target, source, field.width))
            chunks.append(target)
        lines.append('    return %s\n' % (' + '.join(chunks) if chunks else 'b""'))
        self.helpers.append(''.join(lines))
        self.changed = True
        return ast.copy_location(ast.Call(func=name(helper), args=list(node.args), keywords=[]), node)

    def unpack(self, node, fmt):
        try:
            _order, _layouts, fields, size = parse_format(fmt)
        except UnsupportedFormat as exc:
            refuse(node, str(exc))
        if any(isinstance(arg, ast.Starred) for arg in node.args) or node.keywords or len(node.args) != 1:
            refuse(node, 'struct.unpack: exactly one bytes value is the form built')
        helper = self.helper_name('unpack')
        lines = ['def %s(data: bytes):\n' % helper,
                 '    if isinstance(data, bytearray):\n'
                 '        data = bytes(data)\n',
                 '    if not isinstance(data, bytes):\n'
                 '        raise TypeError("a bytes-like object is required, not \'" + type(data).__name__ + "\'")\n',
                 '    if len(data) != %d:\n' % size,
                 '        raise error("unpack requires a buffer of %d bytes")\n' % size]
        values = []
        for index, field in enumerate(fields):
            target = 'v%d' % index
            start, stop = field.offset, field.offset + field.size
            if field.kind == 'int':
                lines.append('    %s = int.from_bytes(data[%d:%d], "%s", signed=%s)\n'
                             % (target, start, stop, _order, field.signed))
            elif field.kind == 'bool':
                lines.append('    %s = data[%d] != 0\n' % (target, start))
            elif field.kind == 'c':
                lines.append('    %s = data[%d:%d]\n' % (target, start, stop))
            elif field.kind == 's':
                lines.append('    %s = data[%d:%d]\n' % (target, start, stop))
            else:
                self.base.add('unpascal')
                lines.append('    %s = _ail_struct_unpascal(data, %d, %d)\n' % (target, start, field.width))
            values.append(target)
        lines.append('    return (%s)\n' % (', '.join(values) + (',' if len(values) == 1 else '')))
        self.helpers.append(''.join(lines))
        self.changed = True
        return ast.copy_location(ast.Call(func=name(helper), args=list(node.args), keywords=[]), node)

    def calcsize(self, node, fmt):
        try:
            _order, _layouts, _fields, size = parse_format(fmt)
        except UnsupportedFormat as exc:
            refuse(node, str(exc))
        if node.args or node.keywords:
            refuse(node, 'struct.calcsize: the format is the only argument')
        self.changed = True
        return ast.copy_location(ast.Constant(value=size), node)


def _literal_format(node, what):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        refuse(node, '%s: the format has to be a string literal: it is read when the program is built' % what)
    return node.value


def run_struct(tree):
    binder = take_imports(tree, 'struct', HANDLED, whole=True,
                          unknown="pack, unpack, calcsize and error are the names built")
    if not binder:
        return False
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and stmt.name == 'error':
            refuse(binder.first, 'the program binds the name error itself; rename it before using struct.error')
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'error' for t in stmt.targets):
            refuse(binder.first, 'the program binds the name error itself; rename it before using struct.error')
    local = set(binder.aliases) | set(binder.names)
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and each.name in local:
            refuse(binder.first, 'the program binds the name %s itself and also imports it; rename one' % each.name)
        if isinstance(each, ast.Name) and isinstance(each.ctx, (ast.Store, ast.Del)) and each.id in local:
            refuse(binder.first, 'the program binds the name %s itself and also imports it; rename one' % each.id)
    run = Run()

    class Replace(ast.NodeTransformer):
        def visit_Attribute(self, node):
            self.generic_visit(node)
            if binder.attr(node) == 'error':
                return ast.copy_location(name('error'), node)
            return node

        def visit_Name(self, node):
            self.generic_visit(node)
            if binder.attr(node) == 'error':
                return ast.copy_location(name('error'), node)
            return node

        def visit_Call(self, node):
            self.generic_visit(node)
            what = binder.attr(node.func)
            if what not in HANDLED:
                return node
            if what == 'error':
                return node
            if what == 'pack':
                args = node.args
                if not args:
                    refuse(node, 'struct.pack: the format is the first argument')
                fmt = _literal_format(args[0], 'struct.pack')
                inner = ast.copy_location(ast.Call(func=node.func, args=args[1:], keywords=node.keywords), node)
                return run.pack(inner, fmt)
            if what == 'unpack':
                if not node.args:
                    refuse(node, 'struct.unpack: the format is the first argument')
                fmt = _literal_format(node.args[0], 'struct.unpack')
                inner = ast.copy_location(ast.Call(func=node.func, args=node.args[1:], keywords=node.keywords), node)
                return run.unpack(inner, fmt)
            if not node.args:
                refuse(node, 'struct.calcsize: the format is the first argument')
            fmt = _literal_format(node.args[0], 'struct.calcsize')
            inner = ast.copy_location(ast.Call(func=node.func, args=node.args[1:], keywords=node.keywords), node)
            return run.calcsize(inner, fmt)

    tree.body = [Replace().visit(stmt) for stmt in tree.body]
    leftover(tree, binder, 'struct.pack, struct.unpack and struct.calcsize with a literal format are the forms built')
    if not run.changed:
        return False
    chunks = [ERROR_CLASS]
    for key in ('bool', 'char', 'str', 'pascal', 'unpascal'):
        if key in run.base:
            start = PRELUDE.find('def _ail_struct_%s' % key)
            if start < 0:
                continue
            end = PRELUDE.find('\n\n\ndef ', start + 1)
            if end < 0:
                end = len(PRELUDE)
            chunks.append(PRELUDE[start:end].strip('\n'))
    chunks.extend(run.helpers)
    insert_after_imports(tree, '\n\n'.join(chunks) + '\n')
    return True


def rewrite_text(source, notes=None):
    """The program text with `struct` lowered; the source as written (and `notes` filled) when a use is not built."""
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if 'struct' not in imported_modules(tree):
        return source
    try:
        if not run_struct(tree):
            return source
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
