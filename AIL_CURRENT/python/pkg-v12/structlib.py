"""Library batch 16: `struct` for literal format strings, lowered onto bytes and int.to_bytes / int.from_bytes.

`structlib.rewrite_text` runs from ail_syntax.python_surface before the other source passes. A program that does
not import `struct` is returned as it was written (the same string), so its C does not change. A use that is not
built keeps the program as written and adds a `note:` line; the import refusal that follows names the module.

Built: `struct.pack`, `struct.unpack`, `struct.unpack_from` and `struct.calcsize` with a string-literal format.
The format is checked at build time: the integer codes (`b B h H i I l L q Q n N P`), `?`, `c`, `s`, `p`, `x`,
whitespace and repeat counts, in every byte order (`@ = < > !`), including native alignment. The float codes
`e f d` and a format computed at run time are refused by name, as are `Struct`, `pack_into` and `iter_unpack`.
`struct.error` is `ValueError` on this path (as `zlib.error` is `RuntimeError`).
"""
import ast
from pathlib import Path
import struct as _host_struct
import sys

HERE = Path(__file__).parent
SUPPORTED = ('pack', 'unpack', 'unpack_from', 'calcsize')
FLOAT_CODES = {'e': 'half float', 'f': 'single float', 'd': 'double float'}
_ORDERS = '@=<>!'


class Refused(Exception):
    def __init__(self, line, text):
        super().__init__(text)
        self.line, self.text = line, text


def refuse(node, text):
    raise Refused(getattr(node, 'lineno', None) or 1, text)


def prelude():
    lines = (HERE / 'prelude_struct.py').read_text(encoding='utf-8').splitlines()
    start = 0
    while start < len(lines) and (lines[start].startswith('#') or not lines[start].strip()):
        start += 1
    return '\n'.join(lines[start:]) + '\n'


def _check_format(node, fmt):
    """Validate a literal format with CPython's own struct module; refuse float and bad formats by name."""
    i = 1 if fmt and fmt[0] in _ORDERS else 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in ' \t\n\r':
            i += 1
            continue
        if '0' <= ch <= '9':
            j = i
            while j < len(fmt) and '0' <= fmt[j] <= '9':
                j += 1
            if j >= len(fmt):
                refuse(node, "struct format %r is not valid: bad char in struct format" % fmt)
            ch = fmt[j]
            i = j + 1
        else:
            i += 1
        if ch in FLOAT_CODES:
            refuse(node, "struct format code %r (%s) is not built: this compiler builds the integer, bool, "
                  "char, string and padding codes (b B h H i I l L q Q n N P ? c s p x) only"
                  % (ch, FLOAT_CODES[ch]))
    try:
        return _host_struct.calcsize(fmt)
    except (TypeError, ValueError, _host_struct.error) as exc:
        refuse(node, "struct format %r is not valid: %s" % (fmt, exc))


class Binder:
    def __init__(self):
        self.aliases = set()
        self.names = {}
        self.first = None

    def __bool__(self):
        return bool(self.aliases or self.names)

    def attr(self, node):
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.aliases:
            return node.attr
        return None


def _take_imports(tree):
    binder = Binder()
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            rest = []
            for alias in node.names:
                if alias.name == 'struct':
                    binder.aliases.add(alias.asname or 'struct')
                    binder.first = binder.first or node
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'struct':
            binder.first = binder.first or node
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, 'from struct import *: name what you use')
                binder.names[alias.asname or alias.name] = alias.name
            continue
        body.append(node)
    tree.body = body
    return binder


class Rewrite(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.needs_prelude = False

    def visit_Call(self, node):
        node = self.generic_visit(node)
        attribute = self.binder.attr(node.func)
        if attribute is None:
            return node
        if attribute not in SUPPORTED:
            refuse(node, 'struct.%s is not built: pack, unpack, unpack_from and calcsize with a string-literal '
                  'format are; Struct, pack_into, iter_unpack and struct.error are not' % attribute)
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            refuse(node, 'struct.%s: keyword arguments and starred arguments are not built; pass the values '
                  'positionally' % attribute)
        if not node.args:
            refuse(node, 'struct.%s expects a format string' % attribute)
        fmt_node = node.args[0]
        if not (isinstance(fmt_node, ast.Constant) and isinstance(fmt_node.value, str)):
            refuse(node, 'struct.%s: the format has to be a string literal written in the program' % attribute)
        fmt = fmt_node.value
        if attribute == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize takes one argument')
            size = _check_format(node, fmt)
            return ast.copy_location(ast.Constant(value=size), node)
        if attribute == 'pack':
            values = node.args[1:]
            for value in values:
                if isinstance(value, ast.Starred):
                    refuse(node, 'struct.pack: a starred value is not built; pass the values positionally')
            _check_format(node, fmt)
            self.needs_prelude = True
            return ast.copy_location(ast.Call(
                func=ast.Name(id='_ail_struct_pack', ctx=ast.Load()),
                args=[fmt_node, ast.List(elts=list(values), ctx=ast.Load())], keywords=[]), node)
        if attribute == 'unpack':
            if len(node.args) != 2:
                refuse(node, 'struct.unpack takes a format and one buffer')
            _check_format(node, fmt)
            self.needs_prelude = True
            return ast.copy_location(ast.Call(
                func=ast.Name(id='_ail_struct_unpack', ctx=ast.Load()),
                args=[fmt_node, node.args[1]], keywords=[]), node)
        if len(node.args) not in (2, 3):
            refuse(node, 'struct.unpack_from takes a format, a buffer and an optional offset')
        _check_format(node, fmt)
        self.needs_prelude = True
        offset = node.args[2] if len(node.args) == 3 else ast.Constant(value=0)
        return ast.copy_location(ast.Call(
            func=ast.Name(id='_ail_struct_unpack_from', ctx=ast.Load()),
            args=[fmt_node, node.args[1], offset], keywords=[]), node)


def _insert_prelude(tree):
    added = ast.parse(prelude()).body
    index = 0
    while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
            isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
        index += 1
    tree.body[index:index] = added


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    try:
        binder = _take_imports(tree)
        if not binder:
            return source
        rewrite = Rewrite(binder)
        tree.body = [rewrite.visit(statement) for statement in tree.body]
        receiver = set(id(each.value) for each in ast.walk(tree) if isinstance(each, ast.Attribute))
        for each in ast.walk(tree):
            found = binder.attr(each)
            if found is not None:
                refuse(each, 'struct.%s is used as a value here; only a direct call to pack, unpack, '
                      'unpack_from or calcsize is built' % found)
            if (isinstance(each, ast.Name) and each.id in binder.aliases and isinstance(each.ctx, ast.Load)
                    and id(each) not in receiver):
                refuse(each, 'the struct module is used as a value here; only a direct call to pack, unpack, '
                      'unpack_from or calcsize is built')
        if rewrite.needs_prelude:
            _insert_prelude(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
