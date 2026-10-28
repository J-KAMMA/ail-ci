"""argparse: long options and positionals lowered onto a small Python prelude (prelude_argparse.py).

Called from stdlib5.py on the parsed module. `parser = argparse.ArgumentParser(...)`, the
`parser.add_argument(...)` calls and `args = parser.parse_args()` are lowered to a prelude class; an
`args.name` read becomes the declared conversion of the parsed string. Built: long `--name` options,
positionals, `type=` int / float / str / pathlib.Path, `default=`, `required=`, `choices=` and
`help=` (ignored). Everything else -- short options, store_true / append / other actions, nargs,
subparsers, groups, the help text -- is refused by name.
"""
import ast
import copy

import stdlib5
from stdlib4 import refuse

HANDLED = {'ArgumentParser'}
ALLOWED = {'type', 'default', 'required', 'choices', 'help', 'dest', 'action', 'nargs'}


def call(func, args):
    return ast.Call(func=func, args=list(args), keywords=[])


def name(identifier, ctx=None):
    return ast.Name(id=identifier, ctx=ctx or ast.Load())


def constant(value):
    return ast.Constant(value=value)


def _string(node, what):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        refuse(node, 'argparse %s must be a string literal' % what)
    return node.value


def _parser_call(node):
    """Validate an ArgumentParser(...) call and return description/prog/add_help keywords."""
    if node.args:
        refuse(node, 'argparse.ArgumentParser() takes its arguments by keyword here (description=, prog=, add_help=)')
    found = {}
    for kw in node.keywords:
        if kw.arg is None:
            refuse(kw.value, 'argparse.ArgumentParser(**kwargs) is not built')
        if kw.arg not in ('description', 'prog', 'add_help'):
            refuse(kw.value, 'argparse.ArgumentParser(%s=) is not built' % kw.arg)
        found[kw.arg] = kw.value
    return [ast.keyword(arg='description', value=found.get('description', constant(''))),
            ast.keyword(arg='prog', value=found.get('prog', constant(''))),
            ast.keyword(arg='add_help', value=found.get('add_help', constant(True)))]


