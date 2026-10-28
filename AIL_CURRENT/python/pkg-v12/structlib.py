"""Library batch 6: `struct` pack / unpack / unpack_from / calcsize for a literal format.

`rewrite_text(source, notes)` runs from ail_syntax.python_surface after the module merge, so a call
spelled `struct.pack(...)` is already the merged `struct__pack(...)`. A literal format is parsed
here with CPython's own `struct.calcsize` as the check; a format with a byte of padding or the
standard integer / float / string codes is lowered onto ordinary byte, int and list operations.
`struct.py` (bundled) supplies only the IEEE-754 conversions, through its C glue.

Built: pack(fmt, ...), `a, b, ... = unpack(fmt, data)` and `a, b, ... = unpack_from(fmt, data[, off])`
in a tuple assignment, and calcsize(fmt). Everything else (a computed format, Struct, pack_into,
iter_unpack, an unpack result used as a value) is refused here by name.
"""
import ast
import struct as _struct
import sys
import textwrap
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from stdlib4 import Refused, refuse
from stdlib5 import insert_after_imports

SUPPORTED = 'xcbB?hHiIlLqQefdspP'
FLOAT_KINDS = {'e': 'half', 'f': 'float', 'd': 'double'}
INT_KINDS = {'b': ('int', True), 'B': ('uint', False), 'h': ('int', True), 'H': ('uint', False),
             'i': ('int', True), 'I': ('uint', False), 'l': ('int', True), 'L': ('uint', False),
             'q': ('int', True), 'Q': ('uint', False), 'P': ('uint', False)}
NOTE = ('struct.pack with a literal format, calcsize(fmt), and `a, b, ... = unpack(fmt, data)` / '
        '`unpack_from(fmt, data[, off])` are built; a computed format, Struct, pack_into, iter_unpack '
        'and an unpack result used as a value are not')


def _name(prefix, number):
    return ast.Name(id='%s%d' % (prefix, number), ctx=ast.Load())


def _order(prefix):
    if prefix in ('>', '!'):
        return 'big'
    if prefix == '<':
        return 'little'
    return sys.byteorder


def _pieces(fmt, node):
    """Parse `fmt` into (prefix, order, fields, size). A field is (kind, offset, size, signed, count)."""
    if not isinstance(fmt, str):
        refuse(node, 'struct: the format must be a string literal: %s' % NOTE)
    if not fmt:
        return '@', sys.byteorder, [], 0
    prefix = fmt[0] if fmt[0] in '@=<>!' else '@'
    body = fmt[1:] if fmt[0] in '@=<>!' else fmt
    native = prefix in ('@',)
    try:
        total = _struct.calcsize(fmt)
    except (struct_error_types()):
        refuse(node, 'struct: %r is not a valid format: %s' % (fmt, NOTE))
    fields = []
    offset = 0
    index = 0
    count = None
    while index < len(body):
        ch = body[index]
        if ch.isspace():
            index += 1
            continue
        if ch.isdigit():
            count = (count or 0) * 10 + int(ch)
            index += 1
            continue
        repeat = 1 if count is None else count
        count = None
        if ch not in SUPPORTED:
            refuse(node, 'struct: the format %r uses %r, which is not built; built bytes are %s: %s'
                   % (fmt, ch, SUPPORTED, NOTE))
        if ch == 'p' and repeat == 0:
            refuse(node, 'struct: the format %r uses a zero-length pascal string, whose empty result '
                         'CPython cannot read back: %s' % (fmt, NOTE))
        if ch == 'x':
            fields.append(('x', offset, repeat, False, repeat))
            offset += repeat
        elif ch in ('s', 'p'):
            fields.append((ch, offset, repeat, False, repeat))
            offset += repeat
        elif ch == 'c':
            for _ in range(repeat):
                fields.append(('c', offset, 1, False, 1))
                offset += 1
        else:
            size = _struct.calcsize(prefix + ch) if native else _struct.calcsize('=' + ch)
            for _ in range(repeat):
                if native and ch not in ('s', 'p', 'x'):
                    align = size
                    pad = (-offset) % align
                    if pad:
                        fields.append(('x', offset, pad, False, pad))
                        offset += pad
                if ch == '?':
                    fields.append(('?', offset, 1, False, 1))
                elif ch in FLOAT_KINDS:
                    fields.append((ch, offset, size, False, 1))
                else:
                    kind, signed = INT_KINDS[ch]
                    fields.append((ch, offset, size, signed, 1))
                offset += size
        index += 1
    if offset != total:
        refuse(node, 'struct: the format %r is not built here (its size is %d, the layout this '
                     'pass builds is %d): %s' % (fmt, total, offset, NOTE))
    return prefix, _order(prefix), fields, total


