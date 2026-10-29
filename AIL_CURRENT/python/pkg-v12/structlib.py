"""`struct` for the formats whose fields are known when the program is built.

The format is a string literal, so every field, offset and size is known here: `calcsize` becomes an int,
`pack` / `unpack` become calls to small generated functions, and `pack_into` / `unpack_from` keep their
buffer and offset. The integer, bool, char, string and padding codes are built; float, double, half-float
and Pascal-string codes are refused by name (the compiler has no float bit conversion in the general path).
A format that is not a literal is refused too: without the literal the field count is not known.
"""
import ast
import struct as _cpystruct

import stdlib3

from stdlib4 import Refused, refuse

SUPPORTED = set("xcbB?hHiIlLqQnNsP")
UNSUPPORTED = {
    'e': 'half-float',
    'f': 'float',
    'd': 'double',
    'p': 'Pascal string',
}
NATIVE_ONLY = set('nNP')
STD_SIZES = {'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4,
             'q': 8, 'Q': 8, 'n': 8, 'N': 8, 'P': 8}
NAT_SIZES = {'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 8, 'L': 8,
             'q': 8, 'Q': 8, 'n': 8, 'N': 8, 'P': 8}
SIGNED = set('bhilqn')

ERROR_PRELUDE = '''\
class _AilStructError(Exception):
    pass
'''

PRELUDE = ERROR_PRELUDE + '''\


def _ail_struct_tname(x):
    if x is None:
        return "NoneType"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, bytes):
        return "bytes"
    if isinstance(x, bytearray):
        return "bytearray"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    if isinstance(x, set):
        return "set"
    return "object"


def _ail_struct_index(v) -> int:
    if isinstance(v, int):
        return v
    raise TypeError("'" + _ail_struct_tname(v) + "' object cannot be interpreted as an integer")


def _ail_struct_int(v, ch, size, endian, signed, lo, hi) -> bytes:
    if not isinstance(v, int):
        raise _AilStructError("required argument is not an integer")
    if v < lo or v > hi:
        raise _AilStructError("'" + ch + "' format requires " + str(lo) + " <= number <= " + str(hi))
    return v.to_bytes(size, endian, signed=signed)


def _ail_struct_uint(data, start, size, endian, signed) -> int:
    return int.from_bytes(data[start:start + size], endian, signed=signed)


def _ail_struct_p(v, endian) -> bytes:
    if not isinstance(v, int):
        raise _AilStructError("required argument is not an integer")
    if v < -9223372036854775808 or v > 18446744073709551615:
        raise _AilStructError("int too large to convert")
    if v < 0:
        v = v & 18446744073709551615
    return v.to_bytes(8, endian, signed=False)


def _ail_struct_char(v) -> bytes:
    if not isinstance(v, bytes) or len(v) != 1:
        raise _AilStructError("char format requires a bytes object of length 1")
    return v


def _ail_struct_pad(v, size) -> bytes:
    if isinstance(v, bytearray):
        v = bytes(v)
    if not isinstance(v, bytes):
        raise _AilStructError("argument for 's' must be a bytes object")
    if len(v) >= size:
        return v[:size]
    return v + b"\\x00" * (size - len(v))


def _ail_struct_data(data):
    if isinstance(data, bytes) or isinstance(data, bytearray):
        return data
    raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")


def _ail_struct_slice(data, start, size) -> bytes:
    return bytes(data[start:start + size])


def _ail_struct_bool(data, start) -> bool:
    return data[start] != 0


def _ail_struct_exact(data, need):
    if len(data) != need:
        raise _AilStructError("unpack requires a buffer of " + str(need) + " bytes")


def _ail_struct_start(data, need, offset):
    offset = _ail_struct_index(offset)
    if offset < 0:
        if offset < -len(data):
            raise _AilStructError("offset " + str(offset) + " out of range for " + str(len(data)) + "-byte buffer")
        start = len(data) + offset
        if start + need > len(data):
            raise _AilStructError("not enough data to unpack " + str(need) + " bytes at offset " + str(offset))
        return start
    if offset + need > len(data):
        raise _AilStructError("unpack_from requires a buffer of at least " + str(offset + need) + " bytes for unpacking " + str(need) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(len(data)) + ")")
    return offset


def _ail_struct_pack_into(buf, offset, packed):
    if not isinstance(buf, bytearray):
        raise TypeError("argument must be read-write bytes-like object, not " + _ail_struct_tname(buf))
    offset = _ail_struct_index(offset)
    if offset < 0:
        if offset < -len(buf):
            raise _AilStructError("offset " + str(offset) + " out of range for " + str(len(buf)) + "-byte buffer")
        start = len(buf) + offset
        if start + len(packed) > len(buf):
            raise _AilStructError("no space to pack " + str(len(packed)) + " bytes at offset " + str(offset))
    else:
        start = offset
        if start + len(packed) > len(buf):
            raise _AilStructError("pack_into requires a buffer of at least " + str(start + len(packed)) + " bytes for packing " + str(len(packed)) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(len(buf)) + ")")
    buf[start:start + len(packed)] = packed
'''


