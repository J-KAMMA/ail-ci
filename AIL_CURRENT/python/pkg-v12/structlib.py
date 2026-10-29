"""`struct` for the Python surface: pack, unpack, unpack_from and calcsize over a literal format.

One entry point, `rewrite_text(source, notes)`, run from ail_syntax.python_surface before the other source
passes.  A program that does not import `struct` is returned as the same string, so its C does not change.
The format string must be a literal: the fields are laid out here, at compile time, and each value is
packed/unpacked by a helper (integer fields through int.to_bytes / int.from_bytes).  `calcsize` becomes
an integer constant.

The format characters built are `x c b B ? h H i I l L q Q n N P s`, in standard mode (`<`, `>`, `!`,
`=`) and native mode (`@` or no prefix, with the Linux x86-64 sizes and alignment).  `f`, `e` and `d`
(16/32/64-bit floats), `p`, dynamic format strings, `Struct`, `iter_unpack`, `pack_into` and the remaining
names are refused here by name.  `struct.error` is `ValueError` in a compiled program (and a failed pack raises
ValueError with CPython's text).
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib5
from stdlib4 import Refused, refuse

HANDLED = ('pack', 'unpack', 'unpack_from', 'calcsize', 'error')
STANDARD = set('x c b B ? h H i I l L q Q s d'.split())
NATIVE = STANDARD | set('n N P'.split())
SIZES = {'x': 1, 'c': 1, 'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4,
         'q': 8, 'Q': 8, 'n': 8, 'N': 8, 'P': 8, 's': 1, 'd': 8}
NATIVE_SIZES = dict(SIZES, l=8, L=8)
SIGNED = set('b h i l q n'.split())
FLOAT_UNBUILT = {'f': "'f' (float32)", 'e': "'e' (float16)", 'd': "'d' (float64)"}
BUILT = "x c b B ? h H i I l L q Q n N P s"


class Field:
    def __init__(self, char, count, offset, width, signed):
        self.char, self.count, self.offset, self.width, self.signed = char, count, offset, width, signed


class Layout:
    def __init__(self, fields, size, order, order_int):
        self.fields, self.size, self.order, self.order_int = fields, size, order, order_int


def literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def layout(fmt, node):
    """The fields and size of `fmt`, or a refusal at `node`."""
    i = 0
    native = True
    if fmt and fmt[0] in '<>!=':
        native = False
        prefix = fmt[0]
        i = 1
    elif fmt and fmt[0] == '@':
        native = True
        prefix = '@'
        i = 1
    else:
        native = True
        prefix = '@'
    order = 'big' if prefix in '>!' else 'little'
    order_int = 1 if order == 'big' else 0
    sizes = NATIVE_SIZES if native else SIZES
    allowed = NATIVE if native else STANDARD
    fields = []
    offset = 0
    while i < len(fmt):
        if fmt[i].isspace():
            i += 1
            continue
        j = i
        while j < len(fmt) and fmt[j].isdigit():
            j += 1
        count = int(fmt[i:j]) if j > i else 1
        if j >= len(fmt):
            refuse(node, "struct format %r: a repeat count must be followed by a format character" % fmt)
        char = fmt[j]
        i = j + 1
        if char in FLOAT_UNBUILT:
            refuse(node, "struct %s is not built: keep the eight (or four) bytes as unsigned integer "
                         "fields and convert where the program needs a float" % FLOAT_UNBUILT[char])
        if char not in allowed:
            refuse(node, "struct format character %r is not built; the characters built here are %s"
                   % (char, BUILT))
        size = sizes[char]
        if char == 's':
            align = 1
            width = count
            if native:
                offset = (offset + align - 1) // align * align
            fields.append(Field(char, count, offset, width, False))
            offset += width
        elif char == 'x':
            if native:
                offset = (offset + 1 - 1) // 1 * 1
            offset += count
        else:
            align = size if native else 1
            if native:
                offset = (offset + align - 1) // align * align
            for _ in range(count):
                fields.append(Field(char, 1, offset, size, char in SIGNED))
                offset += size
    return Layout(fields, offset, order, order_int)


class Lower(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.pending = []
        self.serial = 0

    def temp(self):
        self.serial += 1
        return '_ail_struct_%d' % self.serial

    def assign(self, name, value):
        self.pending.append(ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value))

    def block(self, body):
        out = []
        for statement in body:
            saved, self.pending = self.pending, []
            statement = self.visit(statement)
            out.extend(self.pending)
            out.append(statement)
            self.pending = saved
        return out

    def statement(self, node):
        fields = list(ast.iter_fields(node))
        body_names = {'body', 'orelse', 'finalbody'}
        for name, value in fields:
            if name in body_names and isinstance(value, list):
                setattr(node, name, self.block(value))
            elif isinstance(value, list):
                setattr(node, name, [self.visit(each) if isinstance(each, ast.AST) else each for each in value])
            elif isinstance(value, ast.AST):
                setattr(node, name, self.visit(value))
        return node

    def visit_Module(self, node):
        node.body = self.block(node.body)
        return node

    def visit_ExceptHandler(self, node):
        return self.statement(node)

    def visit_MatchCase(self, node):
        return self.statement(node)

    def generic_visit(self, node):
        if isinstance(node, ast.stmt) or node.__class__.__name__ in ('ExceptHandler', 'MatchCase'):
            return self.statement(node)
        return super().generic_visit(node)

    def visit_Attribute(self, node):
        if self.binder.attr(node) == 'error':
            return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.binder.attr(node) == 'error':
            return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        found = self.binder.attr(node.func)
        if found == 'pack':
            return self.pack(node)
        if found in ('unpack', 'unpack_from'):
            return self.unpack(node, found == 'unpack_from')
        if found == 'calcsize':
            return self.calcsize(node)
        return node

    def args(self, node, count, what):
        if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
            refuse(node, '%s with keywords or *args is not built: pass the values positionally' % what)
        if len(node.args) != count:
            refuse(node, '%s takes %d positional arguments here, got %d' % (what, count, len(node.args)))
        return node.args

    def calcsize(self, node):
        args = self.args(node, 1, 'struct.calcsize')
        fmt = literal(args[0])
        if fmt is None:
            refuse(node, 'struct.calcsize needs a string literal format: the layout is worked out at compile time')
        return ast.copy_location(ast.Constant(value=layout(fmt, node).size), node)

    def pack(self, node):
        if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
            refuse(node, 'struct.pack with keywords or *args is not built: pass the values positionally')
        args = node.args
        if not args:
            refuse(node, 'struct.pack needs a format string')
        fmt = literal(args[0])
        if fmt is None:
            refuse(node, 'struct.pack needs a string literal format: the layout is worked out at compile time')
        lay = layout(fmt, node)
        values = args[1:]
        if len(values) != len(lay.fields):
            refuse(node, "struct.pack(%r) needs %d value%s, got %d"
                   % (fmt, len(lay.fields), '' if len(lay.fields) == 1 else 's', len(values)))
        # the x fields and the native padding are filled in around the values, in order
        parts = []
        value = 0
        cursor = 0
        for field in lay.fields:
            if field.offset > cursor:
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_pad', ctx=ast.Load()),
                                      args=[ast.Constant(value=field.offset - cursor)], keywords=[]))
            char = field.char
            arg = values[value] if char != 'x' else None
            if char != 'x':
                value += 1
            if char == 'x':
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_pad', ctx=ast.Load()),
                                      args=[ast.Constant(value=field.width)], keywords=[]))
            elif char == 's':
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_string', ctx=ast.Load()),
                                      args=[arg, ast.Constant(value=field.width)], keywords=[]))
            elif char == 'c':
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_char', ctx=ast.Load()), args=[arg], keywords=[]))
            elif char == '?':
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_bool', ctx=ast.Load()), args=[arg], keywords=[]))
            else:
                if char in SIGNED:
                    if field.width == 8:
                        lo, hi = -9223372036854775807 - 1, 9223372036854775807
                    else:
                        lo, hi = -(1 << (field.width * 8 - 1)), (1 << (field.width * 8 - 1)) - 1
                    label = "'%s' format requires %d <= number <= %d" % (char, lo, hi)
                else:
                    hi = None if field.width == 8 else (1 << (field.width * 8)) - 1
                    label = ("'%s' format requires 0 <= number <= %d" % (char, hi) if hi is not None
                             else "'%s' format requires 0 <= number <= 18446744073709551615" % char)
                parts.append(ast.Call(func=ast.Name(id='_ail_struct_int', ctx=ast.Load()),
                                      args=[arg, ast.Constant(value=field.width),
                                            ast.Constant(value=field.signed), ast.Constant(value=lay.order),
                                            ast.Constant(value=label)], keywords=[]))
            cursor = field.offset + field.width
        if lay.size > cursor:
            parts.append(ast.Call(func=ast.Name(id='_ail_struct_pad', ctx=ast.Load()),
                                  args=[ast.Constant(value=lay.size - cursor)], keywords=[]))
        if not parts:
            return ast.copy_location(ast.Constant(value=b''), node)
        return ast.copy_location(ast.Call(func=ast.Attribute(value=ast.Constant(value=b''), attr='join', ctx=ast.Load()),
                                          args=[ast.List(elts=parts, ctx=ast.Load())], keywords=[]), node)

    def unpack(self, node, from_offset):
        if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
            refuse(node, 'struct.unpack%s with keywords or *args is not built' % ('_from' if from_offset else ''))
        args = node.args
        if (from_offset and len(args) not in (2, 3)) or (not from_offset and len(args) != 2):
            refuse(node, 'struct.unpack%s takes %s' % ('_from' if from_offset else '',
                                                       'a format, a buffer and an offset' if from_offset
                                                       else 'a format and a buffer'))
        fmt = literal(args[0])
        if fmt is None:
            refuse(node, 'struct.unpack%s needs a string literal format: the layout is worked out at compile time'
                   % ('_from' if from_offset else ''))
        lay = layout(fmt, node)
        offset = args[2] if from_offset and len(args) == 3 else ast.Constant(value=0)
        name = self.temp()
        starts = ast.List(elts=[ast.Constant(value=f.offset) for f in lay.fields], ctx=ast.Load())
        widths = ast.List(elts=[ast.Constant(value=f.width) for f in lay.fields], ctx=ast.Load())
        pieces = ast.Call(func=ast.Name(id='_ail_struct_pieces', ctx=ast.Load()),
                          args=[args[1], offset, starts, widths, ast.Constant(value=lay.size),
                                ast.Constant(value=1 if from_offset else 0)], keywords=[])
        self.assign(name, pieces)
        out = []
        for index, field in enumerate(lay.fields):
            piece = ast.Subscript(value=ast.Name(id=name, ctx=ast.Load()), slice=ast.Constant(value=index),
                                  ctx=ast.Load())
            if field.char == '?':
                out.append(ast.Call(func=ast.Name(id='_ail_struct_bool_from', ctx=ast.Load()), args=[piece],
                                    keywords=[]))
            elif field.char in ('c', 's'):
                out.append(piece)
            else:
                out.append(ast.Call(func=ast.Name(id='_ail_struct_sint' if field.signed else '_ail_struct_uint',
                                                  ctx=ast.Load()),
                                    args=[piece, ast.Constant(value=lay.order)], keywords=[]))
        return ast.copy_location(ast.Tuple(elts=out, ctx=ast.Load()), node)


PRELUDE = '''def _ail_struct_pad(width: int) -> bytes:
    return b"\\x00" * width


def _ail_struct_int(value: int, width: int, signed: bool, order: str, label: str) -> bytes:
    if isinstance(value, bool):
        value = 1 if value else 0
    elif not isinstance(value, int):
        raise ValueError("required argument is not an integer")
    if signed:
        if width == 8:
            lo = -9223372036854775807 - 1
            hi = 9223372036854775807
        else:
            lo = -(1 << (width * 8 - 1))
            hi = (1 << (width * 8 - 1)) - 1
    else:
        lo = 0
        if width < 8:
            hi = (1 << (width * 8)) - 1
        else:
            hi = 9223372036854775807
    if value < lo or value > hi:
        raise ValueError(label)
    return value.to_bytes(width, order, signed=signed)


def _ail_struct_bool(value: int) -> bytes:
    if value:
        return b"\\x01"
    return b"\\x00"


def _ail_struct_char(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != 1:
        raise ValueError("char format requires a bytes object of length 1")
    return value


def _ail_struct_string(value: bytes, width: int) -> bytes:
    if not (isinstance(value, bytes) or isinstance(value, bytearray)):
        raise ValueError("argument for 's' must be a bytes object")
    if isinstance(value, bytearray):
        value = bytes(value)
    if len(value) >= width:
        return value[:width]
    return value + b"\\x00" * (width - len(value))


def _ail_struct_pieces(data: bytes, offset: int, starts: list[int], widths: list[int], size: int,
                       from_offset: int) -> list[bytes]:
    if from_offset == 0:
        if len(data) != size:
            raise ValueError("unpack requires a buffer of %d bytes" % size)
        base = 0
    else:
        if offset < 0:
            base = len(data) + offset
            if base < 0:
                raise ValueError("offset %d out of range for %d-byte buffer" % (offset, len(data)))
            if base + size > len(data):
                raise ValueError("not enough data to unpack %d bytes at offset %d" % (size, offset))
        else:
            base = offset
            if base + size > len(data):
                raise ValueError("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at offset %d (actual buffer size is %d)"
                                 % (base + size, size, offset, len(data)))
    out = []
    i = 0
    while i < len(widths):
        out.append(data[base + starts[i]:base + starts[i] + widths[i]])
        i += 1
    return out


def _ail_struct_uint(piece: bytes, order: str) -> int:
    return int.from_bytes(piece, order, signed=False)


def _ail_struct_sint(piece: bytes, order: str) -> int:
    return int.from_bytes(piece, order, signed=True)


def _ail_struct_bool_from(piece: bytes) -> bool:
    return piece != b"\\x00"

'''


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if 'struct' not in stdlib5.imported_modules(tree):
        return source
    try:
        binder = stdlib5.take_imports(tree, 'struct', set(HANDLED), unknown='pack, unpack, unpack_from, calcsize and error are built')
        if not binder:
            return source
        lower = Lower(binder)
        tree = lower.visit(tree)
        stdlib5.leftover(tree, binder, 'struct.pack, unpack, unpack_from, calcsize and error are the names built')
        stdlib5.insert_after_imports(tree, PRELUDE)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or report it'
                          % (type(exc).__name__, exc)))
        return source