def struct_error_types():
    try:
        return (_struct.error,)
    except AttributeError:                 # pragma: no cover - every CPython has struct.error
        return (ValueError,)


def _used(node, prefix):
    return isinstance(node, ast.Name) and node.id.startswith(prefix)


def _attr(node, prefix):
    if isinstance(node, ast.Name) and node.id.startswith(prefix):
        return node.id[len(prefix):]
    return None


def _int_read(name, offset, size, signed, order, total):
    lines = ['def %s(data: bytes, base: int) -> int:' % name, '    v = 0']
    if order == 'big':
        lines += ['    i = 0', '    while i < %d:' % size, '        b = data[base + %d + i]' % offset]
        if signed:
            lines += ['        if i == 0 and (b & 128) != 0:', '            v = b - 256',
                      '        else:', '            v = (v << 8) | b']
        else:
            lines += ['        v = (v << 8) | b']
        lines += ['        i += 1']
    else:
        lines += ['    i = %d' % (size - 1), '    while i >= 0:',
                  '        b = data[base + %d + i]' % offset]
        if signed:
            lines += ['        if i == %d and (b & 128) != 0:' % (size - 1), '            v = b - 256',
                      '        else:', '            v = (v << 8) | b']
        else:
            lines += ['        v = (v << 8) | b']
        lines += ['        i -= 1']
    lines += ['    return v']
    return '\n'.join(lines) + '\n'


def _float_read(name, kind, offset, size, order):
    bits = name + '_bits'
    body = _int_read('_unused', offset, size, True, order, 0)
    lines = body.splitlines()
    lines[0] = 'def %s(data: bytes, base: int) -> float:' % name
    lines = lines[:-1]
    lines += ['    %s = v' % bits, '    return struct__bits_%s(%s)' % (kind, bits)]
    return '\n'.join(lines) + '\n'


def _field_reader(field, order, fmt, index):
    kind, offset, size, signed, count = field
    name = '_ail_struct_get_%d' % index
    if kind in INT_KINDS:
        return name, _int_read(name, offset, size, signed, order, 0)
    if kind in FLOAT_KINDS:
        return name, _float_read(name, FLOAT_KINDS[kind], offset, size, order)
    if kind == '?':
        return name, ('def %s(data: bytes, base: int) -> bool:\n'
                      '    return data[base + %d] != 0\n' % (name, offset))
    if kind == 'c':
        return name, ('def %s(data: bytes, base: int) -> bytes:\n'
                      '    return data[base + %d:base + %d + 1]\n' % (name, offset, offset))
    if kind == 's':
        return name, ('def %s(data: bytes, base: int) -> bytes:\n'
                      '    return data[base + %d:base + %d + %d]\n' % (name, offset, offset, count))
    if kind == 'p':
        return name, ('def %s(data: bytes, base: int) -> bytes:\n'
                      '    n = data[base + %d]\n'
                      '    if n > %d:\n'
                      '        n = %d\n'
                      '    return data[base + %d + 1:base + %d + 1 + n]\n'
                      % (name, offset, max(count - 1, 0), max(count - 1, 0), offset, offset))
    raise AssertionError(kind)