class _Field:
    def __init__(self, kind, ch, offset, size, signed=False, lo=0, hi=0):
        self.kind, self.ch, self.offset, self.size = kind, ch, offset, size
        self.signed, self.lo, self.hi = signed, lo, hi


def _align(offset, size):
    return (offset + size - 1) // size * size


def _literal(node, fn):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
        refuse(node, 'struct.%s: the format must be a string literal, so the fields are known when the '
                     'program is built' % fn)
    value = node.value
    if isinstance(value, bytes):
        try:
            value = value.decode('ascii')
        except UnicodeDecodeError:
            refuse(node, 'struct.%s: bad char in struct format' % fn)
    return value


def _parse(fmt, node, fn):
    """(endian, fields, total, native) for a literal format; refuse what is not built."""
    i = 0
    n = len(fmt)
    mode = '@'
    if n and fmt[0] in '@=<>!':
        mode = fmt[0]
        i = 1
    native = mode == '@'
    endian = 'little' if mode in '@=<' else 'big'
    try:
        total = _cpystruct.calcsize(fmt)
    except _cpystruct.error as exc:
        refuse(node, 'struct.%s: %s' % (fn, exc))
    fields = []
    offset = 0
    while i < n:
        if fmt[i].isspace():
            i += 1
            continue
        start = i
        while i < n and fmt[i].isdigit():
            i += 1
        count = int(fmt[start:i]) if i > start else 1
        if i >= n:
            refuse(node, 'struct.%s: bad char in struct format' % fn)
        if count > 10000 and fmt[i] not in 'sx':
            refuse(node, 'struct.%s: the format has too many fields for this compiler' % fn)
        ch = fmt[i]
        i += 1
        if ch in UNSUPPORTED:
            refuse(node, "struct.%s: the format character %r (%s) is not built; use the integer, bool, "
                         "char, string and padding codes" % (fn, ch, UNSUPPORTED[ch]))
        if ch not in SUPPORTED:
            refuse(node, 'struct.%s: bad char in struct format' % fn)
        if ch in NATIVE_ONLY and not native:
            refuse(node, 'struct.%s: bad char in struct format' % fn)
        if ch == 'x':
            offset += count
            continue
        if ch == 's':
            fields.append(_Field('bytes', ch, offset, count))
            offset += count
            continue
        if ch == 'c':
            for k in range(count):
                fields.append(_Field('char', ch, offset + k, 1))
            offset += count
            continue
        size = (NAT_SIZES if native else STD_SIZES)[ch]
        if native and ch != '?':
            offset = _align(offset, size)
        signed = ch in SIGNED
        if ch == '?':
            kind = 'bool'
            lo = hi = 0
        else:
            kind = 'int'
            if signed:
                lo, hi = -(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1
            else:
                lo, hi = 0, (1 << (8 * size)) - 1
        for k in range(count):
            fields.append(_Field(kind, ch, offset, size, signed, lo, hi))
            offset += size
    if total != offset:
        refuse(node, 'struct.%s: the format could not be parsed here; report it' % fn)
    return endian, fields, total, native


def _list_expr(args):
    if len(args) == 1 and isinstance(args[0], ast.Starred):
        return ast.Call(func=ast.Name(id='list', ctx=ast.Load()), args=[args[0].value], keywords=[])
    return ast.List(elts=list(args), ctx=ast.Load())


class _Rewrite(ast.NodeTransformer):
    def __init__(self, imports, lib):
        self.imports, self.lib = imports, lib

    def visit_ExceptHandler(self, node):
        if node.type is not None:
            for each in ast.walk(node.type):
                each._ail_struct_handler = True
        return self.generic_visit(node)

    def visit_Call(self, node):
        self.generic_visit(node)
        found = self.imports.resolve(node.func)
        if found is None or found[0] != 'struct':
            return node
        attr = found[1]
        if node.keywords:
            refuse(node, 'struct.%s: keyword arguments are not built' % attr)
        if attr == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize: expected one argument')
            fmt = _literal(node.args[0], 'calcsize')
            try:
                total = _cpystruct.calcsize(fmt)
            except _cpystruct.error as exc:
                refuse(node, 'struct.calcsize: %s' % exc)
            return ast.copy_location(ast.Constant(value=total), node)
        if attr == 'pack':
            if not node.args:
                refuse(node, 'struct.pack: expected a format')
            fmt = _literal(node.args[0], 'pack')
            endian, fields, total, native = _parse(fmt, node, 'pack')
            helper = self.lib.pack_helper(fmt, fields, endian, total)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=[_list_expr(node.args[1:])], keywords=[]), node)
        if attr == 'unpack':
            if len(node.args) != 2:
                refuse(node, 'struct.unpack: expected a format and a buffer')
            fmt = _literal(node.args[0], 'unpack')
            endian, fields, total, native = _parse(fmt, node, 'unpack')
            helper = self.lib.unpack_helper(fmt, fields, endian, total, False)
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=[node.args[1]], keywords=[]), node)
        if attr == 'unpack_from':
            if len(node.args) not in (2, 3):
                refuse(node, 'struct.unpack_from: expected a format, a buffer and an optional offset')
            fmt = _literal(node.args[0], 'unpack_from')
            endian, fields, total, native = _parse(fmt, node, 'unpack_from')
            helper = self.lib.unpack_helper(fmt, fields, endian, total, True)
            args = [node.args[1], node.args[2] if len(node.args) == 3 else ast.Constant(value=0)]
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=args, keywords=[]), node)
        if attr == 'pack_into':
            if len(node.args) < 3:
                refuse(node, 'struct.pack_into: expected a format, a buffer and an offset')
            fmt = _literal(node.args[0], 'pack_into')
            endian, fields, total, native = _parse(fmt, node, 'pack_into')
            helper = self.lib.pack_into_helper(fmt, fields, endian, total)
            args = [node.args[1], node.args[2], _list_expr(node.args[3:])]
            return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                              args=args, keywords=[]), node)
        refuse(node, 'struct.%s is not built: use pack, unpack, calcsize, pack_into or unpack_from with '
                     'a literal format' % attr)
        return node

    def visit_Attribute(self, node):
        found = self.imports.resolve(node)
        if found == ('struct', 'error') and getattr(node, '_ail_struct_handler', False):
            self.lib.need_error = True
            replacement = ast.copy_location(ast.Name(id=self.lib.error_name, ctx=ast.Load()), node)
            replacement._ail_struct_error = True
            return replacement
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in self.imports.names and getattr(node, '_ail_struct_handler', False):
            module, attr = self.imports.names[node.id]
            if module == 'struct' and attr == 'error' and isinstance(node.ctx, ast.Load):
                self.lib.need_error = True
                replacement = ast.copy_location(ast.Name(id=self.lib.error_name, ctx=ast.Load()), node)
                replacement._ail_struct_error = True
                return replacement
        return node


