"""tempfile: gettempdir, mkdtemp and TemporaryDirectory lowered onto os (prelude_tempfile.py).

Called from stdlib5.py on the parsed module. `tempfile.gettempdir()`, `tempfile.mkdtemp(...)` and
`tempfile.TemporaryDirectory(...)` become a small prelude that uses the file layer's `os` functions.
The arguments suffix=, prefix= and dir= are built (positionally or by keyword); everything else --
NamedTemporaryFile, TemporaryFile, SpooledTemporaryFile, mkstemp, mktemp, gettempdirb,
gettempprefixb, tempdir, and TemporaryDirectory(ignore_cleanup_errors=/delete=) -- is refused by name.
"""
import ast

import stdlib5
from stdlib4 import refuse

HANDLED = {'gettempdir', 'mkdtemp', 'TemporaryDirectory'}
PARAMETERS = ('suffix', 'prefix', 'dir')


def _arguments(node, what):
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
    for parameter, value in values.items():
        if isinstance(value, ast.Constant) and not (value.value is None or isinstance(value.value, str)):
            refuse(value, 'tempfile.%s(%s=) is built for str values only' % (what, parameter))
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
                suffix, prefix, directory = _arguments(node, 'mkdtemp')
                used.update(('_ail_tempfile_mkdtemp', '_ail_tempfile_gettempdir', '_ail_tempfile_gettempprefix'))
                return ast.copy_location(stdlib5.call(stdlib5.name('_ail_tempfile_mkdtemp'),
                                                      [suffix, prefix, directory]), node)
            if found == 'TemporaryDirectory':
                suffix, prefix, directory = _arguments(node, 'TemporaryDirectory')
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
