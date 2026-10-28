"""struct.pack and struct.calcsize on the integer codes (called from ail_syntax.python_surface).

The format must be a string literal. `<`, `>`, `!` and `=` are built (with the standard sizes:
b/B = 1, h/H = 2, i/I/l/L = 4, q/Q = 8), the repeat count of every code (including 0), `x` padding
and whitespace between codes. The codes, the repeat count and the size are checked here; the exact
bytes, the item count and the range errors are made by `_ail_struct_pack`, a plain-Python helper
added after the imports (it can be read by CPython next to struct.pack).

Not built, refused by name: a format that is not a literal, the native format (`@` or no byte-order
character: its sizes and alignment depend on the C compiler), s/p/c/?/f/d/n/N, and unpack /
unpack_from / pack_into / iter_unpack / Struct (a tuple value, which this language does not have,
or a pointer). `struct.error` is bound to the helper's exception class, so `except struct.error`
works; only a program that prints the class of the exception sees a different name.
"""
import ast
import sys

import stdlib5
from stdlib4 import refuse

SIZES = {'b': 1, 'B': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4, 'q': 8, 'Q': 8, 'x': 1}
SPACE = ' \t\n\r\x0b\x0c'
MAX_SIZE = 2 ** 31 - 1
WHAT = ('struct.pack(fmt, values) with a literal fmt of the integer codes and struct.calcsize(fmt) are built; '
        'unpack, unpack_from, pack_into, iter_unpack, Struct, the native format and the other codes are not')


def _native_big():
    return sys.byteorder == 'big'


def parse_format(fmt, node):
    """(normalized format, expected item count, size) for a supported format, refusing otherwise."""
    if fmt[:1] in ('<', '>', '!', '='):
        prefix = fmt[0]
        body = fmt[1:]
        big = prefix in ('>', '!') or (prefix == '=' and _native_big())
    elif fmt.strip(SPACE):
        refuse(node, 'struct: a format without a byte-order character uses the native format, whose sizes and '
                     'alignment depend on the C compiler; write ">", "<", "!" or "=" in front')
    else:
        body = ''
        big = _native_big()
    i = 0
    expected = 0
    size = 0
    while i < len(body):
        ch = body[i]
        if ch in SPACE:
            i += 1
            continue
        start = i
        while i < len(body) and body[i].isdigit():
            i += 1
        count = int(body[start:i]) if i > start else 1
        if i >= len(body):
            refuse(node, 'struct: format %r has a repeat count without a format specifier' % fmt)
        code = body[i]
        i += 1
        if code not in SIZES:
            refuse(node, 'struct: the code %r of format %r is not built (the integer codes b B h H i I l L q Q '
                         'and padding x are)' % (code, fmt))
        expected += 0 if code == 'x' else count
        size += count * SIZES[code]
    if size > MAX_SIZE:
        refuse(node, 'struct: format %r declares %d bytes, more than the built maximum of %d'
               % (fmt, size, MAX_SIZE))
    return ('>' if big else '<') + body, expected, size


def run(tree, text):
    b = stdlib5.take_imports(tree, 'struct', {'pack', 'calcsize', 'error'},
                             unknown='pack, calcsize and error are built')
    if not b:
        return
    used = set()

    def fix(node):
        if isinstance(node, ast.Call):
            found = b.attr(node.func)
            if found == 'pack':
                if node.keywords:
                    refuse(node, 'struct.pack: keyword arguments are not built')
                if not node.args:
                    refuse(node, 'struct.pack: the format is missing')
                if any(isinstance(a, ast.Starred) for a in node.args):
                    refuse(node, 'struct.pack with a *values argument is not built: write the values out')
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    refuse(node, 'struct.pack: the format has to be a string literal')
                fmt, _expected, _size = parse_format(first.value, node)
                values = [stdlib5.Replace(fix).visit(a) for a in node.args[1:]]
                used.add('_ail_struct_pack')
                used.add('_AilStructError')
                return stdlib5.call(stdlib5.name('_ail_struct_pack'),
                                    [ast.Constant(value=fmt), ast.List(elts=values, ctx=ast.Load())])
            if found == 'calcsize':
                if node.keywords or len(node.args) != 1:
                    refuse(node, 'struct.calcsize takes one argument')
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    refuse(node, 'struct.calcsize: the format has to be a string literal')
                _fmt, _expected, size = parse_format(first.value, node)
                return ast.Constant(value=size)
            if found is not None:
                refuse(node, 'struct.%s is not built: %s' % (found, WHAT))
        found = b.attr(node)
        if found == 'error':
            used.add('_AilStructError')
            return stdlib5.name('_AilStructError')
        if found is not None:
            refuse(node, 'struct.%s used here is not built: %s' % (found, WHAT))
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, WHAT)
    if used:
        stdlib5.add_once(text, PRELUDE)