class _Lib:
    def __init__(self, helpers, error_name):
        self.helpers = helpers
        self.error_name = error_name
        self.pack = {}
        self.unpack = {}
        self.pack_into = {}
        self.next_pack = 1
        self.next_unpack = 1
        self.next_pack_into = 1
        self.need_error = False

    def _chunks(self, fields, endian, total):
        out = []
        at = 0
        index = 0
        for field in fields:
            if field.offset > at:
                out.append('    out += b"\\x00" * %d' % (field.offset - at))
            if field.kind == 'int':
                if field.ch == 'P':
                    out.append('    out += _ail_struct_p(%s[%d], %r)' % ('vs', index, endian))
                else:
                    out.append('    out += _ail_struct_int(vs[%d], %r, %d, %r, %s, %d, %d)' % (
                        index, field.ch, field.size, endian, field.signed, field.lo, field.hi))
            elif field.kind == 'bool':
                out.append('    out += b"\\x01" if vs[%d] else b"\\x00"' % index)
            elif field.kind == 'char':
                out.append('    out += _ail_struct_char(vs[%d])' % index)
            elif field.kind == 'bytes':
                out.append('    out += _ail_struct_pad(vs[%d], %d)' % (index, field.size))
            index += 1
            at = field.offset + field.size
        if total > at:
            out.append('    out += b"\\x00" * %d' % (total - at))
        return out

    def pack_helper(self, fmt, fields, endian, total):
        if fmt in self.pack:
            return self.pack[fmt]
        name = '_ail_struct_pack_%d' % self.next_pack
        self.next_pack += 1
        count = len(fields)
        lines = ['def %s(vs):' % name,
                 '    if len(vs) != %d:' % count,
                 '        raise ' + self.error_name + '("pack expected %d items for packing (got " + str(len(vs)) + ")")' % count,
                 '    out = b""']
        lines.extend(self._chunks(fields, endian, total))
        lines.append('    return out')
        self.helpers.append('\n'.join(lines) + '\n')
        self.pack[fmt] = name
        return name

    def _read(self, field, start, endian):
        off = '%s + %d' % (start, field.offset)
        if field.kind == 'int':
            return '_ail_struct_uint(data, %s, %d, %r, %s)' % (off, field.size, endian, field.signed)
        if field.kind == 'bool':
            return '_ail_struct_bool(data, %s)' % off
        if field.kind == 'char':
            return '_ail_struct_slice(data, %s, 1)' % off
        return '_ail_struct_slice(data, %s, %d)' % (off, field.size)

    def unpack_helper(self, fmt, fields, endian, total, from_):
        key = (fmt, from_)
        if key in self.unpack:
            return self.unpack[key]
        name = '_ail_struct_unpack%s_%d' % ('_from' if from_ else '', self.next_unpack)
        self.next_unpack += 1
        lines = ['def %s(data%s):' % (name, ', offset' if from_ else '')]
        lines.append('    data = _ail_struct_data(data)')
        if from_:
            lines.append('    start = _ail_struct_start(data, %d, offset)' % total)
        else:
            lines.append('    _ail_struct_exact(data, %d)' % total)
            lines.append('    start = 0')
        values = ', '.join(self._read(f, 'start', endian) for f in fields)
        if len(fields) == 1:
            values += ','
        lines.append('    return (%s)' % values)
        self.helpers.append('\n'.join(lines) + '\n')
        self.unpack[key] = name
        return name

    def pack_into_helper(self, fmt, fields, endian, total):
        if fmt in self.pack_into:
            return self.pack_into[fmt]
        name = '_ail_struct_pack_into_%d' % self.next_pack_into
        self.next_pack_into += 1
        count = len(fields)
        lines = ['def %s(buf, offset, vs):' % name,
                 '    if len(vs) != %d:' % count,
                 '        raise ' + self.error_name + '("pack expected %d items for packing (got " + str(len(vs)) + ")")' % count,
                 '    out = b""']
        lines.extend(self._chunks(fields, endian, total))
        lines.append('    _ail_struct_pack_into(buf, offset, out)')
        self.helpers.append('\n'.join(lines) + '\n')
        self.pack_into[fmt] = name
        return name


