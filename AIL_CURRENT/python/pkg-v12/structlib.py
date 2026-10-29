"""`struct` lowered onto prelude_struct.py.

`struct.calcsize`, `pack`, `unpack` and `unpack_from` are built for a format string written as a literal
that starts with an explicit byte order ('<', '>' or '!').  The supported codes are x c b B ? h H i I l L
q Q s p, with an optional repeat count.  The native '@' form, '=' and the float codes e f d are refused
here by name; so are non-literal formats, because every size and code is checked at compile time.
`Struct`, `iter_unpack`, `pack_into` and `struct.error` are not built.

`calcsize` folds to its integer.  `pack` becomes a join of per-field byte expressions, and each literal
format gets one generated unpack helper with a fixed tuple annotation; neither path builds a dynamic list
of mixed value types, so the typed path can take it.
"""
import ast
import copy
import re
from pathlib import Path

import stdlib4

BUILT = ('calcsize', 'pack', 'unpack', 'unpack_from')
CODES = 'xcbB?hHiIlLqQsp'
UNITS = {'x': 1, 'c': 1, 'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4,
         'l': 4, 'L': 4, 'q': 8, 'Q': 8}
SIGNED = 'bhilq'


def _clean(text):
    return ''.join(text.split())


def _parse(node, fmt):
    if not isinstance(fmt, ast.Constant) or not isinstance(fmt.value, str):
        stdlib4.refuse(node, 'struct: the format must be a literal string, so the compiler can check every '
                             'code and size (assign the value to a str variable only when it is printed)')
    raw = fmt.value
    if raw.strip() and raw[0].isspace():
        stdlib4.refuse(node, 'struct: the format must not start with whitespace')
    if re.search(r'\d\s+[A-Za-z]', raw):
        stdlib4.refuse(node, 'struct: whitespace between a repeat count and a format code is not valid')
    text = _clean(raw)
    if text and text[0] not in '<>!':
        if text[0] in '@=':
            stdlib4.refuse(node, "struct: the native '%s' byte order is not built: write '<' or '>' and the "
                                 'width of every value explicitly' % text[0])
        stdlib4.refuse(node, "struct: the format must start with '<', '>' or '!' (an explicit byte order)")
    ops = []
    index = 1
    while index < len(text):
        count = 1
        if text[index].isdigit():
            count = 0
            while index < len(text) and text[index].isdigit():
                count = count * 10 + int(text[index])
                index += 1
            if index >= len(text):
                stdlib4.refuse(node, 'struct: the format ends with a repeat count and no code')
        code = text[index]
        index += 1
        if code in 'efd':
            stdlib4.refuse(node, "struct: the format code '%s' (a float) is not built: keep the value as an "
                                 'integer (for example scaled by 100) or print it with f"{x:.6f}"' % code)
        if code in 'nN':
            stdlib4.refuse(node, "struct: the format code '%s' is only valid in native mode, which is not "
                                 "built; use 'q' or 'Q'" % code)
        if code not in CODES:
            stdlib4.refuse(node, "struct: the format code '%s' is not built" % code)
        ops.append((code, count))
    size = 0
    fields = 0
    for code, count in ops:
        if code in 'sp':
            size += count
            fields += 1
        elif code == 'x':
            size += count
        else:
            size += UNITS[code] * count
            fields += count
    return text, ops, size, fields


def _call(node, name, args):
    return ast.copy_location(ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[]), node)


def _byte(value):
    return ast.Constant(value=value)


def _pack_value(node, code, count, value, order):
    if code == 'c':
        return _call(node, '_ail_struct_pack_c', [value])
    if code == 's':
        return _call(node, '_ail_struct_pack_s', [value, ast.Constant(value=count)])
    if code == 'p':
        return _call(node, '_ail_struct_pack_p', [value, ast.Constant(value=count)])
    if code == '?':
        flag = ast.Call(func=ast.Name(id='bool', ctx=ast.Load()), args=[value], keywords=[])
        return _call(node, '_ail_struct_bool', [flag])
    unit = UNITS[code]
    return _call(node, '_ail_struct_int_bytes', [
        value, ast.Constant(value=unit), ast.Constant(value=order),
        ast.Constant(value=code in SIGNED), ast.Constant(value=code)])


def _pack(node, fmt, raw_values):
    text, ops, size, fields = _parse(node, fmt)
    order = 'little' if not text or text[0] == '<' else 'big'
    starred = len(raw_values) == 1 and isinstance(raw_values[0], ast.Starred)
    if not starred and any(isinstance(value, ast.Starred) for value in raw_values):
        stdlib4.refuse(node, 'struct.pack: a * argument mixed with other values is not built; collect every '
                             'value in one list or tuple and pass it as *values')
    if starred:
        sequence = raw_values[0].value
    else:
        if len(raw_values) != fields:
            stdlib4.refuse(node, 'struct.pack: the format needs %d values but %d were given' %
                           (fields, len(raw_values)))
        sequence = None
    def value(index):
        if sequence is None:
            return raw_values[index]
        return ast.Subscript(value=copy.deepcopy(sequence), slice=ast.Constant(value=index), ctx=ast.Load())
    parts = []
    if starred:
        length = ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[copy.deepcopy(sequence)], keywords=[])
        parts.append(_call(node, '_ail_struct_arity', [length, ast.Constant(value=fields)]))
    used = 0
    for code, count in ops:
        if code == 'x':
            if count == 1:
                parts.append(_byte(b'\x00'))
            elif count > 1:
                parts.append(ast.BinOp(left=_byte(b'\x00'), op=ast.Mult(), right=ast.Constant(value=count)))
            continue
        if code in 'sp':
            parts.append(_pack_value(node, code, count, value(used), order))
            used += 1
            continue
        for _ in range(count):
            parts.append(_pack_value(node, code, 1, value(used), order))
            used += 1
    if not parts:
        return _byte(b'')
    joined = ast.Call(func=ast.Attribute(value=_byte(b''), attr='join', ctx=ast.Load()),
                      args=[ast.List(elts=parts, ctx=ast.Load())], keywords=[])
    return ast.copy_location(joined, node)


