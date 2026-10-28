"""`struct` lowered to bytes built with int.to_bytes / int.from_bytes (library batch 5, called from stdlib5).

The format string has to be a literal, so the compiler parses it and knows the size and the field list:
`pack`, `unpack`, `unpack_from` and `pack_into` then become calls to helpers generated for that one format,
and `calcsize` becomes the integer size.  Only the standard byte orders `<`, `>`, `!` and `=` are built (the
native `@`, which is also the default, aligns fields and sizes `l`/`P` for the host); the integer, bool, char,
string and pascal-string codes are built, the float codes `e`, `f` and `d` and everything else are refused by
name.  `struct.error` is the exception the helpers raise.  `Struct`, `iter_unpack` and a format that is not a
literal are refused too; `pack_into` with a non-bytearray buffer raises CPython's TypeError.
"""
import ast
import hashlib
import sys

import stdlib5
from stdlib4 import refuse

HANDLED = {'pack', 'unpack', 'calcsize', 'unpack_from', 'pack_into', 'error'}
BUILT = ('pack, unpack, calcsize, unpack_from, pack_into and error are built; the format string has to be a '
         'literal, the byte order `<`, `>`, `!` or `=`, and the codes b B h H i I l L q Q c ? s p x are '
         'built (the float codes e, f, d are not)')

SIZE = {'x': 0, 'c': 1, 'b': 1, 'B': 1, '?': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4,
        'q': 8, 'Q': 8}
SIGNED = {'b', 'h', 'i', 'l', 'q'}