def _add_argument(node):
    """(name, dest, kind, conv, required, default, choices) for one add_argument call."""
    if any(isinstance(a, ast.Starred) for a in node.args):
        refuse(node, 'argparse.add_argument(*args) is not built')
    if len(node.args) != 1:
        refuse(node, 'argparse.add_argument() is built for one option or positional name')
    option = _string(node.args[0], 'argument name')
    if option.startswith('--') and len(option) > 2:
        kind, dest = 'opt', option[2:].replace('-', '_')
    elif option.startswith('-'):
        refuse(node, 'argparse short options are not built; write --%s' % option.lstrip('-'))
    elif option == '':
        refuse(node, 'argparse.add_argument("") is not built')
    else:
        kind, dest = 'pos', option
    values = {}
    for kw in node.keywords:
        if kw.arg is None:
            refuse(kw.value, 'argparse.add_argument(**kwargs) is not built')
        if kw.arg not in ALLOWED:
            refuse(kw.value, 'argparse.add_argument(%s=) is not built' % kw.arg)
        values[kw.arg] = kw.value
    if 'dest' in values:
        dest = _string(values['dest'], 'dest')
    conv = 'str'
    if 'type' in values:
        each = values['type']
        if isinstance(each, ast.Name) and each.id in ('int', 'float', 'str'):
            conv = each.id
        elif isinstance(each, ast.Constant) and each.value is None:
            conv = 'str'
        elif isinstance(each, ast.Name) and each.id == 'Path':
            conv = 'path'
        elif isinstance(each, ast.Attribute) and each.attr == 'Path' \
                and isinstance(each.value, ast.Name) and each.value.id == 'pathlib':
            conv = 'path'
        else:
            refuse(each, 'argparse.add_argument(type=) is built for int, float, str and pathlib.Path')
    required = False
    if 'required' in values:
        each = values['required']
        if not isinstance(each, ast.Constant) or not isinstance(each.value, bool):
            refuse(each, 'argparse.add_argument(required=) must be True or False')
        required = each.value
    if kind == 'pos':
        required = True
    if 'action' in values:
        each = values['action']
        if not (isinstance(each, ast.Constant) and each.value in ('store', None)):
            refuse(each, "argparse.add_argument(action=) is built only for the default 'store'")
    if 'nargs' in values:
        each = values['nargs']
        if not (isinstance(each, ast.Constant) and each.value is None):
            refuse(each, 'argparse.add_argument(nargs=) is not built')
    default = constant('\x00')
    if 'default' in values:
        each = values['default']
        if isinstance(each, ast.Constant) and each.value is None:
            default = constant('\x00')
        elif isinstance(each, ast.Constant) and isinstance(each.value, str):
            default = constant(each.value)
        elif conv == 'int' and isinstance(each, ast.Constant) \
                and isinstance(each.value, int) and not isinstance(each.value, bool):
            default = call(name('str'), [each])
        elif conv == 'float' and isinstance(each, ast.Constant) and isinstance(each.value, float):
            default = call(name('str'), [each])
        elif conv == 'path' and isinstance(each, ast.Call) \
                and (getattr(each.func, 'id', None) == 'Path'
                     or (isinstance(each.func, ast.Attribute) and each.func.attr == 'Path'
                         and isinstance(each.func.value, ast.Name) and each.func.value.id == 'pathlib')):
            default = call(name('str'), [each])
        else:
            refuse(each, 'argparse.add_argument(default=) is built for None, a matching literal '
                         '(str with type=str, int with type=int, float with type=float, Path(...) '
                         'with type=Path), or a string with a converting type')
    if conv == 'path' and kind == 'opt' and not required \
            and not ('default' in values and not (isinstance(values['default'], ast.Constant)
                                                  and values['default'].value is None)):
        refuse(node, 'argparse.add_argument(type=Path) needs required=True or a default= here: '
                    'an absent value would be None and Path(None) is not built')
    choices = ast.List(elts=[], ctx=ast.Load())
    if 'choices' in values:
        each = values['choices']
        if not isinstance(each, (ast.Tuple, ast.List)):
            refuse(each, 'argparse.add_argument(choices=) is built for a literal tuple or list')
        items = []
        for item in each.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                refuse(item, 'argparse.add_argument(choices=) is built for string literals')
            items.append(constant(item.value))
        if len(items) == 0:
            refuse(each, 'argparse.add_argument(choices=) with no choices is not built')
        choices = ast.List(elts=items, ctx=ast.Load())
    return option, dest, kind, conv, required, default, choices


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'argparse', HANDLED,
                                  unknown='ArgumentParser is the one name of the module that is built')
    if not binder:
        return
    parsers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call) and binder.attr(node.value.func) == 'ArgumentParser':
            parsers.add(node.targets[0].id)
    if not parsers:
        binder.names.clear()
        stdlib5.leftover(tree, binder, 'parser = argparse.ArgumentParser(...) is the form that is built')
        return
    path_ctor = None
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.name == 'pathlib':
                    path_ctor = ast.Attribute(value=name(alias.asname or 'pathlib'), attr='Path',
                                              ctx=ast.Load())
        elif isinstance(stmt, ast.ImportFrom) and stmt.module == 'pathlib':
            for alias in stmt.names:
                if alias.name == 'Path':
                    path_ctor = name(alias.asname or 'Path')
    specs = {each: [] for each in parsers}
    args_of = {}

    class Lower(ast.NodeTransformer):
        def visit_Call(self, node):
            found = binder.attr(node.func)
            if found == 'ArgumentParser':
                node.keywords = _parser_call(node)
                node.func = name('_AilArgumentParser')
                return self.generic_visit(node)
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in parsers:
                parser = node.func.value.id
                if node.func.attr == 'add_argument':
                    spec = _add_argument(node)
                    specs[parser].append(spec)
                    option, dest, kind, conv, required, default, choices = spec
                    return ast.copy_location(call(ast.Attribute(value=node.func.value, attr='add_argument',
                                                                ctx=ast.Load()),
                                                  [constant(option), constant(dest), constant(kind), constant(conv),
                                                   constant(required), default, choices]), node)
                if node.func.attr == 'parse_args':
                    if len(node.args) > 1 or node.keywords:
                        refuse(node, 'argparse.parse_args() is built with no argument or one list of strings')
                    if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value is None:
                        refuse(node, 'argparse.parse_args(None) is not built; omit the argument or pass a list')
                    argv = node.args[0] if node.args else ast.Subscript(
                        value=ast.Attribute(value=name('sys'), attr='argv', ctx=ast.Load()),
                        slice=ast.Slice(lower=constant(1), upper=None, step=None), ctx=ast.Load())
                    return ast.copy_location(call(ast.Attribute(value=node.func.value, attr='parse_args',
                                                                ctx=ast.Load()), [argv]), node)
                refuse(node, 'argparse.ArgumentParser.%s is not built' % node.func.attr)
            return self.generic_visit(node)

        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                    and node.value.func.attr == 'parse_args' \
                    and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id in parsers:
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    refuse(node, 'argparse.parse_args() is built when assigned to one name')
                args_of[node.targets[0].id] = node.value.func.value.id
            return node

    tree.body = [Lower().visit(stmt) for stmt in tree.body]
    if args_of and not any(isinstance(s, ast.Import) and any(a.name == 'sys' for a in s.names)
                           for s in tree.body):
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body.insert(index, ast.Import(names=[ast.alias(name='sys', asname=None)]))
    by_dest = {}
    for parser in parsers:
        by_dest[parser] = {spec[1]: spec for spec in specs[parser]}

    class Read(ast.NodeTransformer):
        def visit_Attribute(self, node):
            node = self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id in args_of:
                if isinstance(node.ctx, ast.Store):
                    refuse(node, 'writing an argparse Namespace attribute is not built')
                parser = args_of[node.value.id]
                spec = by_dest[parser].get(node.attr)
                if spec is None:
                    refuse(node, 'argparse Namespace attribute %r is not one of the declared arguments' % node.attr)
                conv = spec[3]
                raw = constant('str') if conv == 'path' else constant(conv)
                kept = ast.Name(id=node.value.id, ctx=ast.Load())
                kept._ail_args_ok = True
                getter = call(name('_ail_argparse_get'), [kept, constant(node.attr), raw])
                if conv == 'path':
                    if path_ctor is None:
                        refuse(node, 'argparse type=Path needs Path or pathlib.Path imported')
                    return ast.copy_location(call(copy.deepcopy(path_ctor), [getter]), node)
                return ast.copy_location(getter, node)
            return node

    tree.body = [Read().visit(stmt) for stmt in tree.body]

    class Bare(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in args_of and not getattr(node, '_ail_args_ok', False):
                refuse(node, 'the argparse Namespace used as a value is not built; read args.name instead')
    for stmt in tree.body:
        Bare().visit(stmt)
    binder.names.clear()
    stdlib5.leftover(tree, binder, 'ArgumentParser, add_argument and parse_args are the forms that are built')
    text.append(stdlib5.prelude('argparse'))
