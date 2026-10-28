"""The `struct` module (library batch 11): pack / unpack / pack_into / unpack_from / calcsize lowered to
prelude_struct.py, for formats made of integer, bool, character and (Pascal) string fields.

A format string must be a literal, so its layout, its item count and its errors are checked by CPython's own
`struct` at compile time (the author-side oracle, not at run time).  The generated program then builds or reads
the bytes with the helper functions of prelude_struct.py.  `unpack` / `unpack_from` get a small wrapper that
returns a real tuple, so printing and unpacking are CPython's.

Not built, refused by name: float32 / half / double floats (`f`, `e`, `d`), a zero-size `p` field (CPython 3.12's
`unpack` raises SystemError for it), `Struct`, `iter_unpack`, a format known only at run time, keyword
arguments, and the other attributes of the module.  `struct.error` is RuntimeError (the same
mapping the compiler uses for zlib.error), because the helper raises RuntimeError; its message is CPython's.
"""
import ast
import struct as _cstruct
import sys

import stdlib4
import stdlib5
from stdlib4 import refuse

HANDLED = {'pack', 'unpack', 'pack_into', 'unpack_from', 'calcsize', 'error'}
CODES = set('xcbB?hHiIlLqQnNPsp')
REFUSED = {'f': 'float32 (f) is not built',
           'e': 'half-precision floats (e) are not built',
           'd': 'double floats (d) are not built in this batch'}
_NATIVE_BIG = 1 if sys.byteorder == 'big' else 0


def _literal(node, name):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        refuse(node, 'struct.%s: the format has to be a string literal' % name)
    return node.value


def _layout(fmt, node, name):
    """(flat op list, byte size, item count) for a format CPython accepts."""
    try:
        _cstruct.calcsize(fmt)
    except (_cstruct.error, TypeError, ValueError) as exc:
        refuse(node, 'struct.%s: %s' % (name, exc))
    endian = '@'
    index = 0
    if fmt and fmt[0] in '@=<>!':
        endian = fmt[0]
        index = 1
    pieces = []                     # (piece text, kind, width, signed, big, alignment)
    while index < len(fmt):
        if fmt[index].isspace():
            index += 1
            continue
        end = index
        while end < len(fmt) and fmt[end].isdigit():
            end += 1
        count = int(fmt[index:end]) if end > index else 1
        index = end
        if index >= len(fmt):
            refuse(node, 'struct.%s: bad char in struct format' % name)
        code = fmt[index]
        if code in REFUSED:
            refuse(node, 'struct.%s: %s' % (name, REFUSED[code]))
        if code not in CODES:
            refuse(node, 'struct.%s: bad char in struct format' % name)
        index += 1
        if code == 'p' and count == 0:
            refuse(node, 'struct.%s: a zero-size p field is not built' % name)
        if code in 'sp':
            pieces.append((str(count) + code, 3 if code == 's' else 6, count, 0, 0, 1))
        elif code == 'x':
            pieces.append((str(count) + 'x', 4, count, 0, 0, 1))
        else:
            try:
                width = _cstruct.calcsize(endian + code)
            except _cstruct.error as exc:             # N/P only exist in native mode
                refuse(node, 'struct.%s: %s' % (name, exc))
            signed = 1 if code in 'bhilqn' else 0
            if code == '?':
                kind = 1
            elif code == 'c':
                kind = 2
            else:
                kind = 0
            big = _NATIVE_BIG if endian in '@=' else (1 if endian in '>!' else 0)
            align = width if code not in 'c?' else 1
            for _ in range(count):
                pieces.append((code, kind, width, signed, big, align))
    ops = []
    prefix = endian
    for text, kind, width, signed, big, align in pieces:
        offset = _cstruct.calcsize(prefix)
        if endian == '@' and align > 1 and offset % align:
            offset += align - offset % align
        ops.extend([kind, width, signed, big, offset])
        prefix += text
    return ops, _cstruct.calcsize(prefix), len(pieces) - sum(1 for p in pieces if p[1] == 4)


