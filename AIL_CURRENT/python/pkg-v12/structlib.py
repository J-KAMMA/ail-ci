"""structlib.py -- `struct.pack` / `struct.unpack` / `struct.calcsize` lowered onto int.to_bytes / from_bytes.

The pass runs from ail_syntax.python_surface, so both compile paths see the same lowered source. It builds the
standard byte orders ('<', '>', '=' and '!') for the integer, bool, char, string, pascal-string and pad codes
(x c b B ? h H i I l L q s p), including repeat counts. Native byte order ('@' or no prefix), the float codes
(e f d), the native-only codes (n N P) and the unsigned 64-bit code Q (whose values can leave int64) are named
refusals, as is every name except pack, unpack and calcsize.
"""
import ast
from pathlib import Path

HERE = Path(__file__).parent
SUPPORTED = ('pack', 'unpack', 'calcsize')


class Refused(Exception):
    def __init__(self, line, text):
        Exception.__init__(self, text)
        self.line, self.text = line, text


def refuse(node, text):
    raise Refused(getattr(node, 'lineno', None) or 1, text)


def _check_literal(node, attr):
    """The plan of a literal format string, or None when the format is computed; an unbuilt literal is refused."""
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    value = node.args[0].value
    if isinstance(value, bytes):
        try:
            value = value.decode()
        except UnicodeDecodeError:
            refuse(node, 'struct.%s: a format string must be text' % attr)
    if not isinstance(value, str):
        refuse(node, 'struct.%s: a format string must be text' % attr)
    import prelude_struct
    try:
        return prelude_struct._ail_struct_plan(value)
    except prelude_struct.error as error:
        refuse(node, 'struct.%s: %s' % (attr, error))


_KIND_TAGS = {'int': 'i', 'bytes': 's', 'bool': 'z'}


def _wrapper_name(kinds):
    if not kinds:
        return '_ail_struct_unpack_0'
    return '_ail_struct_unpack_' + '_'.join(_KIND_TAGS[kind] for kind in kinds)


def _kinds(plan):
    kinds = []
    i = 0
    while i < plan[2]:
        code = plan[4 + 3 * i]
        count = plan[5 + 3 * i]
        if code == 12 or code == 13 or code == 1:
            kind = 'bytes'
            many = 1 if code != 1 else count
        elif code == 4:
            kind = 'bool'
            many = count
        elif code != 0:
            kind = 'int'
            many = count
        else:
            kind = None
            many = 0
        j = 0
        while j < many:
            kinds.append(kind)
            j += 1
        i += 1
    return kinds


class Binder:
    def __init__(self, tree):
        self.aliases = set()               # name bound to the struct module
        self.names = {}                    # name bound by `from struct import name`
        self.nodes = []
        body = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name == 'struct':
                        self.aliases.add(alias.asname or 'struct')
                        self.nodes.append(node)
                    else:
                        rest.append(alias)
                if len(rest) != len(node.names):
                    if rest:
                        node.names = rest
                        body.append(node)
                    continue
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'struct':
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from struct import *: name what you use')
                    self.names[alias.asname or alias.name] = alias.name
                self.nodes.append(node)
                continue
            body.append(node)
        tree.body = body

    def attr(self, node):
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in self.aliases):
            return node.attr
        return None


class Rewriter(ast.NodeTransformer):
    def __init__(self, binder):
        self.binder = binder
        self.used = False
        self.arities = {}

    def visit_Call(self, node):
        attr = self.binder.attr(node.func)
        if attr is None:
            return self.generic_visit(node)
        node.args = [self.visit(arg) for arg in node.args]
        for keyword in node.keywords:
            keyword.value = self.visit(keyword.value)
        if attr not in SUPPORTED:
            refuse(node, 'struct.%s is not built: only pack, unpack and calcsize are built' % attr)
        if node.keywords:
            refuse(node, 'struct.%s keyword arguments are not built' % attr)
        plan = _check_literal(node, attr)
        if attr == 'unpack':
            if plan is None:
                refuse(node, 'struct.unpack with a format that is not a string literal is not built: '
                       'write a literal format, or read the bytes by index')
            kinds = _kinds(plan)
            self.arities[tuple(kinds)] = kinds
            name = _wrapper_name(kinds)
        else:
            name = '_ail_struct_' + attr
        node.func = ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node.func)
        self.used = True
        return node

    def visit_Attribute(self, node):
        self.generic_visit(node)
        attr = self.binder.attr(node)
        if attr is not None:
            refuse(node, 'struct.%s used here is not built: only pack, unpack and calcsize are built' % attr)
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.binder.names:
            refuse(node, 'struct.%s used here is not built: only pack, unpack and calcsize are built'
                   % self.binder.names[node.id])
        return node


def _insert(tree, text, mark=True):
    from iterlower import _mark
    module = ast.parse(text)
    for stmt in module.body:
        if mark:
            _mark(stmt)
        for each in ast.walk(stmt):
            if 'lineno' in getattr(each, '_attributes', ()):
                each.lineno = each.end_lineno = 1
                each.col_offset = each.end_col_offset = 0
    index = 0
    body = tree.body
    while index < len(body) and (isinstance(body[index], (ast.Import, ast.ImportFrom)) or (
            isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
        index += 1
    tree.body = body[:index] + module.body + body[index:]


def _binds_error(tree):
    """Whether the program binds the top-level name `error`, which would collide with the helper class."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == 'error':
            return True
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == 'error':
            return True
        if isinstance(node, ast.ExceptHandler) and node.name == 'error':
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]) == 'error':
                    return True
    return False


def rewrite_text(source, notes=None):
    if 'struct' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    binder = Binder(tree)
    if not binder.nodes:
        return source
    rewriter = Rewriter(binder)
    try:
        tree = rewriter.visit(tree)
        ast.fix_missing_locations(tree)
        if rewriter.used:
            helper = (HERE / 'prelude_struct.py').read_text(encoding='utf-8')
            if _binds_error(tree):
                helper = helper.replace('class error(', 'class _AilStructError(').replace('error(', '_AilStructError(')
            wrappers = ''
            for kinds in sorted(rewriter.arities.values()):
                count = len(kinds)
                name = _wrapper_name(kinds)
                if count == 0:
                    wrappers += ('\n\ndef %s(fmt, data) -> tuple:\n'
                                 '    _ail_struct_unpack_list(fmt, data)\n    return ()\n' % name)
                else:
                    items = ', '.join('%s(values[%d])' % (kinds[i], i) for i in range(count))
                    comma = ',' if count == 1 else ''
                    wrappers += ('\n\ndef %s(fmt, data) -> tuple:\n'
                                 '    values = _ail_struct_unpack_list(fmt, data)\n'
                                 '    return (%s%s)\n' % (name, items, comma))
            _insert(tree, helper)
            if wrappers:
                _insert(tree, wrappers, mark=False)
        text = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    return text.rstrip('\n') + '\n'
