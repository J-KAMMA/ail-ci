"""`struct` lowered onto int.to_bytes / int.from_bytes and the float bit layout.

One entry point, `rewrite_text(source, notes)`, run from ail_syntax.python_surface on the program text. A
program that imports none of the module is returned as it was written (the same string), so its C does not
change. `pack`, `unpack` and `calcsize` are lowered when the format string is a literal; every other use is
refused here by name, and the source is left as written (the import the compiler then meets is reported by
the first note).

The built format characters are x b B ? h H i I l L q Q n N e f d s p P, with the byte orders @ = < > !
and a repeat count. Native mode (@) uses the native sizes and alignment (x86-64: l/L/n/N/P are 8 bytes).
Non-native n/N/P are refused, as CPython does at runtime. A format that is not a literal string, a value
whose count does not match, and pack_into / unpack_from / Struct / iter_unpack are refused at compile time.
`struct.error` is an Exception subclass, as in CPython (it is not a ValueError).
"""
import ast

from stdlib4 import Refused, refuse

MODULE = 'struct'
FUNCS = ('pack', 'unpack', 'calcsize')
INT_CODES = 'bBhHiIlLqQnNP'
FLOAT_CODES = {'e': (10, 5, 2), 'f': (23, 8, 4), 'd': (52, 11, 8)}
UNIT = {'x': 1, 'b': 1, 'B': 1, '?': 1, 'c': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4,
        'l': 4, 'L': 4, 'q': 8, 'Q': 8, 'n': 8, 'N': 8, 'P': 8, 'e': 2, 'f': 4, 'd': 8,
        's': 1, 'p': 1}
NATIVE = dict(UNIT, l=8, L=8, n=8, N=8, P=8)


