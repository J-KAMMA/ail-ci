"""`struct`: pack / unpack / calcsize / error for the integer formats, lowered onto int.to_bytes and int.from_bytes.

Called from ail_syntax.python_surface on the program text. A program that does not import struct is returned as
written. Every use is either lowered to code that produces what CPython 3.12 produces or refused here by name
(`struct.name: why`). Built: pack, unpack, calcsize and error, with a str literal format whose first character is
'<' or '>' (or '!'), and the format characters x b B h H i I l L q Q ?. The native '@' / '=' byte order and
alignment, floats (e f d), c s p, n N, Struct, pack_into, unpack_from and iter_unpack are refused by name.
"""
import ast
import struct as _py_struct

import stdlib5
from stdlib4 import refuse

HANDLED = {'pack', 'unpack', 'calcsize', 'error'}
ALLOWED = set('xbBhHiIlLqQ?')
SPACE = ' \t\n\r'


def _check_format(node, fmt, what):
    if not isinstance(fmt, str):
        refuse(node, '%s: the format has to be a str literal here (CPython reads it at run time)' % what)
    if not fmt:
        refuse(node, '%s: empty format string' % what)
    if fmt[0] not in '<>!':
        refuse(node, '%s: the format %r has to start with "<", ">" or "!"; the native "@" / "=" byte order and '
                     'alignment are not built' % (what, fmt))
    i = 1
    chars = set()
    arity = 0
    while i < len(fmt):
        while i < len(fmt) and fmt[i] in SPACE:
            i += 1
        if i >= len(fmt):
            break
        start = i
        count = 0
        while i < len(fmt) and '0' <= fmt[i] <= '9':
            count = count * 10 + ord(fmt[i]) - 48
            i += 1
        if i >= len(fmt):
            if i > start:
                refuse(node, '%s: repeat count given without format specifier in %r' % (what, fmt))
            break
        if i == start:
            count = 1
        ch = fmt[i]
        i += 1
        if ch not in ALLOWED:
            refuse(node, '%s: the format character %r in %r is not built; the integer formats x b B h H i I l L q Q ? '
                         'are built with "<", ">" or "!"' % (what, ch, fmt))
        chars.add(ch)
        if ch != 'x':
            arity += count
    return chars, arity


class Fix(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.need = set()
        self.unpack_defs = []
        self.unpack_helpers = {}

    def visit_Attribute(self, node):
        node = self.generic_visit(node)
        if self.binder.attr(node) == 'error':
            self.need.add('error')
            return ast.copy_location(stdlib5.name('_AilStructError'), node)
        return node

    def visit_Name(self, node):
        if self.binder.attr(node) == 'error':
            self.need.add('error')
            return ast.copy_location(stdlib5.name('_AilStructError'), node)
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        attr = self.binder.attr(node.func)
        if attr not in ('pack', 'unpack', 'calcsize'):
            return node
        what = 'struct.' + attr
        if node.keywords:
            refuse(node, '%s: keyword arguments are not built' % what)
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            refuse(node, '%s: * arguments are not built' % what)
        if not node.args:
            refuse(node, '%s: missing the format argument' % what)
        fmt = node.args[0]
        if not isinstance(fmt, ast.Constant) or not isinstance(fmt.value, str):
            refuse(node, '%s: the format has to be a str literal here (CPython reads it at run time)' % what)
        chars, arity = _check_format(node, fmt.value, what)
        if attr == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize takes one argument')
            self.need.add('calcsize')
            return ast.copy_location(ast.Constant(value=_py_struct.calcsize(fmt.value)), node)
        if attr == 'pack':
            self.need.add('pack')
            values = ast.List(elts=node.args[1:], ctx=ast.Load())
            return ast.copy_location(stdlib5.call(stdlib5.name('_ail_struct_pack'), [fmt, values]), node)
        if len(node.args) != 2:
            refuse(node, 'struct.unpack takes the format and the bytes')
        if '?' in chars:
            refuse(node, 'struct.unpack: the ? format is not built (its result is a bool; pack does build it)')
        if arity == 0:
            refuse(node, 'struct.unpack: a format with no values is not built (it returns an empty tuple)')
        self.need.add('unpack')
        helper = self.unpack_helpers.get(fmt.value)
        if helper is None:
            helper = '_ail_struct_unpack_tuple_%d' % len(self.unpack_defs)
            self.unpack_helpers[fmt.value] = helper
            self.unpack_defs.append((helper, fmt.value, arity))
        return ast.copy_location(stdlib5.call(stdlib5.name(helper), [node.args[1]]), node)


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any((isinstance(node, ast.Import) and any(alias.name == 'struct' for alias in node.names))
               or (isinstance(node, ast.ImportFrom) and not node.level and node.module == 'struct')
               for node in tree.body):
        return source
    try:
        binder = stdlib5.take_imports(tree, 'struct', HANDLED,
                                      unknown='pack, unpack, calcsize and error are the names that are built')
        if not binder:
            return source
        fix = Fix(binder)
        tree.body = [fix.visit(stmt) for stmt in tree.body]
        stdlib5.leftover(tree, binder, 'pack, unpack, calcsize and error are built for a str literal format with '
                                       '"<", ">" or "!" and the integer format characters')
        if fix.need - {'calcsize'}:
            stdlib5.insert_after_imports(tree, stdlib5.prelude('struct'))
        for helper, fmt, arity in fix.unpack_defs:
            elements = ', '.join('values[%d]' % index for index in range(arity))
            if arity == 1:
                elements += ','
            result = ', '.join('int' for _ in range(arity))
            if arity == 1:
                result += ','
            stdlib5.insert_after_imports(
                tree, 'def %s(data: bytes) -> tuple[%s]:\n    values = _ail_struct_unpack(%r, data)\n'
                      '    return (%s)\n' % (helper, result, fmt, elements))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except stdlib5.Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (_py_struct.error, AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                             'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