def run(imports, tree, helpers):
    if 'struct' not in imports.modules():
        return
    error_name = '_AilStructError' if stdlib3.binds(tree, 'error') else 'error'
    lib = _Lib(helpers, error_name)
    before = len(helpers)
    _Rewrite(imports, lib).visit(tree)
    if len(helpers) > before:
        helpers.insert(before, PRELUDE.replace('_AilStructError', error_name))
    elif lib.need_error:
        helpers.insert(before, ERROR_PRELUDE.replace('_AilStructError', error_name))
    for each in ast.walk(tree):
        if getattr(each, '_ail_struct_error', False):
            continue
        if isinstance(each, ast.Attribute):
            found = imports.resolve(each)
            if found is not None and found[0] == 'struct':
                refuse(each, 'struct.%s used here is not built: use pack, unpack, calcsize, pack_into or '
                             'unpack_from with a literal format' % found[1])
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.names:
            module, attr = imports.names[each.id]
            if module == 'struct':
                refuse(each, 'struct.%s used here is not built: use pack, unpack, calcsize, pack_into or '
                             'unpack_from with a literal format' % attr)
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.aliases:
            if imports.aliases[each.id] == 'struct':
                refuse(each, 'struct used as a value is not built')
    for local in [n for n, found in imports.names.items() if found == ('struct', 'error')]:
        del imports.names[local]
    if imports.aliases.get(error_name) == 'struct':
        del imports.aliases[error_name]
    ast.fix_missing_locations(tree)
