# -*- coding: utf-8 -*-
"""`struct` (library batch 6): pack, unpack, unpack_from, calcsize and error, lowered onto prelude_struct.py.

The formats that are built are the integers, bytes, chars, bools and padding: x c b B ? h H i I l L q Q n N P s,
with the byte orders @ = < > !, native alignment and zero repeat counts. The format may be a str or bytes, an `s`
value or buffer may be a bytearray, and `unpack_from` takes CPython's negative offsets. Native ('@', the default)
uses the 64-bit little-endian sizes and alignment of the target. The float formats f / d / e and the Pascal string p
are refused by name; so are Struct, pack_into, unpack_into and the other names of the module. `unpack` /
`unpack_from` need a format written in the program, so the result is a tuple of the fields; `pack` and `calcsize`
may compute the format at run time.
"""
import ast
import struct as pystruct

import stdlib5
from stdlib4 import refuse

NAMES = {'pack': '_ail_struct_pack_list', 'unpack': '_ail_struct_unpack_list',
         'unpack_from': '_ail_struct_unpack_from_list', 'calcsize': '_ail_struct_calcsize',
         'error': '_AilStructError'}
HANDLED = set(NAMES)
KNOWN = 'xcbB?hHiIlLqQnNPs'
TYPES = {'x': None, 'c': 'bytes', 'b': 'int', 'B': 'int', '?': 'bool', 'h': 'int', 'H': 'int',
         'i': 'int', 'I': 'int', 'l': 'int', 'L': 'int', 'q': 'int', 'Q': 'int',
         'n': 'int', 'N': 'int', 'P': 'int', 's': 'bytes'}


def format_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode('ascii')
        except UnicodeDecodeError:
            return None
    return None


def fields_of(fmt, node, name):
    """(code, count) pairs in a constant format, refusing what the prelude cannot build."""
    original = fmt
    fmt = format_text(fmt)
    if fmt is None:
        refuse(node, 'struct.%s: bad format %r' % (name, original))
    prefix = '@'
    i = 0
    if len(fmt) > 0:
        first = fmt[0]
        if first == '@' or first == '=' or first == '<' or first == '>' or first == '!':
            prefix = first
            i = 1
    fields = []
    while i < len(fmt):
        c = fmt[i]
        if c in ' \t\n\r\v\f':
            i += 1
            continue
        count = 0
        seen = False
        while i < len(fmt) and '0' <= fmt[i] <= '9':
            count = count * 10 + ord(fmt[i]) - 48
            i += 1
            seen = True
        if not seen:
            count = 1
        if i >= len(fmt):
            refuse(node, 'struct.%s: bad format %r' % (name, fmt))
        c = fmt[i]
        i += 1
        if c in 'fde':
            refuse(node, "struct.%s: the %r format (floating point) is not built; pack and unpack are built for "
                   "x c b B ? h H i I l L q Q n N P s" % (name, c))
        if c == 'p':
            refuse(node, "struct.%s: the 'p' format (Pascal string) is not built; use %ds with a bytes value"
                   % (name, count))
        if c not in KNOWN:
            refuse(node, 'struct.%s: bad char in format %r' % (name, fmt))
        if prefix != '@' and c in 'nNP':
            refuse(node, 'struct.%s: the %r format needs the native byte order (@)' % (name, c))
        fields.append((c, count))
    return fields


def element_types(fields):
    out = []
    for code, count in fields:
        kind = TYPES[code]
        if kind is None:
            continue
        if code == 's':
            out.append(kind)
        else:
            out.extend([kind] * count)
    return out


def make_wrapper(fmt, start, name, values):
    if values:
        annotation = ' -> tuple[' + ', '.join(values) + ']'
    else:
        annotation = ''
    args = ', '.join('values[%d]' % i for i in range(len(values)))
    if len(values) == 1:
        args += ','
    if start:
        return ('def %s(data: bytes, offset: int = 0)%s:\n'
                '    values = _ail_struct_unpack_from_list(%r, data, offset)\n'
                '    return (%s)\n' % (name, annotation, fmt, args))
    return ('def %s(data: bytes)%s:\n'
            '    values = _ail_struct_unpack_list(%r, data)\n'
            '    return (%s)\n' % (name, annotation, fmt, args))


