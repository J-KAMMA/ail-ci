"""`struct` (the integer subset) lowered onto prelude_struct.py (library batch 10).

`rewrite_text(source, notes)` runs from ail_syntax.python_surface on the program text before the other source
passes. A program that does not import `struct` at the top level is returned as it was written (the same
string), so its C does not change.

What is built, with CPython 3.12's bytes, tuple values and `struct.error` messages: `pack`, `unpack`,
`unpack_from` (with the optional `offset`, positional or keyword), `pack_into`, `calcsize` and `error`, over
the codes `x c b B h H i I l L q Q s ?` and the byte orders `< > = !` (a format that reaches the helper is a
constant string; `structlib` checks it at compile time).

Everything else is refused here by name (`struct.name: why`, with what to write instead): the native byte
order (no prefix or `@`), the float codes f / d / e, the pascal-string code p, unknown codes, a format that
is not a constant string, `Struct`, `iter_unpack` and any other attribute, keyword arguments to the
functions that take none, and a wrong number of arguments to a function whose arity is fixed.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from stdlib4 import Refused, refuse
import stdlib5

FUNCTIONS = {
    'pack': '_ail_struct_pack',
    'unpack': '_ail_struct_unpack',
    'unpack_from': '_ail_struct_unpack_from',
    'pack_into': '_ail_struct_pack_into',
    'calcsize': '_ail_struct_calcsize',
}
HANDLED = set(FUNCTIONS) | {'error'}
CODES = 'xcbBhHiIlLqQs?'
FLOATS = 'fde'
WHAT = ('struct: the integer subset is pack, unpack, unpack_from, pack_into, calcsize and error over '
        'x c b B h H i I l L q Q s ?, with the < > = ! byte orders')


def binds(tree, name):
    """Whether the program itself binds `name` somewhere (a store, a def, a class or a parameter)."""
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name == name:
            return True
        if isinstance(each, ast.arg) and each.arg == name:
            return True
        if isinstance(each, ast.Name) and each.id == name and isinstance(each.ctx, (ast.Store, ast.Del)):
            return True
    return False


def constant_format(node, what):
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        refuse(node, '%s: the format must be a constant string; %s' % (what, WHAT))
    return node.value


def check_format(node, fmt, what):
    """Refuse by name a constant format whose codes this build does not lower."""
    if len(fmt) == 0 or fmt[0] not in '<>=!':
        refuse(node, '%s: the native byte order (no prefix or "@") is not built; write "<", ">", "=" or "!" '
                    'first so the sizes are fixed' % what)
    i = 1
    count = 0
    have = False
    total = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in ' \t\n\r\v\f':
            if have:
                refuse(node, '%s: a count must be followed by its format code (no space between them)' % what)
            i += 1
            continue
        if '0' <= ch <= '9':
            count = count * 10 + (ord(ch) - 48)
            have = True
            if count > 2147483647:
                refuse(node, '%s: total struct size too long' % what)
            i += 1
            continue
        if ch in FLOATS:
            refuse(node, '%s: the float format code %r is not built; keep the bits as an int with "<Q" / "<I" '
                        'and int.from_bytes / int.to_bytes, or write the value as text' % (what, ch))
        if ch not in CODES:
            refuse(node, '%s: %r is not a format code this compiler builds; %s' % (what, ch, WHAT))
        size = count if have else 1
        if ch == 'h' or ch == 'H':
            size = size * 2
        elif ch == 'i' or ch == 'I' or ch == 'l' or ch == 'L':
            size = size * 4
        elif ch == 'q' or ch == 'Q':
            size = size * 8
        total += size
        if total > 2147483647:
            refuse(node, '%s: total struct size too long' % what)
        count = 0
        have = False
        i += 1
    if have:
        refuse(node, '%s: a count must be followed by its format code' % what)


class Lower(ast.NodeTransformer):
    def __init__(self, binder, err_name):
        self.binder = binder
        self.err_name = err_name
        self.used = False
        self.used_error = False

    def visit_Call(self, node):
        attr = self.binder.attr(node.func)
        if attr in FUNCTIONS:
            return self.generic_visit(self.lower_call(attr, node))
        if attr == 'error':
            refuse(node, 'struct.error is a class (write `except struct.error`), not a function')
        return self.generic_visit(node)

    def lower_call(self, attr, node):
        what = 'struct.' + attr
        args = list(node.args)
        keywords = node.keywords
        if attr != 'unpack_from' and keywords:
            refuse(node, '%s takes positional arguments only' % what)
        if not args:
            refuse(node, '%s needs a format' % what)
        fmt_node = args[0]
        check_format(fmt_node, constant_format(fmt_node, what), what)
        if attr == 'pack':
            self.used = True
            values = ast.Tuple(elts=args[1:], ctx=ast.Load())
            return stdlib5.call(stdlib5.name(FUNCTIONS[attr]), [fmt_node, values])
        if attr == 'unpack':
            if len(args) != 2:
                refuse(node, 'struct.unpack takes exactly a format and a buffer')
            self.used = True
            return stdlib5.call(stdlib5.name(FUNCTIONS[attr]), [fmt_node, args[1]])
        if attr == 'calcsize':
            if len(args) != 1:
                refuse(node, 'struct.calcsize takes exactly a format')
            self.used = True
            return stdlib5.call(stdlib5.name(FUNCTIONS[attr]), [fmt_node])
        if attr == 'unpack_from':
            if keywords:
                if len(args) == 2 and len(keywords) == 1 and keywords[0].arg == 'offset':
                    offset = keywords[0].value
                else:
                    refuse(node, 'struct.unpack_from takes a format, a buffer and an optional offset')
            elif len(args) == 2:
                offset = ast.Constant(value=0)
            elif len(args) == 3:
                offset = args[2]
            else:
                refuse(node, 'struct.unpack_from takes a format, a buffer and an optional offset')
            self.used = True
            return stdlib5.call(stdlib5.name(FUNCTIONS[attr]), [fmt_node, args[1], offset])
        if len(args) < 3:
            refuse(node, 'struct.pack_into takes a format, a buffer, an offset and the values')
        self.used = True
        values = ast.Tuple(elts=args[3:], ctx=ast.Load())
        return stdlib5.call(stdlib5.name(FUNCTIONS[attr]), [fmt_node, args[1], args[2], values])

    def visit_Attribute(self, node):
        found = self.binder.attr(node)
        if found == 'error':
            self.used_error = True
            return ast.copy_location(stdlib5.name(self.err_name), node)
        if found is not None:
            refuse(node, 'struct.%s is not built; %s' % (found, WHAT))
        return self.generic_visit(node)

    def visit_Name(self, node):
        found = self.binder.attr(node)
        if found == 'error':
            self.used_error = True
            return ast.copy_location(stdlib5.name(self.err_name), node)
        if found is not None:
            refuse(node, 'struct.%s used as a value is not built; call it instead' % found)
        return node


def rename_error(text, err_name):
    module = ast.parse(text)
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == 'error':
            node.name = err_name
        for each in ast.walk(node):
            if isinstance(each, ast.Name) and each.id == 'error':
                each.id = err_name
    ast.fix_missing_locations(module)
    return ast.unparse(module)


def run(tree):
    binder = stdlib5.take_imports(tree, 'struct', HANDLED, unknown=WHAT)
    if not binder:
        return False
    for local, attr in binder.names.items():
        if attr != 'error' and binds(tree, local):
            refuse(binder.first, '%s is also bound by the program itself and imported from struct; rename one'
                   % local)
    for alias in binder.aliases:
        if binds(tree, alias):
            refuse(binder.first, '%s is also bound by the program itself and stands for struct here; rename one'
                   % alias)
    uses_error = any(binder.attr(each) == 'error' for each in ast.walk(tree)
                     if isinstance(each, (ast.Name, ast.Attribute)))
    binds_error = binds(tree, 'error')
    if uses_error and binds_error:
        refuse(binder.first, 'the program binds the name error itself and also catches or names struct.error; '
                             'rename one')
    err_name = 'error' if (uses_error or not binds_error) else '_AilStructError'
    lower = Lower(binder, err_name)
    tree.body = [lower.visit(statement) for statement in tree.body]
    binder.names.clear()            # every from-imported name is lowered or refused above
    stdlib5.leftover(tree, binder, WHAT)
    if lower.used or lower.used_error:
        text = stdlib5.prelude('struct')
        if err_name != 'error':
            text = rename_error(text, err_name)
        stdlib5.insert_after_imports(tree, text)
    return True


def rewrite_text(source, notes=None):
    """The program text with `struct` lowered; the source as written (and `notes` filled) when a use is not
    built."""
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    imported = False
    for node in tree.body:
        if isinstance(node, ast.Import) and any(alias.name == 'struct' for alias in node.names):
            imported = True
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'struct':
            imported = True
    if not imported:
        return source
    try:
        if not run(tree):
            return source
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
