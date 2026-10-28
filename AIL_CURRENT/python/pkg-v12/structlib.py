"""Library: `struct`, lowered to bytearray / int.to_bytes() / int.from_bytes().

`rewrite_text(source, notes)` runs from ail_syntax.python_surface before the other source passes, so the
helper functions this pass adds and the calls it rewrites are ordinary Python for the passes that follow.

A format is a string literal with an explicit byte-order prefix (`<`, `>`, `!`, or `=` for native byte
order and the standard sizes without alignment). The codes built are x, c, b, B, h, H, i, I, l, L, q, Q,
s and ?. A repetition count before a code is built (`2I`, `4x`, `8s`). The native layout (`@` or no
prefix) and the float codes e/f/d, p, n, N and P are refused here by name, as is a computed format string
or unpack_from / pack_into / Struct / iter_unpack.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib3

MODULES = ('struct',)
PREFIXES = '<>=!@'
SIZES = {'x': 1, 'c': 1, '?': 1, 'b': 1, 'B': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4,
         'l': 4, 'L': 4, 'q': 8, 'Q': 8, 's': 1}
MAX_SIZE = 1 << 20
UNSIGNED = {'B': (0, 255), 'H': (0, 65535), 'I': (0, 4294967295), 'L': (0, 4294967295),
            'Q': (0, 18446744073709551615)}
SIGNED = {'b': (-128, 127), 'h': (-32768, 32767), 'i': (-2147483648, 2147483647),
          'l': (-2147483648, 2147483647), 'q': (-9223372036854775808, 9223372036854775807)}
FLOAT = {'e', 'f', 'd'}
NATIVE = {'p', 'n', 'N', 'P'}
LEFT_NOTE = ('struct.pack, unpack, calcsize and error are built for a literal format with an explicit '
             'byte order (<, >, ! or =) and the codes x, c, b, B, h, H, i, I, l, L, q, Q, s and ?')


class Refused(Exception):
    def __init__(self, line, text):
        super().__init__(text)
        self.line, self.text = line, text


def refuse(node, text):
    raise Refused(getattr(node, 'lineno', None) or 1, text)


class Imports(stdlib3.Imports):
    def __init__(self, tree, modules):
        self.aliases = {}
        self.names = {}
        self.nodes = []
        body = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name in modules:
                        self.aliases[alias.asname or alias.name] = alias.name
                    else:
                        rest.append(alias)
                if len(rest) != len(node.names):
                    self.nodes.append(node)
                    if rest:
                        node.names = rest
                        body.append(node)
                    continue
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in modules:
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from %s import *: name what you use' % node.module)
                    self.names[alias.asname or alias.name] = (node.module, alias.name)
                self.nodes.append(node)
                continue
            body.append(node)
        tree.body = body


def literal(node, what):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        refuse(node, '%s: the format must be a string literal; write the format in the call' % what)
    return node.value


class Format:
    def __init__(self, node, name, text):
        self.name = name
        self.text = text
        self.fields = []                   # (code, size, offset); `x` fields are present too
        self.values = []                   # the non-x fields
        self.size = 0
        if not text or text[0] not in PREFIXES:
            refuse(node, 'struct.%s: the native layout (@, or no prefix) is not built; write "<" or ">" for a '
                         'standard layout, or "=" for native byte order without alignment' % name)
        prefix = text[0]
        if prefix == '@':
            refuse(node, 'struct.%s: the native layout (@) is not built; write "<" or ">" for a standard layout, '
                         'or "=" for native byte order without alignment' % name)
        self.little = prefix == '<' or (prefix == '=' and sys.byteorder == 'little')
        index = 1
        while index < len(text):
            char = text[index]
            if char.isspace():
                index += 1
                continue
            digits = index
            count = 0
            while index < len(text) and text[index].isdigit():
                count = count * 10 + int(text[index])
                index += 1
            repeated = index > digits
            char = text[index] if index < len(text) else ''
            index += 1
            if not char:
                refuse(node, 'struct.%s: a repeat count needs a format character' % name)
            if char in FLOAT:
                refuse(node, 'struct.%s: the float format character %r is not built; keep the bits as an int '
                             'and use int.to_bytes() / int.from_bytes()' % (name, char))
            if char in NATIVE:
                refuse(node, 'struct.%s: the native format character %r is not built' % (name, char))
            if char not in SIZES:
                refuse(node, 'struct.%s: the format character %r is not built; %s' % (name, char, LEFT_NOTE))
            count = count if repeated else 1
            if char == 's':
                self.grow(node, count)
                field = (char, count, self.size)
                self.fields.append(field)
                self.values.append(field)
                self.size += count
            elif char == 'x':
                self.grow(node, count)
                field = (char, count, self.size)
                self.fields.append(field)
                self.size += count
            else:
                size = SIZES[char]
                self.grow(node, size * count)
                for _ in range(count):
                    field = (char, size, self.size)
                    self.fields.append(field)
                    self.values.append(field)
                    self.size += size
        self.endian = 'little' if self.little else 'big'

    def grow(self, node, amount):
        if self.size + amount > MAX_SIZE:
            refuse(node, 'struct.%s: a format of more than %d bytes is not built; pack a smaller piece at a '
                         'time' % (self.name, MAX_SIZE))


class Renamer(ast.NodeTransformer):
    def __init__(self, imports, helpers):
        self.imports = imports
        self.helpers = helpers
        self.count = 0
        self.used = set()

    def fresh(self, kind, tree):
        if not self.used:
            for each in ast.walk(tree):
                if isinstance(each, ast.Name):
                    self.used.add(each.id)
                elif isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.used.add(each.name)
        while True:
            name = '_ail_bin_%s_%d' % (kind, self.count)
            self.count += 1
            if name not in self.used:
                self.used.add(name)
                return name

    def visit_Call(self, node):
        node = self.generic_visit(node)
        found = self.imports.resolve(node.func)
        if found is None or found[0] != 'struct':
            return self.generic_visit(node)
        name = found[1]
        if name not in ('pack', 'unpack', 'calcsize'):
            refuse(node, 'struct.%s used here is not built: %s' % (name, LEFT_NOTE))
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            refuse(node, 'struct.%s: * and ** arguments are not built' % name)
        if node.keywords:
            refuse(node, 'struct.%s: keyword arguments are not built' % name)
        if not node.args:
            refuse(node, 'struct.%s: the format is required' % name)
        fmt = Format(node.args[0], name, literal(node.args[0], 'struct.%s' % name))
        if name == 'calcsize':
            if len(node.args) != 1:
                refuse(node, 'struct.calcsize: one argument is built (the format)')
            return ast.copy_location(ast.Constant(value=fmt.size), node)
        if name == 'pack':
            values = node.args[1:]
            want = len(fmt.values)
            if len(values) != want:
                refuse(node, 'struct.pack: the format %r packs %d value%s (%d given)' %
                       (fmt.text, want, '' if want == 1 else 's', len(values)))
            helper = self.fresh('pack', self.tree)
            self.helpers.append(pack_helper(helper, fmt))
            call = ast.Call(func=ast.Name(id=helper, ctx=ast.Load()), args=values, keywords=[])
            return ast.copy_location(call, node)
        if name == 'unpack':
            if len(node.args) != 2:
                refuse(node, 'struct.unpack: two arguments are built (the format and the buffer)')
            helper = self.fresh('unpack', self.tree)
            self.helpers.append(unpack_helper(helper, fmt))
            call = ast.Call(func=ast.Name(id=helper, ctx=ast.Load()), args=[node.args[1]], keywords=[])
            return ast.copy_location(call, node)

    def visit_Attribute(self, node):
        found = self.imports.resolve(node)
        if found == ('struct', 'error'):
            return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.imports.names:
            module, attr = self.imports.names[node.id]
            if (module, attr) == ('struct', 'error'):
                return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        return node


def range_check(line, code, arg):
    if code in UNSIGNED:
        low, high = UNSIGNED[code]
        lines = []
        if low:
            lines.append('    if %s < %d:' % (arg, low))
        else:
            lines.append('    if %s < 0:' % arg)
        lines.append('        raise ValueError(%r)' % ("'%s' format requires %d <= number <= %d" % (code, low, high)))
        lines.append('    if %s > %d:' % (arg, high))
        lines.append('        raise ValueError(%r)' % ("'%s' format requires %d <= number <= %d" % (code, low, high)))
        return lines
    if code in SIGNED:
        low, high = SIGNED[code]
        return ['    if %s < %d or %s > %d:' % (arg, low, arg, high),
                '        raise ValueError(%r)' % ("'%s' format requires %d <= number <= %d" % (code, low, high))]
    return []


def pack_helper(name, fmt):
    params = ', '.join('v%d' % i for i in range(len(fmt.values)))
    lines = ['def %s(%s) -> bytes:' % (name, params)]
    lines.append('    out = bytearray()')
    arg = 0
    for code, size, _ in fmt.fields:
        if code == 'x':
            lines.append('    out.extend(b"\\x00" * %d)' % size)
            continue
        current = 'v%d' % arg
        arg += 1
        if code == 'c':
            lines.append('    if not isinstance(%s, bytes):' % current)
            lines.append('        raise ValueError("char format requires a bytes object of length 1")')
            lines.append('    if len(%s) != 1:' % current)
            lines.append('        raise ValueError("char format requires a bytes object of length 1")')
            lines.append('    out.extend(%s)' % current)
        elif code == 's':
            lines.append('    if not isinstance(%s, bytes) and not isinstance(%s, bytearray):' % (current, current))
            lines.append('        raise ValueError("argument for \'s\' must be a bytes object")')
            lines.append('    out.extend((%s)[0:%d])' % (current, size))
            if size:
                lines.append('    if len(%s) < %d:' % (current, size))
                lines.append('        out.extend(b"\\x00" * (%d - len(%s)))' % (size, current))
        elif code == '?':
            lines.append('    out.append(1 if %s else 0)' % current)
        else:
            lines.append('    if not isinstance(%s, int) and not isinstance(%s, bool):' % (current, current))
            lines.append('        raise ValueError("required argument is not an integer")')
            lines.extend(range_check(lines, code, current))
            signed = 'True' if code in SIGNED else 'False'
            lines.append('    out.extend((%s).to_bytes(%d, "%s", signed=%s))' % (current, size, fmt.endian, signed))
    lines.append('    return bytes(out)')
    return '\n'.join(lines) + '\n'


def unpack_helper(name, fmt):
    kinds = []
    for code, _, _ in fmt.values:
        if code in ('c', 's'):
            kinds.append('bytes')
        elif code == '?':
            kinds.append('bool')
        else:
            kinds.append('int')
    annotation = ' -> tuple[%s]' % ', '.join(kinds) if kinds else ''
    lines = ['def %s(d)%s:' % (name, annotation)]
    lines.append('    if not isinstance(d, bytes) and not isinstance(d, bytearray):')
    lines.append('        raise TypeError("a bytes-like object is required, not \'%s\'" % type(d).__name__)')
    lines.append('    if len(d) != %d:' % fmt.size)
    lines.append('        raise ValueError("unpack requires a buffer of %d bytes")' % fmt.size)
    parts = []
    for code, size, offset in fmt.values:
        if code == '?':
            parts.append('d[%d] != 0' % offset)
        elif code in ('c', 's'):
            parts.append('bytes(d[%d:%d])' % (offset, offset + size))
        else:
            signed = 'True' if code in SIGNED else 'False'
            parts.append('int.from_bytes(d[%d:%d], "%s", signed=%s)' % (offset, offset + size, fmt.endian, signed))
    lines.append('    return (%s,)' % ', '.join(parts) if len(parts) == 1 else '    return (%s)' % ', '.join(parts))
    return '\n'.join(lines) + '\n'


def leftovers(tree, imports):
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute):
            found = imports.resolve(each)
            if found is not None:
                refuse(each, 'struct.%s used here is not built: %s' % (found[1], LEFT_NOTE))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.names:
            module, attr = imports.names[each.id]
            refuse(each, 'struct.%s used here is not built: %s' % (attr, LEFT_NOTE))


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return source
    imports = Imports(tree, MODULES)
    if not imports.aliases and not imports.names:
        return source
    helpers = []
    try:
        for alias in list(imports.aliases) + list(imports.names):
            if stdlib3.binds(tree, alias):
                refuse(tree.body[0] if tree.body else tree, '%s is also bound by the program itself; rename it '
                       '(the name stands for an imported module here)' % alias)
        renamer = Renamer(imports, helpers)
        renamer.tree = tree
        tree = renamer.visit(tree)
        leftovers(tree, imports)
        added = []
        for chunk in helpers:
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