class Binder:
    """The names a program binds to `struct`, found at the top level."""

    def __init__(self, tree):
        self.aliases = {}
        self.names = {}
        self.nodes = []
        body = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name == MODULE:
                        self.aliases[alias.asname or alias.name] = MODULE
                    else:
                        rest.append(alias)
                if len(rest) != len(node.names):
                    self.nodes.append(node)
                    if rest:
                        node.names = rest
                        body.append(node)
                    continue
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == MODULE:
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from struct import *: name what you use')
                    self.names[alias.asname or alias.name] = (MODULE, alias.name)
                self.nodes.append(node)
                continue
            body.append(node)
        tree.body = body
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)) or node in self.nodes:
                continue
            if isinstance(node, ast.Import):
                if any(alias.name == MODULE for alias in node.names):
                    refuse(node, 'import struct: place the import at the top of the file, not inside a function or block')
            elif not node.level and node.module == MODULE:
                refuse(node, 'from struct import ...: place the import at the top of the file, not inside a function or block')

    def resolve(self, node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.aliases.get(node.value.id)
            if module is not None:
                return module, node.attr
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        return None


def literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def size_of(code, native):
    return (NATIVE if native else UNIT)[code]


def parse(text, node):
    """(fields, total, order): a field is (code, count, unit, offset), and a pad field is (code, count)."""
    endian = '@'
    index = 0
    if text[:1] in ('@', '=', '<', '>', '!'):
        endian = text[0]
        index = 1
    native = endian == '@'
    order = 1 if endian in ('>', '!') else 0
    fields = []
    offset = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        start = index
        while index < len(text) and text[index].isdigit():
            index += 1
        count = int(text[start:index]) if index > start else 1
        if index >= len(text):
            refuse(node, 'struct: repeat count given without format specifier')
        code = text[index]
        index += 1
        if code == 'x':
            if count:
                fields.append((code, count))
                offset += count
            continue
        if code == 's' or code == 'p':
            fields.append((code, count, count, offset))
            offset += count
            continue
        if code not in UNIT:
            refuse(node, "struct: format character %r is not built: use one of x b B ? h H i I l L q Q n N e f d s p P"
                   % code)
        if code in 'nNP' and not native:
            refuse(node, "struct: format character %r needs the native mode @ (CPython refuses it in =, <, > and !)"
                   % code)
        if count == 0:
            if native:
                unit = size_of(code, native)
                offset = (offset + unit - 1) // unit * unit
            continue
        unit = size_of(code, native)
        if native and code not in 'c?':
            offset = (offset + unit - 1) // unit * unit
        fields.append((code, count, unit, offset))
        offset += unit * count
    return fields, offset, order, native


class Lower(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.helpers = []
        self.serial = 0

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.binder.names.get(node.id) == (MODULE, 'error'):
            return ast.Name(id='error', ctx=ast.Load())
        return node

    def visit_Attribute(self, node):
        self.generic_visit(node)
        found = self.binder.resolve(node)
        if found == (MODULE, 'error'):
            return ast.Name(id='error', ctx=ast.Load())
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        found = self.binder.resolve(node.func)
        if found is None or found[0] != MODULE:
            return node
        name = found[1]
        if name not in FUNCS:
            refuse(node, 'struct.%s is not built: this compiler builds struct.pack, struct.unpack and '
                         'struct.calcsize with a literal format string' % name)
        if node.keywords:
            refuse(node, 'struct.%s: use positional arguments only' % name)
        if not node.args:
            refuse(node, 'struct.%s: the format string is required' % name)
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            refuse(node, 'struct.%s: unpacked values are not built; pass the values one by one' % name)
        fmt = literal(node.args[0])
        if fmt is None:
            refuse(node, 'struct.%s: the format string must be a literal string, so the bytes can be laid out '
                         'when the program is compiled' % name)
        fields, total, order, native = parse(fmt, node)
        if name == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize: one argument, the format string')
            return ast.copy_location(ast.Constant(value=total), node)
        if name == 'pack':
            return self.lower_pack(node, fmt, fields, total, order, native)
        return self.lower_unpack(node, fmt, fields, total, order)

    def lower_pack(self, node, fmt, fields, total, order, native):
        values = node.args[1:]
        needed = 0
        for field in fields:
            if field[0] == 'x':
                continue
            if field[0] in 'sp':
                needed += 1
            else:
                needed += field[1]
        if len(values) != needed:
            refuse(node, 'struct.pack: format %r needs %d value(s), got %d' % (fmt, needed, len(values)))
        parts = []
        cursor = 0
        position = 0
        for field in fields:
            code = field[0]
            count = field[1]
            if code == 'x':
                parts.append('b"\\x00" * %d' % count)
                position += count
                continue
            offset = field[3]
            if offset > position:
                parts.append('b"\\x00" * %d' % (offset - position))
                position = offset
            if code in 'sp':
                value = ast.unparse(values[cursor])
                cursor += 1
                if code == 's':
                    parts.append('_ail_st_pack_s(%s, %d)' % (value, count))
                else:
                    parts.append('_ail_st_pack_p(%s, %d)' % (value, count))
                position += count
                continue
            unit = field[2]
            signed = 1 if code in 'bhilqn' else 0
            for _ in range(count):
                value = ast.unparse(values[cursor])
                cursor += 1
                if code == 'c':
                    parts.append('_ail_st_pack_c(%s)' % value)
                elif code == '?':
                    parts.append('_ail_st_pack_bool(%s)' % value)
                elif code == 'd':
                    parts.append('_ail_st_pack_d(%s, %d)' % (value, order))
                elif code in 'ef':
                    mbits, ebits, width = FLOAT_CODES[code]
                    inf_on_overflow = 1 if native and code == 'f' else 0
                    parts.append('_ail_st_pack_float(%s, %d, %d, %d, %d, "%s", %d)'
                                 % (value, mbits, ebits, width, order, code, inf_on_overflow))
                else:
                    parts.append('_ail_st_pack_int(%s, %d, %d, %d, "%s")'
                                 % (value, unit, signed, order, code))
            position += unit * count
        if total > position:
            parts.append('b"\\x00" * %d' % (total - position))
        if not parts:
            return ast.copy_location(ast.parse('b""', mode='eval').body, node)
        return ast.copy_location(ast.parse('(' + ' + '.join(parts) + ')', mode='eval').body, node)

    def lower_unpack(self, node, fmt, fields, total, order):
        if len(node.args) != 2:
            refuse(node, 'struct.unpack: two arguments, the format string and the bytes')
        data = ast.unparse(node.args[1])
        exprs = []
        types = []
        for field in fields:
            code = field[0]
            if code == 'x':
                continue
            count = field[1]
            if code in 'sp':
                if code == 'p' and count == 0:
                    refuse(node, "struct.unpack: a zero-count 'p' field is not built (CPython 3.12 stops with "
                                 "SystemError: Negative size passed to PyBytes_FromStringAndSize)")
                if code == 's':
                    exprs.append('_ail_st_unpack_s(data, %d, %d)' % (field[3], count))
                else:
                    exprs.append('_ail_st_unpack_p(data, %d, %d)' % (field[3], count))
                types.append('bytes')
                continue
            unit = field[2]
            for index in range(count):
                offset = field[3] + index * unit
                if code == 'c':
                    exprs.append('_ail_st_unpack_c(data, %d)' % offset)
                    types.append('bytes')
                elif code == '?':
                    exprs.append('_ail_st_unpack_bool(data, %d)' % offset)
                    types.append('bool')
                elif code == 'd':
                    exprs.append('_ail_st_unpack_d(data, %d, %d)' % (offset, order))
                    types.append('float')
                elif code in FLOAT_CODES:
                    mbits, ebits, width = FLOAT_CODES[code]
                    exprs.append('_ail_st_unpack_float(data, %d, %d, %d, %d, %d)'
                                 % (offset, width, mbits, ebits, order))
                    types.append('float')
                else:
                    signed = 1 if code in 'bhilqn' else 0
                    exprs.append('_ail_st_unpack_int(data, %d, %d, %d, %d, "%s")'
                                 % (offset, unit, signed, order, code))
                    types.append('int')
        name = '_ail_st_unpack_%d' % self.serial
        self.serial += 1
        items = ', '.join(exprs)
        if len(exprs) == 1:
            items += ','
        if types:
            annotation = 'tuple[%s]' % ', '.join(types)
        else:
            annotation = 'tuple[()]'
        self.helpers.append('def %s(data: bytes) -> %s:\n'
                            '    if len(data) != %d:\n'
                            '        raise error("unpack requires a buffer of %d bytes")\n'
                            '    return (%s)\n' % (name, annotation, total, total, items))
        return ast.copy_location(ast.parse('%s(%s)' % (name, data), mode='eval').body, node)


HELPERS = r"""
class error(Exception):
    pass


def _ail_st_order(order: int) -> str:
    if order:
        return "big"
    return "little"


def _ail_st_round(value: float) -> int:
    whole = int(value)
    rest = value - whole
    if rest > 0.5 or (rest == 0.5 and (whole & 1)):
        whole += 1
    return whole


def _ail_st_negative(value: float) -> bool:
    if value < 0.0:
        return True
    if value == 0.0 or value != value:
        return str(value)[:1] == "-"
    return False


def _ail_st_log2(value: float) -> int:
    exponent = 0
    working = value
    if working >= 1.0:
        while working >= 2.0:
            working = working / 2.0
            exponent += 1
    else:
        while working < 1.0:
            working = working * 2.0
            exponent -= 1
    return exponent


def _ail_st_pack_int(value: int, width: int, signed: int, order: int, code: str) -> bytes:
    if not isinstance(value, int):
        raise error("required argument is not an integer")
    if code == 'P':
        if value < 0:
            return value.to_bytes(8, _ail_st_order(order), signed=True)
        if value > 9223372036854775807:
            raise error("'P' format requires 0 <= number <= 18446744073709551615")
        return value.to_bytes(8, _ail_st_order(order), signed=False)
    if signed:
        if width == 8:
            low = -9223372036854775808
            high = 9223372036854775807
            shown = '%d' % high
        else:
            high = (1 << (8 * width - 1)) - 1
            low = -high - 1
            shown = '%d' % high
    else:
        low = 0
        if width == 8:
            high = 9223372036854775807
            shown = '18446744073709551615'
        else:
            high = (1 << (8 * width)) - 1
            shown = '%d' % high
    if value < low or value > high:
        raise error("'%s' format requires %d <= number <= %s" % (code, low, shown))
    if width == 8 and signed and value < 0:
        return value.to_bytes(8, _ail_st_order(order), signed=True)
    if value < 0:
        value += 1 << (8 * width)
    return value.to_bytes(width, _ail_st_order(order), signed=False)


def _ail_st_unpack_int(data: bytes, offset: int, width: int, signed: int, order: int, code: str) -> int:
    if signed or width == 8:
        return int.from_bytes(data[offset:offset + width], _ail_st_order(order), signed=True)
    return int.from_bytes(data[offset:offset + width], _ail_st_order(order), signed=False)


def _ail_st_pack_bool(value) -> bytes:
    if value:
        return b"\x01"
    return b"\x00"


def _ail_st_unpack_bool(data: bytes, offset: int) -> bool:
    if data[offset]:
        return True
    return False


def _ail_st_pack_c(value: bytes) -> bytes:
    if not isinstance(value, bytes):
        raise error("char format requires a bytes object of length 1")
    if len(value) != 1:
        raise error("char format requires a bytes object of length 1")
    return bytes(value)


def _ail_st_unpack_c(data: bytes, offset: int) -> bytes:
    return data[offset:offset + 1]


def _ail_st_pack_s(value: bytes, count: int) -> bytes:
    if not (isinstance(value, bytes) or isinstance(value, bytearray)):
        raise error("argument for 's' must be a bytes object")
    data = bytes(value)
    if len(data) >= count:
        return data[:count]
    return data + b"\x00" * (count - len(data))


def _ail_st_pack_p(value: bytes, count: int) -> bytes:
    if not (isinstance(value, bytes) or isinstance(value, bytearray)):
        raise error("argument for 'p' must be a bytes object")
    data = bytes(value)
    if count == 0:
        return b""
    length = len(data)
    if length > 255:
        length = 255
    if length > count - 1:
        length = count - 1
    return length.to_bytes(1, "little") + data[:length] + b"\x00" * (count - 1 - length)


def _ail_st_unpack_s(data: bytes, offset: int, count: int) -> bytes:
    return data[offset:offset + count]


def _ail_st_unpack_p(data: bytes, offset: int, count: int) -> bytes:
    if count == 0:
        return b""
    length = data[offset]
    if length >= count:
        length = count - 1
    return data[offset + 1:offset + 1 + length]


def _ail_st_finite(value: float) -> int:
    if value != value:
        return 1
    if value == float("inf") or value == float("-inf"):
        return 2
    return 0


def _ail_st_f2bits(value: float, mbits: int, ebits: int, code: str, inf_on_overflow: int) -> int:
    state = _ail_st_finite(value)
    sign = 1 if _ail_st_negative(value) else 0
    signbit = sign << (mbits + ebits)
    maxexp = (1 << ebits) - 1
    if state == 1:
        return signbit | (maxexp << mbits) | (1 << (mbits - 1))
    if state == 2:
        return signbit | (maxexp << mbits)
    absolute = abs(value)
    if absolute == 0.0:
        return signbit
    exponent = _ail_st_log2(absolute)
    fraction = absolute / (2.0 ** exponent)
    if fraction >= 2.0:
        fraction = fraction / 2.0
        exponent += 1
    elif fraction < 1.0:
        fraction = fraction * 2.0
        exponent -= 1
    target = exponent + ((1 << (ebits - 1)) - 1)
    mantissa = _ail_st_round((fraction - 1.0) * float(1 << mbits))
    if mantissa == (1 << mbits):
        mantissa = 0
        target += 1
    if target >= maxexp:
        if inf_on_overflow:
            return signbit | (maxexp << mbits)
        raise OverflowError("float too large to pack with %s format" % code)
    if target <= 0:
        scaled = _ail_st_round(absolute / (2.0 ** (2 - (1 << (ebits - 1)) - mbits)))
        return signbit | scaled
    return signbit | (target << mbits) | mantissa


def _ail_st_bits2f(bits: int, mbits: int, ebits: int) -> float:
    sign = (bits >> (mbits + ebits)) & 1
    exponent = (bits >> mbits) & ((1 << ebits) - 1)
    mantissa = bits & ((1 << mbits) - 1)
    maxexp = (1 << ebits) - 1
    if exponent == maxexp:
        if mantissa != 0:
            return float("nan")
        if sign:
            return float("-inf")
        return float("inf")
    if exponent == 0:
        if mantissa == 0:
            if sign:
                return -0.0
            return 0.0
        value = float(mantissa) * (2.0 ** (2 - (1 << (ebits - 1)) - mbits))
        if sign:
            return -value
        return value
    value = float((1 << mbits) + mantissa) * (2.0 ** (exponent + 1 - (1 << (ebits - 1)) - mbits))
    if sign:
        return -value
    return value


def _ail_st_pack_float(value: float, mbits: int, ebits: int, width: int, order: int, code: str, inf_on_overflow: int) -> bytes:
    bits = _ail_st_f2bits(value, mbits, ebits, code, inf_on_overflow)
    return bits.to_bytes(width, _ail_st_order(order), signed=False)


def _ail_st_unpack_float(data: bytes, offset: int, width: int, mbits: int, ebits: int, order: int) -> float:
    bits = int.from_bytes(data[offset:offset + width], _ail_st_order(order), signed=False)
    return _ail_st_bits2f(bits, mbits, ebits)


def _ail_st_f64bits(value: float) -> int:
    state = _ail_st_finite(value)
    sign = 1 if _ail_st_negative(value) else 0
    signbit = -9223372036854775808 if sign else 0
    if state == 1:
        return signbit | (0x7ff << 52) | 0x8000000000000
    if state == 2:
        return signbit | (0x7ff << 52)
    absolute = abs(value)
    if absolute == 0.0:
        return signbit
    exponent = _ail_st_log2(absolute)
    if exponent < -1022:
        mantissa = _ail_st_round(absolute / (2.0 ** -1074))
        return signbit | mantissa
    fraction = absolute / (2.0 ** exponent)
    if fraction >= 2.0:
        fraction = fraction / 2.0
        exponent += 1
    elif fraction < 1.0:
        fraction = fraction * 2.0
        exponent -= 1
    mantissa = _ail_st_round((fraction - 1.0) * float(1 << 52))
    if mantissa == (1 << 52):
        mantissa = 0
        exponent += 1
    if exponent >= 1024:
        return signbit | (0x7ff << 52)
    return signbit | ((exponent + 1023) << 52) | mantissa


def _ail_st_pack_d(value: float, order: int) -> bytes:
    return _ail_st_f64bits(value).to_bytes(8, _ail_st_order(order), signed=True)


def _ail_st_unpack_d(data: bytes, offset: int, order: int) -> float:
    bits = int.from_bytes(data[offset:offset + 8], _ail_st_order(order), signed=True)
    sign = 1 if bits < 0 else 0
    exponent = (bits >> 52) & 0x7ff
    mantissa = bits & 0xfffffffffffff
    if exponent == 0x7ff:
        if mantissa != 0:
            return float("nan")
        if sign:
            return float("-inf")
        return float("inf")
    if exponent == 0:
        if mantissa == 0:
            if sign:
                return -0.0
            return 0.0
        value = float(mantissa) * (2.0 ** -1074)
        if sign:
            return -value
        return value
    value = float((1 << 52) + mantissa) * (2.0 ** (exponent - 1023 - 52))
    if sign:
        return -value
    return value
"""



def leftovers(tree, binder):
    for each in ast.walk(tree):
        found = binder.resolve(each) if isinstance(each, ast.Attribute) else None
        if found is not None and found[0] == MODULE:
            if found[1] == 'error':
                continue
            if found[1] in FUNCS:
                refuse(each, 'struct.%s used as a value is not built: call it with a literal format string' % found[1])
            refuse(each, 'struct.%s is not built: this compiler builds struct.pack, struct.unpack and struct.calcsize'
                   % found[1])
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load):
            found = binder.names.get(each.id)
            if found == (MODULE, 'error'):
                continue
            if found is not None:
                refuse(each, 'struct.%s used here is not built' % found[1])
            if each.id in binder.aliases:
                refuse(each, 'struct used as a value is not built')


def rewrite_text(source, notes=None):
    """The program text with `struct` lowered; the source as written (and `notes` filled) when a use is not built."""
    if MODULE not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    try:
        binder = Binder(tree)
        if not binder.nodes:
            return source
        lower = Lower(binder)
        tree = lower.visit(tree)
        leftovers(tree, binder)
        added = ast.parse(HELPERS).body
        for chunk in lower.helpers:
            added.extend(ast.parse(chunk).body)
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body[index:index] = added
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return text.rstrip('\n') + '\n'
