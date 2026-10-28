"""argparse.py -- lower the supported part of `argparse` onto prelude_argparse.py.

The parser object is ordinary Python in the prelude.  This pass removes the import, renames the
constructor, checks every `add_argument` (so anything outside the supported subset is refused by
name before the program is built), and adds a Namespace class whose attributes are exactly the
`dest` names of the parser's arguments.  `parse_args()` returns that object, so `args.output`
keeps its ordinary attribute spelling.

Supported: ArgumentParser(prog=..., description=..., add_help=..., allow_abbrev=...),
add_argument with a literal name (or names), action='store' (the default), no nargs, type in
(str, int, float, bool, pathlib.Path), default, required, choices, help, metavar and dest, and
parse_args() with no arguments or one sequence.  Everything else is a named refusal.
"""
import ast
import copy
import keyword
from pathlib import Path

HERE = Path(__file__).parent


class Refused(Exception):
    def __init__(self, line, text):
        Exception.__init__(self, text)
        self.line = line
        self.text = text


def refuse(node, text):
    raise Refused(getattr(node, 'lineno', None) or 1, text)


def prelude(name):
    lines = (HERE / ('prelude_%s.py' % name)).read_text(encoding='utf-8').splitlines()
    start = 0
    while start < len(lines) and (lines[start].startswith('#') or not lines[start].strip()):
        start += 1
    return '\n'.join(lines[start:]) + '\n'


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _string(node):
    value = _const(node)
    return value if isinstance(value, str) else None


def _type_name(node):
    if node is None:
        return None
    if isinstance(node, ast.Name) and node.id in ('str', 'int', 'float', 'bool'):
        return node.id
    if isinstance(node, ast.Name) and node.id == 'Path':
        return 'Path'
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == 'pathlib' and node.attr == 'Path'):
        return 'Path'
    return ''