def _const_str(node):
    """The text of a string literal, including implicit and `+` concatenation, or a named refusal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _const_str(node.left) + _const_str(node.right)
    refuse(node, 'struct: the format string has to be a string literal so the compiler can check it')


def _limits(size, signed):
    if signed:
        return -(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1
    return 0, (1 << (8 * size)) - 1


def _parse(fmt, node):
    """(endian, [(code, count, size, signed), ...], total size) or a refusal naming the format."""
    if not fmt.strip():
        return sys.byteorder, [], 0
    index = 0
    if fmt and fmt[0] in '<>=!@':
        prefix = fmt[0]
        index = 1
    else:
        prefix = '@'
    if prefix == '@':
        refuse(node, 'struct: the native byte order and alignment (the `@` prefix, which is also the default) is '
                     'not built; write `<` or `>` for a standard size and byte order')
    endian = 'big' if prefix in '>!' else 'little' if prefix == '<' else sys.byteorder
    fields = []
    size = 0
    while index < len(fmt):
        ch = fmt[index]
        if ch in ' \t\n\r\v\f':
            index += 1
            continue
        start = index
        while index < len(fmt) and fmt[index].isdigit():
            index += 1
        count = int(fmt[start:index]) if index > start else 1
        if index >= len(fmt):
            refuse(node, 'struct: a repeat count at the end of the format needs a format code')
        code = fmt[index]
        index += 1
        if code in 'efd':
            refuse(node, 'struct: the float format %r is not built: encode the bits of a float with '
                         'int.to_bytes / int.from_bytes (or use pack with an integer format)' % code)
        if code in 'sp':
            fields.append((code, count, count, False))
            size += count
        elif code == 'x':
            fields.append((code, count, count, False))
            size += count
        elif code in SIZE:
            each = SIZE[code]
            for _ in range(count):
                fields.append((code, 1, each, code in SIGNED))
            size += each * count
        else:
            refuse(node, 'struct: the format code %r is not built; the codes built are b B h H i I l L q Q c ? '
                         's p x (n, N and P are native-only and the native order is not built)' % code)
    return endian, fields, size


def _tag(fmt):
    return hashlib.sha1(fmt.encode('utf-8')).hexdigest()[:12]


class Lower:
    def __init__(self, tree, binder, text):
        self.tree = tree
        self.b = binder
        self.text = text
        self.pack = {}
        self.unpack = {}
        self.pack_into = {}
        self.prelude = False

    def helper_pack(self, endian, fields):
        key = (endian, tuple(fields))
        if key in self.pack:
            return self.pack[key]
        name = '_ail_struct_pack_' + _tag(repr(key))
        params = []
        parts = []
        for code, count, size, signed in fields:
            if code == 'x':
                parts.append('b"\\x00" * %d' % count)
                continue
            value = 'p%d' % len(params)
            params.append(value)
            if code == '?':
                parts.append('_ail_struct_bool(%s)' % value)
            elif code == 'c':
                parts.append('_ail_struct_char(%s)' % value)
            elif code == 's':
                parts.append('_ail_struct_s(%s, %d)' % (value, count))
            elif code == 'p':
                parts.append('_ail_struct_p(%s, %d)' % (value, count))
            else:
                lo, hi = _limits(size, signed)
                parts.append('_ail_struct_int(%s, %d, %s, %r, %d, %d, %r)'
                             % (value, size, signed, code, lo, hi, endian))
        body = ' + '.join(parts) if parts else 'b""'
        self.text.append('def %s(%s) -> bytes:\n    return %s\n' % (name, ', '.join(params), body))
        self.prelude = True
        self.pack[key] = name
        return name

    def helper_unpack(self, endian, fields, size):
        key = (endian, tuple(fields), size)
        if key in self.unpack:
            return self.unpack[key]
        name = '_ail_struct_unpack_' + _tag(repr(key))
        lines = ['def %s(data, offset: int, exact: int):' % name,
                 '    _ail_struct_check(data, offset, %d, exact)' % size]
        result = []
        at = 0
        for i, (code, count, width, signed) in enumerate(fields):
            var = 'r%d' % i
            if code == 'x':
                at += width
                continue
            if code == '?':
                lines.append('    %s = _ail_struct_unpack_bool(data[offset + %d:offset + %d])' % (var, at, at + width))
            elif code == 'c':
                lines.append('    %s = _ail_struct_unpack_char(data[offset + %d:offset + %d])' % (var, at, at + width))
            elif code == 's':
                lines.append('    %s = _ail_struct_unpack_s(data[offset + %d:offset + %d])' % (var, at, at + width))
            elif code == 'p':
                lines.append('    %s = _ail_struct_unpack_p(data[offset + %d:offset + %d], %d)'
                             % (var, at, at + width, width))
            else:
                lines.append('    %s = _ail_struct_unpack_int(data[offset + %d:offset + %d], %d, %s, %r)'
                             % (var, at, at + width, width, signed, endian))
            result.append(var)
            at += width
        lines.append('    return (%s)' % (', '.join(result) + (',' if len(result) == 1 else '')))
        self.text.append('\n'.join(lines) + '\n')
        self.prelude = True
        self.unpack[key] = name
        return name

    def helper_pack_into(self, endian, fields):
        key = (endian, tuple(fields))
        if key in self.pack_into:
            return self.pack_into[key]
        pack = self.helper_pack(endian, fields)
        name = '_ail_struct_pack_into_' + _tag(repr(key))
        params = ['p%d' % i for i in range(sum(1 for field in fields if field[0] != 'x'))]
        self.text.append('def %s(buf, offset: int, %s) -> None:\n    _ail_struct_store(buf, offset, %s(%s))\n'
                         % (name, ', '.join(params), pack, ', '.join(params)))
        self.pack_into[key] = name
        return name

    def call(self, name, args):
        return ast.Call(func=stdlib5.name(name), args=list(args), keywords=[])

    def fix(self, node):
        attr = self.b.attr(node)
        if attr == 'error':
            self.prelude = True
            return stdlib5.name('error')
        if not isinstance(node, ast.Call):
            return None
        found = self.b.attr(node.func)
        if found is None:
            return None
        if found not in HANDLED:
            refuse(node, 'struct.%s is not built: %s' % (found, BUILT))
        if node.keywords:
            refuse(node, 'struct.%s: keyword arguments are not built; write the format and the values positionally'
                   % found)
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                refuse(arg, 'struct.%s: a starred argument is not built; write the values out' % found)
        if found == 'error':
            refuse(node, 'struct.error(...) is not built: the helpers raise struct.error themselves')
        if not node.args:
            refuse(node, 'struct.%s: the format string is the first argument' % found)
        children = [stdlib5.Replace(self.fix).visit(arg) for arg in node.args]
        fmt = _const_str(children[0])
        endian, fields, size = _parse(fmt, children[0])
        if found == 'calcsize':
            if len(children) != 1:
                refuse(node, 'struct.calcsize takes one argument (the format)')
            return ast.Constant(value=size)
        values = list(children[1:])
        if found in ('pack', 'pack_into'):
            needed = sum(1 for field in fields if field[0] != 'x')
            got = len(values) - 2 if found == 'pack_into' else len(values)
            if got != needed:
                refuse(node, 'struct.%s: the format %r takes %d value(s), this call has %d'
                       % (found, fmt, needed, got))
        if found == 'pack':
            return self.call(self.helper_pack(endian, fields), values)
        if found == 'pack_into':
            if len(values) < 1:
                refuse(node, 'struct.pack_into takes a buffer and an offset after the format')
            return self.call(self.helper_pack_into(endian, fields), values)
        if found == 'unpack':
            if len(values) != 1:
                refuse(node, 'struct.unpack takes a format and one buffer')
            helper = self.helper_unpack(endian, fields, size)
            return self.call(helper, [values[0], ast.Constant(value=0), ast.Constant(value=1)])
        if found == 'unpack_from':
            if len(values) not in (1, 2):
                refuse(node, 'struct.unpack_from takes a format, a buffer and an optional offset')
            helper = self.helper_unpack(endian, fields, size)
            offset = values[1] if len(values) == 2 else ast.Constant(value=0)
            return self.call(helper, [values[0], offset, ast.Constant(value=0)])
        refuse(node, 'struct.%s is not built: %s' % (found, BUILT))


def _binds_error(tree):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == 'error':
            return node
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Name) and target.id == 'error':
                return node
    return None


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'struct', HANDLED, unknown=BUILT)
    if not binder:
        return
    found = _binds_error(tree)
    if found is not None:
        refuse(found, 'the program binds the name error itself and also imports struct.error; rename one')
    lower = Lower(tree, binder, text)
    tree.body = [stdlib5.Replace(lower.fix).visit(statement) for statement in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, BUILT)
    if lower.prelude:
        text.insert(0, stdlib5.prelude('struct'))