def _ops(ops):
    return ast.List(elts=[ast.Constant(value=value) for value in ops], ctx=ast.Load())


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'struct', HANDLED,
                                  unknown='pack, unpack, pack_into, unpack_from, calcsize and error are built')
    if not binder:
        return
    used = set()
    wrappers = []
    seen = {}

    def wrapper(ops, count, size, offset_call):
        key = (tuple(ops), count, size, offset_call)
        if key in seen:
            return seen[key]
        name = '_ail_struct_unpack_%d' % len(seen)
        seen[key] = name
        offset = 'offset' if offset_call else '0'
        fields = []
        index = 0
        while index < len(ops):
            kind = ops[index]
            width = ops[index + 1]
            signed = ops[index + 2]
            big = ops[index + 3]
            position = ops[index + 4]
            index += 5
            if kind == 0:
                fields.append('_ail_struct_unpack_int(data, %s, %d, %d, %d, %d)'
                              % (offset, position, width, signed, big))
            elif kind == 1:
                fields.append('_ail_struct_unpack_bool(data, %s, %d)' % (offset, position))
            elif kind == 2:
                fields.append('_ail_struct_unpack_char(data, %s, %d)' % (offset, position))
            elif kind == 3:
                fields.append('_ail_struct_unpack_bytes(data, %s, %d, %d)' % (offset, position, width))
            elif kind == 6:
                fields.append('_ail_struct_unpack_pascal(data, %s, %d, %d)' % (offset, position, width))
        result = '()' if not fields else '(%s,)' % ', '.join(fields)
        if offset_call:
            source = ('def %s(data, offset):\n'
                      '    _ail_struct_unpack_check(data, offset, %d, 0)\n'
                      '    return %s\n') % (name, size, result)
        else:
            source = ('def %s(data):\n'
                      '    _ail_struct_unpack_check(data, 0, %d, 1)\n'
                      '    return %s\n') % (name, size, result)
        wrappers.append(source)
        used.add('_ail_struct_unpack_check')
        return name

    def fix(node):
        if isinstance(node, ast.Call):
            found = binder.attr(node.func)
            if found is None:
                return None
            if node.keywords:
                refuse(node, 'struct.%s: keyword arguments are not built' % found)
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                refuse(node, 'struct.%s: a starred argument is not built' % found)
            args = [stdlib5.Replace(fix).visit(arg) for arg in node.args]
            if found == 'calcsize':
                if len(args) != 1:
                    refuse(node, 'struct.calcsize takes exactly one argument')
                return ast.Constant(value=_layout(_literal(args[0], found), node, found)[1])
            if found in ('pack', 'unpack', 'pack_into', 'unpack_from'):
                least = {'pack': 1, 'unpack': 2, 'pack_into': 3, 'unpack_from': 2}[found]
                most = {'pack': None, 'unpack': 2, 'pack_into': None, 'unpack_from': 3}[found]
                if len(args) < least or (most is not None and len(args) > most):
                    refuse(node, 'struct.%s: these arguments are not built' % found)
                fmt = _literal(args[0], found)
                ops, size, count = _layout(fmt, node, found)
                if found == 'pack':
                    used.add('_ail_struct_pack')
                    return stdlib5.call(stdlib5.name('_ail_struct_pack'), [
                        _ops(ops), ast.Constant(value=count),
                        ast.List(elts=args[1:], ctx=ast.Load())])
                if found == 'unpack':
                    name = wrapper(ops, count, size, False)
                    return stdlib5.call(stdlib5.name(name), [args[1]])
                if found == 'unpack_from':
                    offset = args[2] if len(args) == 3 else ast.Constant(value=0)
                    name = wrapper(ops, count, size, True)
                    return stdlib5.call(stdlib5.name(name), [args[1], offset])
                used.add('_ail_struct_pack_into')
                return stdlib5.call(stdlib5.name('_ail_struct_pack_into'), [
                    _ops(ops), ast.Constant(value=count), ast.Constant(value=size), args[1], args[2],
                    ast.List(elts=args[3:], ctx=ast.Load())])
        found = binder.attr(node)
        if found == 'error':
            return ast.copy_location(ast.Name(id='RuntimeError', ctx=ast.Load()), node)
        return None

    tree.body = [stdlib5.Replace(fix).visit(statement) for statement in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, 'pack, unpack, pack_into, unpack_from, calcsize and error are built')
    if used:
        text.append((stdlib5.HERE / 'prelude_struct.py').read_text(encoding='utf-8'))
    text.extend(wrappers)


def rewrite_text(source, notes=None):
    """The program text with the `struct` module lowered; the source as written (and `notes` filled) when a use is
    not built."""
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
        if ast.dump(tree) == before and not text:
            return source
        if text:
            stdlib5.insert_after_imports(tree, '\n\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except stdlib4.Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