def _pack_helper(fields, order, fmt, number):
    name = '_ail_struct_pack_%d' % number
    params = []
    arg = 0
    for kind, offset, size, signed, count in fields:
        if kind == 'x':
            continue
        if kind in ('s', 'p', 'c'):
            params.append('p%d: bytes' % arg)
        elif kind in FLOAT_KINDS:
            params.append('p%d: float' % arg)
        elif kind == '?':
            params.append('p%d: bool' % arg)
        else:
            params.append('p%d: int' % arg)
        arg += 1
    lines = ['def %s(%s) -> bytes:' % (name, ', '.join(params)), '    out: list[int] = []']
    arg = 0
    for kind, offset, size, signed, count in fields:
        if kind == 'x':
            lines += ['    out.append(0)'] * count
        elif kind in INT_KINDS:
            p = 'p%d' % arg
            arg += 1
            if kind == 'P':
                shifts = ([8 * k for k in range(size)] if order == 'little'
                          else [8 * k for k in range(size - 1, -1, -1)])
                for shift in shifts:
                    lines += ['    out.append((%s >> %d) & 255)' % (p, shift)]
                continue
            limit = 1 << (8 * size - 1)
            low, high = (-limit, limit - 1) if signed else (0, 2 * limit - 1)
            condition = '%s < %d or %s > %d' % (p, low, p, high)
            if not signed and size == 8:
                condition = '%s < 0' % p
            message = "'%s' format requires %d <= number <= %d" % (kind, low, high)
            lines += ['    if %s:' % condition,
                      '        raise RuntimeError(%r)' % message]
            tb = '_tb%d' % arg
            lines += ["    %s = %s.to_bytes(%d, %r, signed=%s)" % (tb, p, size, order, signed)]
            lines += ['    for b in %s:' % tb, '        out.append(b)']
        elif kind == '?':
            lines += ['    out.append(1 if p%d else 0)' % arg]
            arg += 1
        elif kind == 'c':
            p = 'p%d' % arg
            arg += 1
            lines += ['    if len(%s) != 1:' % p,
                      '        raise RuntimeError("char format requires a bytes object of length 1")',
                      '    out.append(%s[0])' % p]
        elif kind == 's':
            p = 'p%d' % arg
            arg += 1
            v, i = '_sv%d' % arg, '_si%d' % arg
            lines += ['    %s = %s' % (v, p), '    %s = 0' % i,
                      '    while %s < %d:' % (i, count),
                      '        out.append(%s[%s] if %s < len(%s) else 0)' % (v, i, i, v),
                      '        %s += 1' % i]
        elif kind == 'p':
            p = 'p%d' % arg
            arg += 1
            n, i = '_pn%d' % arg, '_pi%d' % arg
            lines += ['    %s = len(%s)' % (n, p)]
            if count > 0:
                lines += ['    if %s > %d:' % (n, count - 1), '        %s = %d' % (n, count - 1)]
            lines += ['    out.append(%s)' % n, '    %s = 0' % i,
                      '    while %s < %d:' % (i, max(count - 1, 0)),
                      '        out.append(%s[%s] if %s < %s else 0)' % (p, i, i, n),
                      '        %s += 1' % i]
        elif kind in FLOAT_KINDS:
            p = 'p%d' % arg
            arg += 1
            bits = '_pb%d' % arg
            lines += ['    %s = struct__%s_bits(%s)' % (bits, FLOAT_KINDS[kind], p)]
            shifts = [8 * k for k in range(size)] if order == 'little' else [8 * k for k in range(size - 1, -1, -1)]
            for shift in shifts:
                lines += ['    out.append((%s >> %d) & 255)' % (bits, shift)]
        else:
            raise AssertionError(kind)
    lines += ['    return bytes(out)']
    return name, '\n'.join(lines) + '\n'