PRELUDE = r'''
class _AilStructError(Exception):
    pass


def _ail_struct_pack(template: str, vals: list[int]) -> bytes:
    big = True
    i = 0
    if len(template) > 0 and (template[0] == '<' or template[0] == '>'):
        big = template[0] == '>'
        i = 1
    n = len(template)
    expected = 0
    j = i
    while j < n:
        c = template[j]
        if c == ' ' or c == '\t' or c == '\n' or c == '\r' or c == '\v' or c == '\f':
            j += 1
            continue
        start = j
        while j < n and template[j].isdigit():
            j += 1
        count = 1
        if j > start:
            count = int(template[start:j])
        if j >= n:
            break
        code = template[j]
        j += 1
        if code != 'x':
            expected += count
    got = len(vals)
    if got != expected:
        raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(got) + ")")
    out: list[bytes] = []
    vi = 0
    j = i
    while j < n:
        c = template[j]
        if c == ' ' or c == '\t' or c == '\n' or c == '\r' or c == '\v' or c == '\f':
            j += 1
            continue
        start = j
        while j < n and template[j].isdigit():
            j += 1
        count = 1
        if j > start:
            count = int(template[start:j])
        code = template[j]
        j += 1
        if code == 'x':
            if count > 0:
                out.append(bytes(count))
            continue
        size = 1
        if code == 'h' or code == 'H':
            size = 2
        elif code == 'i' or code == 'I' or code == 'l' or code == 'L':
            size = 4
        elif code == 'q' or code == 'Q':
            size = 8
        signed = code == 'b' or code == 'h' or code == 'i' or code == 'l' or code == 'q'
        lo = 0
        hi = 0
        hi_text = ""
        if code == 'b':
            lo = -128
            hi = 127
            hi_text = "127"
        elif code == 'B':
            lo = 0
            hi = 255
            hi_text = "255"
        elif code == 'h':
            lo = -32768
            hi = 32767
            hi_text = "32767"
        elif code == 'H':
            lo = 0
            hi = 65535
            hi_text = "65535"
        elif code == 'i' or code == 'l':
            lo = -2147483648
            hi = 2147483647
            hi_text = "2147483647"
        elif code == 'I' or code == 'L':
            lo = 0
            hi = 4294967295
            hi_text = "4294967295"
        elif code == 'q':
            lo = -9223372036854775807 - 1
            hi = 9223372036854775807
            hi_text = "9223372036854775807"
        else:
            lo = 0
            hi = 9223372036854775807
            hi_text = "18446744073709551615"
        k = 0
        while k < count:
            v = vals[vi]
            vi += 1
            if not isinstance(v, int):
                raise _AilStructError("required argument is not an integer")
            if v < lo or v > hi:
                raise _AilStructError("'" + code + "' format requires " + str(lo) + " <= number <= " + hi_text)
            out.append(v.to_bytes(size, "big" if big else "little", signed=signed))
            k += 1
    return b"".join(out)
'''


def rewrite_text(source, notes=None):
    """The program text with struct.pack / struct.calcsize lowered; the source as written (and `notes`
    filled) when a use is not built."""
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if 'struct' not in stdlib5.imported_modules(tree):
        return source
    text = []
    try:
        before = ast.dump(tree)
        run(tree, text)
        if not text and ast.dump(tree) == before:
            return source
        if text:
            stdlib5.insert_after_imports(tree, '\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except stdlib5.Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
