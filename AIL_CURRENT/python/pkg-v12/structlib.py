"""Library batch 44: `struct` for the integer, bool, char, string and padding formats.

`rewrite_text(source, notes)` runs from ail_syntax.python_surface before the other source passes and removes the
module's imports, replacing each call with a helper function whose format is checked here. A literal format whose
values are built returns the same bytes (and the same tuple) as CPython 3.12; a non-literal format, a float format
('e', 'f', 'd'), Struct / iter_unpack, or a format character outside the subset is refused by name.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from stdlib4 import Refused, refuse
from stdlib5 import imported_modules, insert_after_imports, leftover, prelude, take_imports

HANDLED = {'pack', 'unpack', 'unpack_from', 'pack_into', 'calcsize', 'error'}
UNBUILT = ('Struct, iter_unpack and the float formats e, f and d are not built; '
           'use pack / unpack / unpack_from / pack_into / calcsize with an integer, bool, c, s, p or x format')
CHARS = 'xcbB?hHiIlLqQnNspP'
UNSIGNED = 'BHLQNP'
WS = ' \t\n\r\v\f'


class FormatError(Exception):
    pass


def _elem_size(prefix, ch):
    if ch in 'xc bB?sp'.replace(' ', ''):
        return 1
    if ch in 'hH':
        return 2
    if ch in 'iI':
        return 4
    if ch in 'lL':
        return 8 if prefix == '@' else 4
    if ch in 'qQnNP':
        return 8
    raise FormatError('bad char in struct format')


def _padding(pos, align):
    if align <= 1:
        return 0
    return (align - pos % align) % align


def _layout(fmt):
    prefix = '@'
    start = 0
    if fmt and fmt[0] in '<>=!@':
        prefix = fmt[0]
        start = 1
    values = []
    pos = 0
    num = ''
    i = start
    while i < len(fmt):
        ch = fmt[i]
        if ch in WS:
            if num != '':
                raise FormatError('bad char in struct format')
            i += 1
            continue
        if ch >= '0' and ch <= '9':
            num += ch
            i += 1
            continue
        if ch in 'fde':
            raise FormatError("the '%s' float format is not built: use an integer, bool, c, s, p or x format" % ch)
        if ch not in CHARS:
            raise FormatError('bad char in struct format')
        if ch in 'nNP' and prefix != '@':
            raise FormatError('bad char in struct format')
        n = 1
        if num != '':
            n = int(num)
        if ch == 'x':
            pos += n
        elif ch == 's' or ch == 'p':
            values.append(ch)
            pos += n
        else:
            size = _elem_size(prefix, ch)
            if n == 0:
                if prefix == '@':
                    pos += _padding(pos, size)
            else:
                k = 0
                while k < n:
                    if prefix == '@':
                        pos += _padding(pos, size)
                    pos += size
                    values.append(ch)
                    k += 1
        num = ''
        i += 1
    if num != '':
        raise FormatError('repeat count given without format specifier')
    return values, pos


def _has_zero_p(fmt):
    prefix = "@"
    start = 0
    if fmt and fmt[0] in "<>=!@":
        prefix = fmt[0]
        start = 1
    num = ""
    i = start
    while i < len(fmt):
        ch = fmt[i]
        if ch in WS:
            if num != "":
                raise FormatError("bad char in struct format")
            i += 1
            continue
        if ch >= "0" and ch <= "9":
            num += ch
            i += 1
            continue
        n = 1
        if num != "":
            n = int(num)
        if ch == "p" and n == 0:
            return True
        num = ""
        i += 1
    return False


def _constant_format(node, name):
    if len(node.args) == 0:
        refuse(node, 'struct.%s: the format must be a literal string' % name)
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        refuse(node, 'struct.%s: the format must be a literal string' % name)
    return first.value


def _pack_call(idx, ch, fmt):
    if ch == '?':
        return '_ail_struct_pack_bool(%r, %d, v%d)' % (fmt, idx, idx)
    if ch in 'csp':
        return '_ail_struct_pack_bytes(%r, %d, v%d)' % (fmt, idx, idx)
    return '_ail_struct_pack_int(%r, %d, v%d)' % (fmt, idx, idx)


def _unpack_call(idx, ch, fmt):
    if ch == '?':
        return '_ail_struct_unpack_bool(%r, %d, data)' % (fmt, idx)
    if ch in 'csp':
        return '_ail_struct_unpack_bytes(%r, %d, data)' % (fmt, idx)
    return '_ail_struct_unpack_int(%r, %d, data)' % (fmt, idx)


def _unpack_at_call(idx, ch, fmt):
    if ch == '?':
        return '_ail_struct_unpack_bool_at(%r, %d, data, offset)' % (fmt, idx)
    if ch in 'csp':
        return '_ail_struct_unpack_bytes_at(%r, %d, data, offset)' % (fmt, idx)
    return '_ail_struct_unpack_int_at(%r, %d, data, offset)' % (fmt, idx)


def _binds_name(tree, wanted):
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and each.name == wanted:
            return True
        if isinstance(each, ast.arg) and each.arg == wanted:
            return True
        if isinstance(each, ast.Name) and each.id == wanted and isinstance(each.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(each, (ast.Import, ast.ImportFrom)):
            for alias in each.names:
                if (alias.asname or alias.name.split('.')[0]) == wanted:
                    return True
    return False


def run(tree, text):
    binder = take_imports(tree, 'struct', HANDLED, unknown=UNBUILT)
    if not binder:
        return
    uses_error = False
    counter = [0]
    helpers = []

    def helper_name(kind):
        counter[0] += 1
        return '_ail_struct_%s_%d' % (kind, counter[0])

    def fix(node):
        nonlocal uses_error
        if binder.attr(node) == 'error':
            if _binds_name(tree, 'error'):
                refuse(binder.first, 'the program binds the name error itself and also uses struct.error; rename one')
            uses_error = True
            return ast.Name(id='error', ctx=ast.Load())
        if isinstance(node, ast.Call) and binder.attr(node.func) == 'error':
            if _binds_name(tree, 'error'):
                refuse(binder.first, 'the program binds the name error itself and also uses struct.error; rename one')
            uses_error = True
            node.func = ast.Name(id='error', ctx=ast.Load())
            return node
        found = binder.attr(node)
        if found is not None and found not in HANDLED:
            refuse(node, 'struct.%s is not built: %s' % (found, UNBUILT))
        if not isinstance(node, ast.Call):
            return None
        found = binder.attr(node.func)
        if found is None or found not in HANDLED:
            return None
        if node.keywords:
            refuse(node, 'struct.%s: keyword arguments are not built' % found)
        for each in node.args:
            if isinstance(each, ast.Starred):
                refuse(node, 'struct.%s: starred arguments are not built' % found)
        fmt = _constant_format(node, found)
        try:
            values, total = _layout(fmt)
        except FormatError as exc:
            refuse(node, 'struct.%s: %s' % (found, exc))
        if found == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize: one format argument is built')
            return ast.Constant(value=total)
        if found == 'pack':
            if len(node.args) - 1 != len(values):
                refuse(node, 'struct.pack expected %d items for packing (got %d)' % (len(values), len(node.args) - 1))
            name = helper_name('pack')
            params = ', '.join('v%d' % k for k in range(len(values)))
            calls = ', '.join(_pack_call(k, ch, fmt) for k, ch in enumerate(values))
            helpers.append('def %s(%s):\n    return _ail_struct_pack_join(%r, [%s])\n'
                           % (name, params, fmt, calls))
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=node.args[1:], keywords=[])
        if found == 'unpack':
            if len(node.args) != 2:
                refuse(node, 'struct.unpack: a format and one buffer are built')
            if _has_zero_p(fmt):
                refuse(node, "struct.unpack: a zero-width 'p' format is not built (CPython 3.12 raises SystemError)")
            name = helper_name('unpack')
            calls = ', '.join(_unpack_call(k, ch, fmt) for k, ch in enumerate(values))
            if len(values) == 0:
                body = '    return ()\n'
            elif len(values) == 1:
                body = '    return (%s,)\n' % calls
            else:
                body = '    return (%s)\n' % calls
            helpers.append('def %s(data):\n    _ail_struct_check(%r, data)\n%s'
                           % (name, fmt, body))
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=node.args[1:], keywords=[])
        if found == 'unpack_from':
            if len(node.args) != 2 and len(node.args) != 3:
                refuse(node, 'struct.unpack_from: a format, one buffer and an optional offset are built')
            if _has_zero_p(fmt):
                refuse(node, "struct.unpack_from: a zero-width 'p' format is not built (CPython 3.12 raises SystemError)")
            name = helper_name('unpack_from')
            calls = ', '.join(_unpack_at_call(k, ch, fmt) for k, ch in enumerate(values))
            if len(values) == 0:
                body = '    return ()\n'
            elif len(values) == 1:
                body = '    return (%s,)\n' % calls
            else:
                body = '    return (%s)\n' % calls
            helpers.append('def %s(data, offset):\n    offset = _ail_struct_check_from(%r, data, offset)\n%s'
                           % (name, fmt, body))
            args = node.args[1:]
            if len(args) == 1:
                args = args + [ast.Constant(value=0)]
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[])
        if found == 'pack_into':
            if len(node.args) - 3 != len(values):
                refuse(node, 'struct.pack_into expected %d items for packing (got %d)'
                       % (len(values), len(node.args) - 3))
            name = helper_name('pack_into')
            params = 'buf, offset' + ''.join(', v%d' % k for k in range(len(values)))
            lines = ['def %s(%s):' % (name, params), '    offset = _ail_struct_check_into(%r, buf, offset)' % fmt]
            for k, ch in enumerate(values):
                lines.append('    _ail_struct_store_item(buf, %r, %d, offset, %s)'
                             % (fmt, k, _pack_call(k, ch, fmt)))
            helpers.append('\n'.join(lines) + '\n')
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=node.args[1:], keywords=[])
        return None

    body = []
    for stmt in tree.body:
        body.append(_Replace(fix).visit(stmt))
    tree.body = body
    binder.names.pop('error', None)
    leftover(tree, binder, 'pack, unpack, unpack_from, pack_into, calcsize and error are the names that are built')
    if helpers:
        text.append(prelude('struct'))
        text.extend(helpers)
    elif uses_error:
        text.append(prelude('struct'))


class _Replace(ast.NodeTransformer):
    def __init__(self, fn):
        self.fn = fn

    def visit(self, node):
        node = super().visit(node)
        if isinstance(node, ast.expr):
            new = self.fn(node)
            if new is not None:
                return ast.copy_location(new, node)
        return node


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if 'struct' not in imported_modules(tree):
        return source
    before = ast.dump(tree)
    text = []
    try:
        run(tree, text)
        changed = ast.dump(tree) != before or bool(text)
        if not changed:
            return source
        if text:
            insert_after_imports(tree, '\n\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct library rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