def _call_name(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _literal_format(call, what):
    if not call.args:
        refuse(call, 'struct.%s(): the format is the first argument: %s' % (what, NOTE))
    fmt = call.args[0]
    if not (isinstance(fmt, ast.Constant) and isinstance(fmt.value, str)):
        refuse(fmt, 'struct.%s(): the format must be a string literal: %s' % (what, NOTE))
    return fmt.value


def _parse_call(call, what, extra):
    fmt = _literal_format(call, what)
    prefix, order, fields, total = _pieces(fmt, call.args[0])
    if call.keywords:
        refuse(call, 'struct.%s(): keyword arguments are not built: %s' % (what, NOTE))
    return fmt, order, fields, total


def _field_count(fields):
    return len([f for f in fields if f[0] != 'x'])


class Rewrite(ast.NodeTransformer):
    def __init__(self):
        self.helpers = []
        self.readers = {}
        self.packers = {}
        self.number = 0

    def _helper(self, text):
        self.helpers.append(text)

    def _reader(self, field, order, fmt):
        key = (field, order)
        if key not in self.readers:
            name, text = _field_reader(field, order, fmt, self.number)
            self.number += 1
            self.readers[key] = name
            self._helper(text)
        return self.readers[key]

    def _packer(self, fields, order, fmt):
        key = (tuple(fields), order)
        if key not in self.packers:
            name, text = _pack_helper(fields, order, fmt, self.number)
            self.number += 1
            self.packers[key] = name
            self._helper(text)
        return self.packers[key]

    def visit_Call(self, node):
        self.generic_visit(node)
        what = _attr(node.func, 'struct__')
        if what == 'calcsize':
            fmt = _literal_format(node, 'calcsize')
            _, _, _, total = _pieces(fmt, node.args[0])
            return ast.copy_location(ast.Constant(value=total), node)
        if what == 'pack':
            fmt, order, fields, total = _parse_call(node, 'pack', 0)
            args = node.args[1:]
            if len(args) != _field_count(fields):
                refuse(node, 'struct.pack(%r): this format takes %d values, not %d: %s'
                       % (fmt, _field_count(fields), len(args), NOTE))
            values = [f for f in fields if f[0] != 'x']
            args = [ast.copy_location(ast.Compare(left=arg, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)]),
                                      arg) if value[0] == '?' else arg
                    for value, arg in zip(values, args)]
            name = self._packer(fields, order, fmt)
            return ast.copy_location(ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[]), node)
        if what in ('unpack', 'unpack_from'):
            refuse(node, 'struct.%s() is built only as `a, b, ... = struct.%s(...)`: an unpack result '
                         'used as a value is not built; %s' % (what, what, NOTE))
        return node

    def visit_Assign(self, node):
        call = node.value if isinstance(node.value, ast.Call) else None
        what = _call_name(call)
        if call is not None and what in ('struct__unpack', 'struct__unpack_from') and \
                isinstance(node.targets[0], (ast.Tuple, ast.List)):
            target = node.targets[0]
            if len(node.targets) != 1 or not all(isinstance(e, ast.Name) for e in target.elts):
                refuse(node, 'struct.%s(): only `a, b, ... = struct.%s(...)` with plain names is '
                       'built: %s' % (what[len('struct__'):], what[len('struct__'):], NOTE))
            fmt = _literal_format(call, what[len('struct__'):])
            _, order, fields, total = _parse_call(call, what[len('struct__'):], 0)
            if len(target.elts) != _field_count(fields):
                refuse(node, 'struct.%s(%r) gives %d values, but %d names are assigned: %s'
                       % (what[len('struct__'):], fmt, _field_count(fields), len(target.elts), NOTE))
            name = 'unpack' if what == 'struct__unpack' else 'unpack_from'
            if len(call.args) < 2:
                refuse(call, 'struct.%s(): the data is the second argument: %s' % (name, NOTE))
            if name == 'unpack' and len(call.args) != 2:
                refuse(call, 'struct.unpack() takes exactly a format and the data: %s' % NOTE)
            if name == 'unpack_from' and not (2 <= len(call.args) <= 3):
                refuse(call, 'struct.unpack_from() takes a format, the data and an optional offset: %s' % NOTE)
            data, off = call.args[1], (call.args[2] if len(call.args) == 3 else ast.Constant(value=0))
            data = ast.Call(func=ast.Name(id='bytes', ctx=ast.Load()), args=[self.visit(data)], keywords=[])
            off = self.visit(off)
            self.number += 1
            tag = self.number
            dn = '_ail_su_data_%d' % tag
            on = '_ail_su_off_%d' % tag
            bn = '_ail_su_base_%d' % tag
            out = [ast.Assign(targets=[ast.Name(id=dn, ctx=ast.Store())], value=data),
                   ast.Assign(targets=[ast.Name(id=on, ctx=ast.Store())], value=off)]
            if name == 'unpack':
                check = (f'{bn} = {on}\n'
                         f'if len({dn}) != {total}:\n'
                         f'    raise RuntimeError("unpack requires a buffer of {total} bytes")\n')
            else:
                check = (f'if {on} < -len({dn}):\n'
                         f'    raise RuntimeError("offset %d out of range for %d-byte buffer" % ({on}, len({dn})))\n'
                         f'if {on} < 0:\n'
                         f'    {bn} = len({dn}) + {on}\n'
                         f'else:\n'
                         f'    {bn} = {on}\n'
                         f'if len({dn}) - {bn} < {total}:\n'
                         f'    if {on} < 0:\n'
                         f'        raise RuntimeError("not enough data to unpack {total} bytes at offset %d" % {on})\n'
                         f'    raise RuntimeError("unpack_from requires a buffer of at least %d bytes for '
                         f'unpacking {total} bytes at offset %d (actual buffer size is %d)" % '
                         f'({on} + {total}, {on}, len({dn})))\n')
            out.extend(ast.parse(check).body)
            index = 0
            for field, target_name in zip([f for f in fields if f[0] != 'x'], target.elts):
                helper = self._reader(field, order, fmt)
                call_node = ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                     args=[ast.Name(id=dn, ctx=ast.Load()), ast.Name(id=bn, ctx=ast.Load())],
                                     keywords=[])
                out.append(ast.Assign(targets=[target_name], value=ast.copy_location(call_node, node)))
                index += 1
            return [ast.copy_location(each, node) for each in out]
        return self.generic_visit(node)


def rewrite_text(source, notes=None):
    if 'struct__' not in source and 'struct.' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, ast.Name) and n.id.startswith('struct__') for n in ast.walk(tree)):
        return source
    defined = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
    try:
        rewrite = Rewrite()
        tree.body = [rewrite.visit(stmt) for stmt in tree.body]
        tree.body = [each for group in tree.body for each in (group if isinstance(group, list) else [group])]
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id.startswith('struct__'):
                if each.id in defined:
                    continue
                attr = each.id[len('struct__'):]
                if attr in ('pack', 'unpack', 'unpack_from', 'calcsize'):
                    continue                 # left only when a parent shape was not a plain assignment
                refuse(each, 'struct.%s is not built: %s' % (attr, NOTE))
        if rewrite.helpers:
            insert_after_imports(tree, '\n\n'.join(rewrite.helpers))
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program; %s' % NOTE))
        return source
