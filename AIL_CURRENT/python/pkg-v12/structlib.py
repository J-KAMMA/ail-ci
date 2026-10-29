"""`struct` pack / unpack / unpack_from / calcsize / error, lowered onto prelude_struct.py (library batch 6).

The format string has to be a literal so the layout is known at compile time: the explicit byte-order
prefixes '<', '>' and '!' are built (with standard sizes and no alignment), and the integer codes
b B h H i I l L q Q, the byte/string codes c s x and the boolean '?' are built, with repeat counts.
Everything else is refused by name: the native prefixes '@' and no prefix (their alignment is not built),
the floating-point codes e f d, the Pascal string p, the native-only codes n N P, a computed format and
the names pack_into / iter_unpack / Struct. struct.error is the prelude's `error` class.
"""
import ast
import sys

import stdlib5
from stdlib4 import Refused, refuse

HANDLED = ('pack', 'unpack', 'unpack_from', 'calcsize', 'error')
SIZES = {
    'b': (1, True), 'B': (1, False),
    'h': (2, True), 'H': (2, False),
    'i': (4, True), 'I': (4, False),
    'l': (4, True), 'L': (4, False),
    'q': (8, True), 'Q': (8, False),
}
REFUSED = {
    'f': "struct: the floating-point format 'f' is not built: keep the value as an int, or use '<I' / '<Q' on its bit pattern",
    'd': "struct: the floating-point format 'd' is not built: keep the value as an int, or use '<Q' on its bit pattern",
    'e': "struct: the half-float format 'e' is not built",
    'p': "struct: the Pascal-string format 'p' is not built: use 's' (a fixed number of bytes)",
    'n': "struct: the native-only format 'n' is not built: use a fixed-size code with '<' or '>'",
    'N': "struct: the native-only format 'N' is not built: use a fixed-size code with '<' or '>'",
    'P': "struct: the native-only format 'P' is not built: use a fixed-size code with '<' or '>'",
}
NOTE = ("struct.pack / unpack / unpack_from / calcsize with a literal format using '<', '>', '!', the "
        "integer codes b B h H i I l L q Q, c s x and ? are built")


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def parse_format(fmt, node):
    """(the format as prelude_struct reads it, fields, size) or a refusal at `node`."""
    if fmt == '':
        return '', [], 0
    first = fmt[0]
    if first == '<':
        prefix, body = '<', fmt[1:]
    elif first == '>':
        prefix, body = '>', fmt[1:]
    elif first == '!':
        prefix, body = '>', fmt[1:]
    elif first == '=':
        prefix, body = ('<' if sys.byteorder == 'little' else '>'), fmt[1:]
    elif first == '@':
        refuse(node, "struct format %r uses native alignment, which is not built: write '<' or '>' before "
                     "the codes (standard sizes, no padding)" % fmt)
    else:
        refuse(node, "struct format %r has no byte-order prefix, and native alignment is not built: write "
                     "'<' or '>' before the codes" % fmt)
    fields = []
    i = 0
    while i < len(body):
        j = i
        while j < len(body) and body[j].isdigit():
            j += 1
        count = int(body[i:j]) if j > i else 1
        if j >= len(body):
            refuse(node, "struct format %r gives a repeat count without a format character" % fmt)
        code = body[j]
        if code == 'x':
            fields.append(('x', count, count, False))
        elif code == 'c':
            fields.append(('c', count, 1, False))
        elif code == 's':
            fields.append(('s', 1, count, False))
        elif code == '?':
            fields.append(('?', count, 1, False))
        elif code in SIZES:
            size, signed = SIZES[code]
            fields.append((code, count, size, signed))
        elif code in REFUSED:
            refuse(node, REFUSED[code])
        else:
            refuse(node, "struct format %r has an unknown format character %r" % (fmt, code))
        i = j + 1
    size = 0
    for code, count, width, signed in fields:
        if code == 's' or code == 'x':
            size += width
        else:
            size += count * width
    return prefix + body, fields, size


def _binds_error(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == 'error':
            return node
        if isinstance(node, ast.arg) and node.arg == 'error':
            return node
        if isinstance(node, ast.ExceptHandler) and node.name == 'error':
            return node
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == 'error':
            return node
        if isinstance(node, ast.Global) and 'error' in node.names:
            return node
        if isinstance(node, ast.Nonlocal) and 'error' in node.names:
            return node
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]) == 'error':
                    return node
    return None


def _binds_helper(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name.startswith('_ail_struct_'):
            return node
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id.startswith('_ail_struct_'):
            return node
        if isinstance(node, ast.arg) and node.arg.startswith('_ail_struct_'):
            return node
        if isinstance(node, ast.ExceptHandler) and node.name and node.name.startswith('_ail_struct_'):
            return node
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]).startswith('_ail_struct_'):
                    return node
    return None


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'struct', set(HANDLED), unknown=NOTE)
    if not binder:
        return False
    bound = _binds_error(tree)
    if bound is not None:
        refuse(bound, "struct: the program binds the name error, which struct.error uses; rename it")
    bound = _binds_helper(tree)
    if bound is not None:
        refuse(bound, "struct: the program binds a name starting with _ail_struct_, which struct uses; rename it")
    changed = False
    needs_prelude = False

    def fix(node):
        nonlocal changed, needs_prelude
        if isinstance(node, ast.Call):
            found = binder.attr(node.func)
            if found in ('pack', 'unpack', 'unpack_from', 'calcsize'):
                if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args[:1]):
                    refuse(node, "struct.%s with keyword arguments or a starred format is not built" % found)
                if not node.args:
                    refuse(node, "struct.%s needs a format string" % found)
                fmt = _literal(node.args[0])
                if fmt is None:
                    refuse(node.args[0], "struct.%s needs a literal format string, so the layout is known "
                                         "when the program is compiled" % found)
                normal, fields, size = parse_format(fmt, node.args[0])
                args = [stdlib5.Replace(fix).visit(arg) for arg in node.args[1:]]
                if found == 'calcsize':
                    if args:
                        refuse(node, "struct.calcsize takes one format string")
                    changed = True
                    return ast.copy_location(ast.Constant(value=size), node)
                if found == 'pack':
                    changed = True
                    needs_prelude = True
                    return ast.copy_location(stdlib5.call(stdlib5.name('_ail_struct_pack'),
                                                          [ast.Constant(value=normal)] + args), node)
                if found == 'unpack':
                    if len(args) != 1:
                        refuse(node, "struct.unpack takes a format string and one buffer")
                    changed = True
                    needs_prelude = True
                    return ast.copy_location(stdlib5.call(stdlib5.name('_ail_struct_unpack'),
                                                          [ast.Constant(value=normal)] + args), node)
                if len(args) not in (1, 2):
                    refuse(node, "struct.unpack_from takes a format string, one buffer and an optional offset")
                changed = True
                needs_prelude = True
                return ast.copy_location(stdlib5.call(stdlib5.name('_ail_struct_unpack_from'),
                                                      [ast.Constant(value=normal)] + args), node)
        if binder.attr(node) == 'error':
            changed = True
            needs_prelude = True
            return stdlib5.name('error')
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.pop('error', None)
    stdlib5.leftover(tree, binder, NOTE)
    if needs_prelude:
        text.append(stdlib5.prelude('struct'))
    return changed


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body):
        return source
    text = []
    try:
        if not run(tree, text):
            return source
        if text:
            stdlib5.insert_after_imports(tree, '\n\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the struct rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
