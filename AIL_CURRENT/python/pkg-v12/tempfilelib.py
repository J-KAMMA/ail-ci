"""tempfile: gettempdir, mkdtemp and TemporaryDirectory lowered onto os (prelude_tempfile.py).

Called from stdlib5.py on the parsed module. `tempfile.gettempdir()`, `tempfile.mkdtemp(...)` and
`tempfile.TemporaryDirectory(...)` become a small prelude that uses the file layer's `os` functions.
The arguments suffix=, prefix= and dir= are built (positionally or by keyword); everything else --
NamedTemporaryFile, TemporaryFile, SpooledTemporaryFile, mkstemp, mktemp, gettempdirb,
gettempprefixb, tempdir, and TemporaryDirectory(ignore_cleanup_errors=/delete=) -- is refused by name.

TemporaryDirectory is built where its lifetime is explicit: directly in a `with`, or assigned to a
name that is later given a `.cleanup()` call.  CPython's finalizer that removes the directory when
the object is merely garbage-collected is not built, so other uses (a bare object returned or kept
without cleanup, or `TemporaryDirectory(...).name`) are refused by name instead of leaking the tree.
Arguments that are statically bytes are refused like a bytes literal; a value that only reaches the
call at run time is caught by the prelude with a named TypeError.
"""
import ast

import stdlib5
from stdlib4 import refuse

HANDLED = {'gettempdir', 'mkdtemp', 'TemporaryDirectory'}
PARAMETERS = ('suffix', 'prefix', 'dir')