class Rewrite:
    def __init__(self, tree):
        self.tree = tree
        self.module_aliases = set()
        self.class_names = set()
        self.parser_names = set()
        self.result_names = set()
        self.dests = []
        self.extra = []
        self.allowed = set()
        self.allowed_names = set()
        self.need_path = False
        self.path_bound = False
        self.path_dests = []
        self.path_optional = set()

    def line(self, node):
        return getattr(node, 'lineno', None) or 1

    def add_dest(self, dest, node):
        if not dest.isidentifier() or keyword.iskeyword(dest):
            refuse(node, 'argparse: destination %r is not a usable attribute name' % dest)
        if dest not in self.dests:
            self.dests.append(dest)

    def is_constructor(self, node):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id in self.module_aliases and func.attr == 'ArgumentParser':
            return True
        return isinstance(func, ast.Name) and func.id in self.class_names

    def take_imports(self):
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'pathlib':
                for alias in node.names:
                    if alias.name == 'Path' and (alias.asname in (None, 'Path')):
                        self.path_bound = True
        body = []
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name == 'argparse':
                        self.module_aliases.add(alias.asname or 'argparse')
                    else:
                        rest.append(alias)
                if rest:
                    node.names = rest
                    body.append(node)
                continue
            if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'argparse':
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from argparse import *: name what you use')
                    if alias.name == 'ArgumentParser':
                        self.class_names.add(alias.asname or 'ArgumentParser')
                    else:
                        refuse(node, 'argparse.%s is not built: only ArgumentParser is supported' % alias.name)
                continue
            if isinstance(node, ast.ImportFrom) and node.module in ('pathlib',):
                body.append(node)
                continue
            body.append(node)
        self.tree.body = body

    def find_parsers(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if self.is_constructor(value):
                    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                        refuse(node, 'argparse.ArgumentParser() must be assigned to one name')
                    self.parser_names.add(targets[0].id)
                    self.check_constructor(value)
                    value.func = ast.Name(id='_AilArgumentParser', ctx=ast.Load())
                    ast.copy_location(value.func, value)

    def check_constructor(self, call):
        for key in call.keywords:
            if key.arg not in ('prog', 'description', 'add_help', 'allow_abbrev'):
                refuse(key.value, 'argparse.ArgumentParser(%s=...) is not built' % (key.arg or '**'))
        if len(call.args) > 0:
            refuse(call, 'argparse.ArgumentParser() takes keyword arguments only in this compiler')

    def check_add(self, call):
        names = []
        for arg in call.args:
            if isinstance(arg, ast.Starred):
                refuse(arg, 'argparse.add_argument(*names) is not built')
            text = _string(arg)
            if text is None:
                refuse(arg, 'argparse.add_argument() needs a literal argument name')
            names.append(text)
        if not names:
            refuse(call, 'argparse.add_argument() needs at least one name')
        option = False
        for name in names:
            if name.startswith('-'):
                option = True
        with_dash = 0
        for name in names:
            if name.startswith('-'):
                with_dash += 1
        if with_dash != 0 and with_dash != len(names):
            refuse(call, 'argparse.add_argument() cannot mix positional and option names')
        kwargs = {}
        for key in call.keywords:
            if key.arg is None:
                refuse(key.value, 'argparse.add_argument(**kwargs) is not built')
            if key.arg not in ('action', 'nargs', 'const', 'default', 'type', 'choices', 'required',
                               'help', 'metavar', 'dest'):
                refuse(key.value, 'argparse.add_argument(%s=...) is not built' % key.arg)
            kwargs[key.arg] = key.value
        action = _string(kwargs.get('action')) if 'action' in kwargs else 'store'
        if action != 'store':
            refuse(kwargs.get('action', call), 'argparse.add_argument(action=%r) is not built: only action="store"'
                   % action)
        if 'nargs' in kwargs:
            value = _const(kwargs['nargs'])
            if value is not None:
                refuse(kwargs['nargs'], 'argparse.add_argument(nargs=...) is not built')
        if 'const' in kwargs:
            value = _const(kwargs['const'])
            if value is not None:
                refuse(kwargs['const'], 'argparse.add_argument(const=...) is not built')
        if 'help' in kwargs:
            value = _const(kwargs['help'])
            if value is not None and not isinstance(value, str):
                refuse(kwargs['help'], 'argparse.add_argument(help=...) needs a string or None')
        if 'metavar' in kwargs:
            value = _const(kwargs['metavar'])
            if value is not None and not isinstance(value, str):
                refuse(kwargs['metavar'], 'argparse.add_argument(metavar=...) needs a string or None')
        if 'dest' in kwargs:
            dest = _string(kwargs['dest'])
            if dest is None:
                refuse(kwargs['dest'], 'argparse.add_argument(dest=...) needs a string')
        elif option:
            dest = None
            for name in names:
                if name.startswith('--'):
                    dest = name
                    break
            if dest is None:
                dest = names[0]
            while dest.startswith('-'):
                dest = dest[1:]
            dest = dest.replace('-', '_')
        else:
            dest = names[0]
        self.add_dest(dest, call)
        if 'type' in kwargs:
            label = _type_name(kwargs['type'])
            if label == '':
                refuse(kwargs['type'], 'argparse.add_argument(type=...) is not built: use str, int, float, '
                       'bool or pathlib.Path')
            if label is not None:
                if label == 'Path' and 'default' in kwargs:
                    default = kwargs['default']
                    if isinstance(default, ast.Call) and _type_name(default.func) == 'Path':
                        wrapped = ast.Call(func=ast.Name(id='str', ctx=ast.Load()), args=[default],
                                           keywords=[])
                        ast.copy_location(wrapped, default)
                        ast.copy_location(wrapped.func, default)
                        for key in call.keywords:
                            if key.arg == 'default':
                                key.value = wrapped
                call.keywords = [key for key in call.keywords if key.arg != 'type']
                if label == 'Path':
                    self.need_path = True
                    if dest not in self.path_dests:
                        self.path_dests.append(dest)
                    required = kwargs.get('required')
                    guaranteed = isinstance(required, ast.Constant) and required.value is True
                    if not guaranteed and 'default' in kwargs:
                        default = kwargs['default']
                        if isinstance(default, ast.Constant):
                            guaranteed = default.value is not None
                        elif isinstance(default, ast.Call):
                            guaranteed = _type_name(default.func) == 'Path'
                    if not guaranteed:
                        self.path_optional.add(dest)
                call.keywords.append(ast.keyword(arg='_ail_type_name', value=ast.Constant(value=label)))
        return option

    def run(self):
        self.take_imports()
        self.find_parsers()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                        and isinstance(node.value.func.value, ast.Name) \
                        and node.value.func.value.id in self.parser_names \
                        and node.value.func.attr == 'parse_args':
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.result_names.add(target.id)
        statements = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                statements.add(id(node.value))
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                base = node.func.value
                if isinstance(base, ast.Name) and base.id in self.parser_names:
                    attr = node.func.attr
                    if attr == 'add_argument':
                        if id(node) not in statements:
                            refuse(node, 'the action returned by argparse.add_argument() is not built')
                        self.check_add(node)
                        self.allowed.add(id(node.func))
                        self.allowed_names.add(id(base))
                    elif attr == 'parse_args':
                        if len(node.args) > 1 or node.keywords:
                            refuse(node, 'argparse.parse_args() takes no arguments or one sequence')
                        self.allowed.add(id(node.func))
                        self.allowed_names.add(id(base))
                    else:
                        refuse(node.func, 'argparse parser.%s() is not built' % attr)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in self.result_names:
                if node.attr not in self.dests:
                    refuse(node, 'argparse Namespace has no argument destination %r' % node.attr)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in ('getattr', 'setattr') and node.args \
                    and isinstance(node.args[0], ast.Name) and node.args[0].id in self.result_names:
                refuse(node, 'argparse Namespace %s() is not built: read args.<dest>' % node.func.id)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'vars' \
                    and node.args and isinstance(node.args[0], ast.Name) \
                    and node.args[0].id in self.result_names and self.path_dests:
                refuse(node, 'vars() of an argparse Namespace with a path destination is not built')
        self.rewrite_path_reads()
        self.check_leftovers()

    def rewrite_path_reads(self):
        if not self.path_dests:
            return
        path_dests = self.path_dests
        path_optional = self.path_optional

        class PathReads(ast.NodeTransformer):
            def visit_Attribute(self, node):
                self.generic_visit(node)
                if node.attr in path_dests and isinstance(node.ctx, ast.Load):
                    call = ast.Call(func=ast.Name(id='Path', ctx=ast.Load()), args=[node], keywords=[])
                    ast.copy_location(call, node)
                    ast.copy_location(call.func, node)
                    if node.attr in path_optional:
                        test = ast.Compare(left=copy.deepcopy(node), ops=[ast.IsNot()],
                                           comparators=[ast.Constant(value=None)])
                        guarded = ast.IfExp(test=test, body=call, orelse=ast.Constant(value=None))
                        ast.copy_location(test, node)
                        ast.copy_location(guarded, node)
                        return guarded
                    return call
                return node

        self.tree = PathReads().visit(self.tree)
        ast.fix_missing_locations(self.tree)

    def check_leftovers(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in self.module_aliases:
                refuse(node, 'argparse.%s is not built' % node.attr)
            if isinstance(node, ast.Name) and node.id in self.module_aliases and isinstance(node.ctx, ast.Load):
                refuse(node, 'the argparse module is not built as a value')
            if isinstance(node, ast.Name) and node.id in self.class_names and isinstance(node.ctx, ast.Load):
                refuse(node, 'argparse.ArgumentParser used as a value is not built')
            if isinstance(node, ast.Name) and node.id in self.parser_names and isinstance(node.ctx, ast.Load) \
                    and id(node) not in self.allowed_names:
                refuse(node, 'an argparse parser used as a value is not built')
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in self.parser_names and id(node) not in self.allowed:
                refuse(node, 'argparse parser.%s is not built' % node.attr)


def namespace_source(dests, extra, path_dests=()):
    names = list(dests)
    for name in extra:
        if name not in names:
            names.append(name)
    paths = set(path_dests)
    lines = ['class _AilNamespace:', '    def __init__(self, values) -> None:']
    if not dests:
        lines.append('        pass')
    else:
        for name in dests:
            lines.append('        if "%s" in values:' % name)
            lines.append('            self.%s = values["%s"]' % (name, name))
    lines.append('    def __repr__(self) -> str:')
    lines.append('        parts = []')
    for name in names:
        lines.append('        if hasattr(self, "%s"):' % name)
        if name in paths:
            lines.append('            if self.%s is None:' % name)
            lines.append('                parts.append("%s=None")' % name)
            lines.append('            else:')
            lines.append('                parts.append("%s=" + repr(Path(self.%s)))' % (name, name))
        else:
            lines.append('            parts.append("%s=" + repr(self.%s))' % (name, name))
    lines.append('        return "Namespace(" + ", ".join(parts) + ")"')
    lines.append('    def __eq__(self, other) -> bool:')
    lines.append('        if not isinstance(other, _AilNamespace):')
    lines.append('            return False')
    lines.append('        return vars(self) == vars(other)')
    return '\n'.join(lines) + '\n'


def rewrite_text(source, notes=None):
    if 'argparse' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) and (
            (isinstance(n, ast.Import) and any(a.name == 'argparse' for a in n.names))
            or (isinstance(n, ast.ImportFrom) and not n.level and n.module == 'argparse'))
            for n in tree.body):
        return source
    rewrite = Rewrite(tree)
    try:
        rewrite.run()
        chunks = [prelude('argparse'), namespace_source(rewrite.dests, rewrite.extra, rewrite.path_dests)]
        added = []
        if rewrite.need_path and not rewrite.path_bound:
            added.extend(ast.parse('from pathlib import Path\n').body)
        for chunk in chunks:
            added.extend(ast.parse(chunk).body)
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom))
                                          or (isinstance(tree.body[index], ast.Expr)
                                              and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body[index:index] = added
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the argparse lowering could not handle this program (%s: %s); simplify the use '
                          'or report it' % (type(exc).__name__, exc)))
        return source