def run(tree, text):
    binder = stdlib5.take_imports(
        tree, 'struct', HANDLED,
        unknown='pack, unpack, unpack_from, calcsize and error are the names that are built')
    if not binder:
        return
    roots = set()
    wrappers = []
    cache = {}

    def wrapper(fmt, start):
        key = (fmt, start)
        if key not in cache:
            fields = fields_of(fmt, binder.first, 'unpack_from' if start else 'unpack')
            values = element_types(fields)
            name = ('_ail_struct_unpack_from_%d' if start else '_ail_struct_unpack_%d') % len(cache)
            cache[key] = name
            wrappers.append(make_wrapper(fmt, start, name, values))
        return cache[key]

    def one(call, what):
        if call.keywords:
            refuse(call, 'struct.%s: keyword arguments are not built' % what)
        return [stdlib5.Replace(fix).visit(a) for a in call.args]

    def fix(node):
        if isinstance(node, ast.Call):
            called = binder.attr(node.func)
            if called == 'pack':
                args = one(node, 'pack')
                if not args:
                    refuse(node, 'struct.pack takes a format and the values')
                fmt = args[0]
                if isinstance(fmt, ast.Constant) and isinstance(fmt.value, (str, bytes)):
                    fields_of(fmt.value, node, 'pack')
                if len(args) == 2 and isinstance(node.args[1], ast.Starred):
                    values = stdlib5.Replace(fix).visit(node.args[1].value)
                elif any(isinstance(a, ast.Starred) for a in node.args[1:]):
                    refuse(node, 'struct.pack: a *values argument must be the only value argument')
                else:
                    values = ast.List(elts=args[1:], ctx=ast.Load())
                roots.add('_ail_struct_pack_list')
                return stdlib5.call(stdlib5.name('_ail_struct_pack_list'), [args[0], values])
            if called == 'unpack' or called == 'unpack_from':
                args = one(node, called)
                if len(args) < 2:
                    refuse(node, 'struct.%s takes a format and a buffer' % called)
                fmt = args[0]
                if not (isinstance(fmt, ast.Constant) and isinstance(fmt.value, (str, bytes))):
                    refuse(node, 'struct.%s: the format must be written in the program (pack may compute it)'
                           % called)
                fields_of(fmt.value, node, called)
                name = wrapper(fmt.value, called == 'unpack_from')
                roots.add('_ail_struct_unpack_from_list' if called == 'unpack_from' else '_ail_struct_unpack_list')
                return stdlib5.call(stdlib5.name(name), args[1:])
            if called == 'calcsize':
                args = one(node, 'calcsize')
                if not args:
                    refuse(node, 'struct.calcsize takes a format')
                fmt = args[0]
                if isinstance(fmt, ast.Constant) and isinstance(fmt.value, (str, bytes)):
                    fields_of(fmt.value, node, 'calcsize')
                    return ast.copy_location(ast.Constant(value=pystruct.calcsize(fmt.value)), node)
                roots.add('_ail_struct_calcsize')
                return stdlib5.call(stdlib5.name('_ail_struct_calcsize'), [args[0]])
        found = binder.attr(node)
        if found == 'error':
            roots.add('_AilStructError')
            return stdlib5.name('_AilStructError')
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, 'see the reference for the struct functions that are built')
    if roots or wrappers:
        chunks = []
        if wrappers:
            chunks.extend(wrappers)
        if roots:
            roots.add('_AilStructIndexProbe')
            chunks.append(stdlib5.shake(stdlib5.prelude('struct'), roots))
        text.append('\n\n'.join(chunks))