def _unpack_type(code):
    if code == '?':
        return 'bool'
    if code in 'csp':
        return 'bytes'
    return 'int'


class Unpacker:
    def __init__(self):
        self.names = {}

    def helper(self, node, fmt):
        text, ops, size, fields = _parse(node, fmt)
        if fields == 0:
            stdlib4.refuse(node, 'struct.unpack of a format with no values is not built: it returns an empty '
                                 'tuple, so just use () after checking the length of the bytes')
        if any(code == 'p' and count == 0 for code, count in ops):
            stdlib4.refuse(node, "struct.unpack of a 'p' field with a zero count is not built: CPython 3.12 "
                                 'raises SystemError instead of returning an empty value')
        if text not in self.names:
            self.names[text] = (self._source(text, ops, size), len(self.names))
        source, number = self.names[text]
        return '_ail_struct_lowered_unpack_%d' % number, source

    def _source(self, text, ops, size):
        order = 'little' if not text or text[0] == '<' else 'big'
        types = []
        lines = []
        position = 0
        index = 0
        for code, count in ops:
            if code == 'x':
                position += count
                continue
            if code in 'sp':
                types.append('bytes')
                name = '_v%d' % index
                if code == 's':
                    lines.append('    %s: bytes = bytes(data[pos + %d:pos + %d])' %
                                 (name, position, position + count))
                else:
                    lines.append('    %s: bytes = _ail_struct_pascal(data, pos + %d, %d)' %
                                 (name, position, count))
                position += count
                index += 1
                continue
            for _ in range(count):
                types.append(_unpack_type(code))
                name = '_v%d' % index
                if code == 'c':
                    lines.append('    %s: bytes = bytes(data[pos + %d:pos + %d])' %
                                 (name, position, position + 1))
                elif code == '?':
                    lines.append('    %s: bool = data[pos + %d] != 0' % (name, position))
                else:
                    signed = 'True' if code in SIGNED else 'False'
                    lines.append("    %s: int = int.from_bytes(data[pos + %d:pos + %d], '%s', signed=%s)" %
                                 (name, position, position + UNITS[code], order, signed))
                position += UNITS[code]
                index += 1
        annotation = 'tuple[%s]' % ', '.join(types)
        # the number is filled in by helper() so the name and the call agree
        head = ['def PLACEHOLDER(data: bytes, offset: int, exact: bool) -> %s:' % annotation,
                '    pos: int = offset',
                '    if pos < 0:',
                '        pos = len(data) + pos',
                '    if pos < 0 or len(data) < pos + %d or (exact and len(data) != pos + %d):' % (size, size),
                f'        raise ValueError("unpack requires a buffer of %d bytes" % {size})']
        names = ', '.join('_v%d' % i for i in range(index))
        if index == 1:
            names += ','
        tail = ['    return (%s)' % names]
        return '\n'.join(head + lines + tail)

    def finish(self, text, number):
        source = self.names[text][0]
        return source.replace('def PLACEHOLDER(', 'def _ail_struct_lowered_unpack_%d(' % number, 1)


class Rewrite(ast.NodeTransformer):
    def __init__(self, imports, unpacker, helpers):
        self.imports = imports
        self.unpacker = unpacker
        self.helpers = helpers


def run(imports, tree, helpers):
    unpacker = Unpacker()
    generated = []

    class Lower(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            found = imports.resolve(node.func)
            if found is None or found[0] != 'struct':
                return node
            name = found[1]
            if node.keywords:
                stdlib4.refuse(node, 'struct.%s: keyword arguments are not built' % name)
            args = node.args
            if name == 'calcsize':
                if len(args) != 1:
                    stdlib4.refuse(node, 'struct.calcsize takes one format string')
                text, ops, size, fields = _parse(node, args[0])
                return ast.copy_location(ast.Constant(value=size), node)
            if name == 'pack':
                if not args:
                    stdlib4.refuse(node, 'struct.pack needs a format string')
                return _pack(node, args[0], args[1:])
            if name in ('unpack', 'unpack_from'):
                if (name == 'unpack' and len(args) != 2) or (
                        name == 'unpack_from' and len(args) not in (2, 3)):
                    if name == 'unpack':
                        stdlib4.refuse(node, 'struct.unpack takes a format string and a bytes value')
                    stdlib4.refuse(node, 'struct.unpack_from takes a format string, a bytes value and an '
                                         'optional offset')
                helper, source = unpacker.helper(node, args[0])
                if source not in generated:
                    generated.append(source)
                offset = args[2] if len(args) == 3 else ast.copy_location(ast.Constant(value=0), node)
                exact = ast.copy_location(ast.Constant(value=name == 'unpack'), node)
                return _call(node, helper, [args[1], offset, exact])
            stdlib4.refuse(node, 'struct.%s is not built: struct builds calcsize, pack, unpack and unpack_from '
                                 "for a literal '<', '>' or '!' format of integer, character, bool, string and "
                                 'pad codes' % name)

    Lower().visit(tree)
    ast.fix_missing_locations(tree)
    for text, (source, number) in unpacker.names.items():
        if source in generated:
            helpers.append(unpacker.finish(text, number))
    helpers.append(Path(__file__).with_name('prelude_struct.py').read_text(encoding='utf-8'))