def _literal_kind(node):
    """The kind of a literal expression: bytes, str, none, byteslist/strlist, bytesdict/strdict."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bytes):
            return 'bytes'
        if isinstance(node.value, str):
            return 'str'
        if node.value is None:
            return 'none'
        return None
    if isinstance(node, (ast.List, ast.Tuple)):
        kinds = {_literal_kind(element) for element in node.elts}
        for kind in ('bytes', 'str'):
            if kinds == {kind}:
                return kind + 'list'
        return None
    if isinstance(node, ast.Dict):
        kinds = {_literal_kind(value) for value in node.values}
        for kind in ('bytes', 'str'):
            if kinds == {kind}:
                return kind + 'dict'
        return None
    return None


def _own_nodes(root):
    """The nodes of one lexical scope, without descending into a nested function, lambda or class."""
    def walk(node, top):
        if not top and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from walk(child, False)
    return walk(root, True)


class _Types:
    """A small, conservative static type map: which names/items/attributes are definitely bytes."""

    def __init__(self, tree):
        self.parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent
        self.scopes = {}
        self.attrs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                        annotation = statement.annotation
                        if isinstance(annotation, ast.Name) and annotation.id == 'bytes':
                            self.attrs.add(statement.target.id)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Attribute) and _literal_kind(node.value) == 'bytes':
                self.attrs.add(node.targets[0].attr)

    def scope_of(self, node):
        parent = self.parents.get(node)
        while parent is not None and not isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = self.parents.get(parent)
        return parent

    def info(self, scope):
        if scope in self.scopes:
            return self.scopes[scope]
        values = {}
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = list(scope.args.posonlyargs) + list(scope.args.args) + list(scope.args.kwonlyargs)
            for argument in arguments:
                annotation = argument.annotation
                if isinstance(annotation, ast.Name) and annotation.id in ('bytes', 'str'):
                    values[argument.arg] = annotation.id
        nodes = list(_own_nodes(scope))
        for _ in range(4):
            for node in nodes:
                if isinstance(node, ast.Assign):
                    targets, value = node.targets, node.value
                elif isinstance(node, ast.AnnAssign):
                    targets, value = [node.target], node.value
                else:
                    continue
                if value is None or len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    continue
                kind = self.kind(value, values)
                if kind is not None:
                    values[targets[0].id] = kind
        self.scopes[scope] = values
        return values

    def kind(self, node, values):
        literal = _literal_kind(node)
        if literal is not None:
            return literal
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.JoinedStr):
            return 'str'
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self.kind(node.left, values), self.kind(node.right, values)
            return left if left == right else None
        if isinstance(node, ast.IfExp):
            body, orelse = self.kind(node.body, values), self.kind(node.orelse, values)
            return body if body == orelse else None
        return None

    def is_bytes(self, node, scope):
        values = self.info(scope)
        if self.kind(node, values) == 'bytes':
            return True
        if isinstance(node, ast.Subscript) and self.kind(node.value, values) in ('byteslist', 'bytesdict'):
            return True
        if isinstance(node, ast.Attribute) and node.attr in self.attrs:
            return True
        return False

    def has_cleanup(self, scope, name):
        for node in _own_nodes(scope):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'cleanup' and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == name:
                return True
        return False

    def lifetime_is_explicit(self, node):
        """True for `with TemporaryDirectory(...)` and `x = TemporaryDirectory(...)` with a later
        `x.cleanup()`; the CPython finalizer is not built, so every other use is refused."""
        parent = self.parents.get(node)
        if isinstance(parent, ast.withitem) and parent.context_expr is node:
            return True
        if isinstance(parent, ast.Assign):
            targets, value = parent.targets, parent.value
        elif isinstance(parent, ast.AnnAssign):
            targets, value = [parent.target], parent.value
        else:
            return False
        if value is not node or len(targets) != 1 or not isinstance(targets[0], ast.Name):
            return False
        return self.has_cleanup(self.scope_of(node), targets[0].id)


def _arguments(node, what, types):
    """The (suffix, prefix, dir) argument nodes of a mkdtemp/TemporaryDirectory call."""
    for argument in node.args:
        if isinstance(argument, ast.Starred):
            refuse(node, 'tempfile.%s(*args) is not built' % what)
    if len(node.args) > 3:
        refuse(node, 'tempfile.%s() takes suffix, prefix and dir here' % what)
    values = {}
    for index, argument in enumerate(node.args):
        values[PARAMETERS[index]] = argument
    for keyword in node.keywords:
        if keyword.arg is None:
            refuse(keyword.value, 'tempfile.%s(**kwargs) is not built' % what)
        if keyword.arg not in PARAMETERS:
            refuse(keyword.value, 'tempfile.%s(%s=) is not built' % (what, keyword.arg))
        if keyword.arg in values:
            refuse(keyword.value, 'tempfile.%s() got multiple values for %s' % (what, keyword.arg))
        values[keyword.arg] = keyword.value
    scope = types.scope_of(node)
    for parameter, value in values.items():
        if isinstance(value, ast.Constant) and not (value.value is None or isinstance(value.value, str)):
            refuse(value, 'tempfile.%s(%s=) is built for str values only' % (what, parameter))
        if types.is_bytes(value, scope):
            refuse(value, 'tempfile.%s(%s=) is built for str values only (bytes is not built)'
                   % (what, parameter))
    suffix = values.get('suffix', ast.Constant(value=''))
    prefix = values.get('prefix', stdlib5.call(stdlib5.name('_ail_tempfile_gettempprefix'), []))
    directory = values.get('dir', stdlib5.call(stdlib5.name('_ail_tempfile_gettempdir'), []))
    if isinstance(suffix, ast.Constant) and suffix.value is None:
        suffix = ast.Constant(value='')
    if isinstance(prefix, ast.Constant) and prefix.value is None:
        prefix = stdlib5.call(stdlib5.name('_ail_tempfile_gettempprefix'), [])
    if isinstance(directory, ast.Constant) and directory.value is None:
        directory = stdlib5.call(stdlib5.name('_ail_tempfile_gettempdir'), [])
    return suffix, prefix, directory


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'tempfile', HANDLED,
                                  unknown='gettempdir, mkdtemp and TemporaryDirectory are the names that are built')
    if not binder:
        return
    used = set()
    types = _Types(tree)

    class Lower(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            found = binder.attr(node.func)
            if found is None:
                return node
            if found == 'gettempdir':
                if node.args or node.keywords:
                    refuse(node, 'tempfile.gettempdir() takes no arguments')
                used.add('_ail_tempfile_gettempdir')
                return ast.copy_location(stdlib5.call(stdlib5.name('_ail_tempfile_gettempdir'), []), node)
            if found == 'mkdtemp':
                suffix, prefix, directory = _arguments(node, 'mkdtemp', types)
                used.update(('_ail_tempfile_mkdtemp', '_ail_tempfile_gettempdir', '_ail_tempfile_gettempprefix'))
                return ast.copy_location(stdlib5.call(stdlib5.name('_ail_tempfile_mkdtemp'),
                                                      [suffix, prefix, directory]), node)
            if found == 'TemporaryDirectory':
                if not types.lifetime_is_explicit(node):
                    refuse(node, 'tempfile.TemporaryDirectory() without cleanup() is not built: '
                                 'use `with tempfile.TemporaryDirectory(...) as name` or call '
                                 '.cleanup() (the garbage-collection finalizer is not built)')
                suffix, prefix, directory = _arguments(node, 'TemporaryDirectory', types)
                used.update(('_AilTemporaryDirectory', '_ail_tempfile_mkdtemp', '_ail_tempfile_gettempdir',
                             '_ail_tempfile_gettempprefix'))
                return ast.copy_location(stdlib5.call(stdlib5.name('_AilTemporaryDirectory'),
                                                      [suffix, prefix, directory]), node)
            refuse(node, 'tempfile.%s is not built: gettempdir, mkdtemp and TemporaryDirectory are' % found)
            return node

    tree.body = [Lower().visit(statement) for statement in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, 'gettempdir, mkdtemp and TemporaryDirectory are the forms that are built')

    has_os = False
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == 'os' and alias.asname is None:
                    has_os = True
    if not has_os:
        tree.body.insert(0, ast.Import(names=[ast.alias(name='os', asname=None)]))
    text.append(stdlib5.shake(stdlib5.prelude('tempfile'), used))
