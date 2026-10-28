"""argparse (library batch 8): ArgumentParser / add_argument / parse_args lowered to the program.

Only the form a program writes directly is built: a parser name assigned once from
`ArgumentParser(...)`, `add_argument(...)` statements on that name, and
`NAME = parser.parse_args([args])`.  The parse itself becomes ordinary Python over a
`list[str]` (sys.argv[1:] or the explicit list), so it runs on both builds and uses no
runtime module.  A use outside that shape is refused by name.

Supported add_argument keywords: type (str, int, float, Path / pathlib.Path), default,
required, choices (a tuple/list of literals), action (store, store_true, store_false),
dest, help, metavar.  Positionals, several option strings for one argument, long
`--opt=value`, short `-cVALUE` / `-c=VALUE`, short clusters (-vv, -qv), `--`, and a
negative number used as a positional are understood.  Not built (named refusal): nargs,
const, action other than the three above, an optional argument with neither a default nor
required=True, any other keyword, a second parse_args on the same parser, and help.  A
parser with add_help=True is only lowered when the argv is a literal list/tuple with no
help token anywhere before `--`; a runtime argv (sys.argv) or a literal `-h`/`--help`
(including an abbreviation such as `--he`) is refused, so no approximate help is printed.
"""
import ast

import stdlib5
from stdlib4 import refuse

_HELP = 'show this help message and exit'


class Arg:
    def __init__(self, names, dest, positional, typeexpr, default, required, choices, action):
        self.names = names
        self.name = names[0]
        self.dest = dest
        self.positional = positional
        self.typeexpr = typeexpr
        self.default = default
        self.required = required
        self.choices = choices
        self.action = action


class Parser:
    def __init__(self, name):
        self.name = name
        self.args = []
        self.by_dest = {}
        self.by_name = {}
        self.add_help = True
        self.description = None

    def add(self, arg):
        if arg.dest in self.by_dest:
            refuse(None, 'argparse: two arguments use the destination %r' % arg.dest)
        for option in arg.names:
            if option in self.by_name:
                refuse(None, 'argparse: the option string %r is used twice' % option)
            self.by_name[option] = arg
        self.args.append(arg)
        self.by_dest[arg.dest] = arg

    def hidden(self, dest):
        return '_ail_argparse_%s_arg_%s' % (self.name, dest)

    def flag(self, dest):
        return self.hidden(dest) + '_set'


def _is_parser_call(node, binder):
    return isinstance(node, ast.Call) and binder.attr(node.func) == 'ArgumentParser'


def _is_parse_call(node, parsers):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id in parsers
            and node.func.attr == 'parse_args')


def _is_add_call(node, parsers):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id in parsers
            and node.func.attr == 'add_argument')


def _const_str(node, what):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    refuse(node, 'argparse: %s must be a string literal' % what)


def _const_bool(node, what):
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    refuse(node, 'argparse: %s must be True or False' % what)


def _type_expr(node):
    if isinstance(node, ast.Constant) and node.value is None:
        return ast.Name(id='str', ctx=ast.Load())
    if isinstance(node, ast.Name) and node.id in ('str', 'int', 'float', 'Path'):
        return node
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == 'pathlib' and node.attr == 'Path'):
        return node
    refuse(node, 'argparse: type= must be str, int, float or pathlib.Path')
    return None


def _choices(node):
    if not isinstance(node, (ast.Tuple, ast.List)):
        refuse(node, 'argparse: choices must be a tuple or list of literals')
    out = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and (item.value is None or isinstance(item.value, (str, int, float))):
            out.append(item.value)
        else:
            refuse(item, 'argparse: choices must be string, int or float literals')
    return out


def _parser_call(call, parser):
    if call.args:
        refuse(call, 'argparse: ArgumentParser(prog) as a positional argument is not built')
    for kw in call.keywords:
        if kw.arg is None:
            refuse(call, 'argparse: ArgumentParser(**kwargs) is not built')
        if kw.arg == 'add_help':
            parser.add_help = _const_bool(kw.value, 'add_help')
        elif kw.arg == 'description':
            if not (isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)):
                parser.description = None
        elif kw.arg == 'prefix_chars':
            if not (isinstance(kw.value, ast.Constant) and kw.value.value == '-'):
                refuse(kw, 'argparse: ArgumentParser(prefix_chars=...) is not built')
        elif kw.arg == 'argument_default':
            if not (isinstance(kw.value, ast.Constant) and kw.value.value is None):
                refuse(kw, 'argparse: ArgumentParser(argument_default=...) is not built')
        elif kw.arg in ('prog', 'usage', 'formatter_class', 'epilog'):
            pass
        else:
            refuse(kw, 'argparse: ArgumentParser(%s=...) is not built' % kw.arg)


def _add_argument(call, parser):
    if not call.args:
        refuse(call, 'argparse: add_argument() needs an argument name')
    names = [_const_str(node, 'an argument name') for node in call.args]
    positional = not names[0].startswith('-')
    if positional and len(names) > 1:
        refuse(call, 'argparse: a positional argument has one name')
    for name in names:
        if name in ('-', '--'):
            refuse(call, 'argparse: %r is not a usable argument name' % name)
        if not positional and not name.startswith('-'):
            refuse(call, 'argparse: an option name starts with -')
        if not positional and len(name) == 2 and (name[1].isdigit() or name[1] == '.'):
            refuse(call, 'argparse: an option name that looks like a negative number is not built')
    kwargs = {}
    for kw in call.keywords:
        if kw.arg is None:
            refuse(call, 'argparse: add_argument(**kwargs) is not built')
        kwargs[kw.arg] = kw.value
    allowed = {'type', 'default', 'required', 'choices', 'action', 'dest', 'help', 'metavar'}
    for key in kwargs:
        if key not in allowed:
            refuse(kwargs[key], 'argparse: add_argument(%s=...) is not built' % key)
    action = 'store'
    if 'action' in kwargs:
        action = _const_str(kwargs['action'], 'action')
        if action not in ('store', 'store_true', 'store_false'):
            refuse(kwargs['action'], 'argparse: action=%r is not built (store, store_true, store_false)' % action)
    if action != 'store' and 'type' in kwargs and not (
            isinstance(kwargs['type'], ast.Constant) and kwargs['type'].value is None):
        refuse(kwargs['type'], 'argparse: action=%s does not take type=' % action)
    if action != 'store' and 'choices' in kwargs:
        refuse(kwargs['choices'], 'argparse: action=%s does not take choices=' % action)
    if 'dest' in kwargs:
        dest = _const_str(kwargs['dest'], 'dest')
    elif positional:
        dest = names[0]
    else:
        long = [name for name in names if name.startswith('--')]
        dest = (long[0] if long else names[0]).lstrip('-').replace('-', '_')
    if not dest.isidentifier():
        refuse(call, 'argparse: destination %r is not a Python name' % dest)
    required = False
    if 'required' in kwargs:
        required = _const_bool(kwargs['required'], 'required')
        if positional:
            refuse(kwargs['required'], 'argparse: required= is not a positional argument option')
    if positional:
        required = True
        if 'default' in kwargs:
            refuse(kwargs['default'], 'argparse: a positional argument has no default here')
    typeexpr = _type_expr(kwargs['type']) if 'type' in kwargs else ast.Name(id='str', ctx=ast.Load())
    default = kwargs.get('default')
    if action == 'store_true' and default is None:
        default = ast.Constant(value=False)
    if action == 'store_false' and default is None:
        default = ast.Constant(value=True)
    if action == 'store' and isinstance(default, ast.Constant) and isinstance(default.value, str) \
            and ast.unparse(typeexpr) != 'str':
        text = ast.unparse(typeexpr)
        if text in ('int', 'float'):
            try:
                (int if text == 'int' else float)(default.value)
            except (ValueError, OverflowError):
                refuse(call, 'argparse: default=%r is not a valid %s' % (default.value, text))
        default = ast.Call(func=typeexpr, args=[default], keywords=[])
    if not positional and not required and default is None:
        refuse(call, 'argparse: an optional argument with neither default= nor required=True is not built')
    choices = _choices(kwargs['choices']) if 'choices' in kwargs else None
    arg = Arg(names, dest, positional, typeexpr, default, required, choices, action)
    parser.add(arg)
    return arg


def _dummy(typeexpr):
    text = ast.unparse(typeexpr)
    return {'str': '""', 'int': '0', 'float': '0.0'}.get(text, '%s("")' % text)


def _init_lines(parser, arg):
    hidden = parser.hidden(arg.dest)
    if arg.action == 'store_true' or arg.action == 'store_false':
        kind = 'bool'
    else:
        kind = ast.unparse(arg.typeexpr)
    default = ast.unparse(arg.default) if arg.default is not None else _dummy(arg.typeexpr)
    return ['%s: %s = %s' % (hidden, kind, default), '%s: int = 0' % parser.flag(arg.dest)]


def _convert_lines(parser, arg, expr):
    hidden = parser.hidden(arg.dest)
    text = ast.unparse(arg.typeexpr)
    lines = []
    if text == 'str':
        lines.append('%s = %s' % (hidden, expr))
    elif text in ('int', 'float'):
        lines += ['try:', '    %s = %s(%s)' % (hidden, text, expr), 'except ValueError:', '    sys.exit(2)']
    else:
        lines.append('%s = %s(%s)' % (hidden, text, expr))
    if arg.choices is not None:
        if not arg.choices:
            lines.append('sys.exit(2)')
        else:
            tests = ' or '.join('%s == %r' % (hidden, value) for value in arg.choices)
            lines += ['if not (%s):' % tests, '    sys.exit(2)']
    return lines


def _assign_lines(parser, arg, expr):
    if arg.action == 'store_true':
        return ['%s = True' % parser.hidden(arg.dest), '%s = 1' % parser.flag(arg.dest)]
    if arg.action == 'store_false':
        return ['%s = False' % parser.hidden(arg.dest), '%s = 1' % parser.flag(arg.dest)]
    return _convert_lines(parser, arg, expr) + ['%s = 1' % parser.flag(arg.dest)]


def _indent(lines, amount=1):
    pad = '    ' * amount
    return [pad + line if line else line for line in lines]


def _negative(expr):
    """An expression that is true when `expr` is CPython's negative-number token: -12 or -.5 / -5.5."""
    body = '%s[1:]' % expr
    return ('(%s.startswith("-") and (%s.isdigit() or (%s.count(".") == 1 and %s.replace(".", "", 1).isdigit() '
            'and %s[-1] != ".")))' % (expr, body, body, body, body))


def _short_options(parser):
    out = []
    seen = set()
    for arg in parser.args:
        if arg.positional:
            continue
        for name in arg.names:
            if len(name) == 2 and not name.startswith('--') and name[1] not in seen:
                out.append((name, arg))
                seen.add(name[1])
    return out


def _expand_lines(parser, base):
    """Split a short-option cluster (-vv, -qv, -c5, -c=5) into ordinary tokens before the parse loop."""
    shorts = _short_options(parser)
    if not shorts:
        return []
    pairs = [pair for pair, _ in shorts]
    full = [name for arg in parser.args if not arg.positional for name in arg.names
            if not name.startswith('--') and len(name) > 2]
    condition = ['not %s_dd' % base,
                 '%s_t.startswith("-") and not %s_t.startswith("--") and len(%s_t) > 2' % (base, base, base)]
    condition.append('(' + ' or '.join('%s_t[0:2] == %r' % (base, pair) for pair in pairs) + ')')
    if full:
        condition.append('not (' + ' or '.join('%s_t == %r' % (base, name) for name in full) + ')')
    lines = ['%s_argv0: list[str] = %s_argv' % (base, base),
             '%s_expanded: list[str] = []' % base,
             '%s_dd: int = 0' % base,
             '%s_j: int = 0' % base,
             'while %s_j < len(%s_argv0):' % (base, base),
             '    %s_t: str = %s_argv0[%s_j]' % (base, base, base),
             '    if %s_t == "--":' % base,
             '        %s_dd = 1' % base,
             '    if %s:' % ' and '.join(condition),
             '        %s_k: int = 1' % base,
             '        while %s_k < len(%s_t):' % (base, base),
             '            %s_c: str = %s_t[%s_k]' % (base, base, base)]
    body = []
    for index, (name, arg) in enumerate(shorts):
        char = name[1]
        word = 'if' if index == 0 else 'elif'
        if arg.action == 'store':
            body += ['%s %s_c == %r:' % (word, base, char),
                     '    %s_rest: str = %s_t[%s_k + 1:]' % (base, base, base),
                     '    %s_expanded.append(%r + %s_rest)' % (base, name, base),
                     '    %s_k = len(%s_t)' % (base, base)]
        else:
            body += ['%s %s_c == %r:' % (word, base, char),
                     '    %s_expanded.append(%r)' % (base, name),
                     '    %s_k = %s_k + 1' % (base, base)]
    body += ['else:',
             '    %s_expanded.append(%s_t)' % (base, base),
             '    %s_k = len(%s_t)' % (base, base)]
    lines += _indent(body, 3)
    lines += ['    else:',
              '        %s_expanded.append(%s_t)' % (base, base),
              '    %s_j = %s_j + 1' % (base, base),
              '%s_argv = %s_expanded' % (base, base)]
    return lines


def _positional_lines(parser, token, ind):
    positionals = [a for a in parser.args if a.positional]
    if not positionals:
        return ['sys.exit(2)']
    lines = []
    for index, arg in enumerate(positionals):
        word = 'if' if index == 0 else 'elif'
        lines.append('%s %s == %d:' % (word, ind['pos'], index))
        body = _assign_lines(parser, arg, token) + ['%s = %d' % (ind['pos'], index + 1)]
        lines += _indent(body)
    lines.append('else:')
    lines += _indent(['sys.exit(2)'])
    return lines


def _static_argv(argv):
    """The tokens of a literal list/tuple argv, or None when the argv is computed at runtime."""
    if not isinstance(argv, (ast.List, ast.Tuple)):
        return None
    tokens = []
    for item in argv.elts:
        if not (isinstance(item, ast.Constant) and isinstance(item.value, str)):
            return None
        tokens.append(item.value)
    return tokens


def _help_like(token):
    """True when CPython's parser could take this literal token as -h/--help (or an abbreviation)."""
    if token == '--':
        return False
    if token.startswith('--'):
        return len(token) >= 3 and '--help'.startswith(token)
    if token.startswith('-') and token != '-':
        return 'h' in token[1:]
    return False


def _parse_lines(parser, args_name, call):
    if len(call.args) > 1 or (call.args and call.keywords):
        refuse(call, 'argparse: parse_args() takes no argument or one list')
    if call.keywords:
        if len(call.keywords) != 1 or call.keywords[0].arg != 'args':
            refuse(call, 'argparse: parse_args(%s=...) is not built' % (call.keywords[0].arg or '**'))
        argv = call.keywords[0].value
    elif call.args:
        argv = call.args[0]
    else:
        argv = ast.parse('sys.argv[1:]', mode='eval').body
    if parser.add_help:
        tokens = _static_argv(argv)
        if tokens is None:
            refuse(argv, 'argparse: help output (-h/--help) is not built; add_help=True needs a '
                         'literal argv with no help token')
        after_dash = False
        for token in tokens:
            if token == '--':
                after_dash = True
                continue
            if not after_dash and _help_like(token):
                refuse(call, 'argparse: help output (-h/--help) is not built')
    base = '_ail_argparse_%s' % parser.name
    ind = {'pos': base + '_pos'}
    lines = ['%s_argv: list[str] = %s' % (base, ast.unparse(argv))]
    lines += _expand_lines(parser, base)
    lines += ['%s_i: int = 0' % base,
              '%s_pos: int = 0' % base,
              'while %s_i < len(%s_argv):' % (base, base)]
    inner = ['%s_tok: str = %s_argv[%s_i]' % (base, base, base)]
    positionals = [a for a in parser.args if a.positional]
    branches = []
    branches.append(('if', ['%s_tok == "--"' % base], None))
    long_names = [name for arg in parser.args if not arg.positional
                  for name in arg.names if name.startswith('--')]
    for arg in parser.args:
        if arg.positional:
            continue
        for name in arg.names:
            spellings = [name]
            if name.startswith('--'):
                for end in range(3, len(name)):
                    prefix = name[:end]
                    if sum(1 for other in long_names if other.startswith(prefix)) == 1:
                        spellings.append(prefix)
            for spelling in spellings:
                cond = ['%s_tok == %r' % (base, spelling)]
                if spelling.startswith('--') and arg.action == 'store':
                    cond[0] = '(%s or %s_tok.startswith(%r))' % (cond[0], base, spelling + '=')
                elif not spelling.startswith('--') and arg.action == 'store':
                    cond[0] = '(%s or (%s_tok.startswith(%r) and len(%s_tok) > %d))' % (
                        cond[0], base, spelling, base, len(spelling))
                elif not spelling.startswith('--') and len(spelling) == 2:
                    cond[0] = '(%s or (%s_tok.startswith(%r) and len(%s_tok) > 2 and %s_tok[1:] == %r * (len(%s_tok) - 1)))' % (
                        cond[0], base, spelling, base, base, spelling[1], base)
                branches.append(('elif' if branches else 'if', cond, (arg, spelling)))
    unknown = ['%s_tok.startswith("-") and %s_tok != "-"' % (base, base)]
    if positionals:
        unknown.append('not (%s_pos < %d and %s)' % (base, len(positionals), _negative(base + '_tok')))
    branches.append(('elif' if branches else 'if', unknown, 'unknown'))
    branches.append(('else', None, 'positional'))
    for word, cond, payload in branches:
        if word == 'else':
            inner.append('else:')
        else:
            inner.append('%s %s:' % (word, ' and '.join(cond)))
        if isinstance(payload, list):
            body = payload
        elif payload == 'unknown':
            body = ['sys.exit(2)']
        elif payload == 'positional':
            body = _positional_lines(parser, base + '_tok', ind)
        elif payload is None:
            body = ['%s_i = %s_i + 1' % (base, base),
                    'while %s_i < len(%s_argv):' % (base, base),
                    '    %s_tok = %s_argv[%s_i]' % (base, base, base)]
            body += _indent(_positional_lines(parser, base + '_tok', ind))
            body += ['    %s_i = %s_i + 1' % (base, base), 'break']
        elif isinstance(payload, tuple):
            arg, name = payload
            if arg.action != 'store':
                body = _assign_lines(parser, arg, base + '_tok')
            else:
                body = ['if %s_tok == %r:' % (base, name),
                        '    %s_i = %s_i + 1' % (base, base),
                        '    if %s_i >= len(%s_argv):' % (base, base),
                        '        sys.exit(2)',
                        '    if %s_argv[%s_i].startswith("-") and %s_argv[%s_i] != "-" and not %s:' % (
                            base, base, base, base, _negative('%s_argv[%s_i]' % (base, base))),
                        '        sys.exit(2)']
                body += _indent(_assign_lines(parser, arg, '%s_argv[%s_i]' % (base, base)))
                body += ['else:']
                if name.startswith('--'):
                    expr = '%s_tok[%d:]' % (base, len(name) + 1)
                else:
                    expr = '%s_tok[%d:] if %s_tok[%d] == "=" else %s_tok[%d:]' % (
                        base, len(name) + 1, base, len(name), base, len(name))
                body += _indent(_assign_lines(parser, arg, expr))
        else:
            raise AssertionError(payload)
        inner += _indent(body)
    inner.append('%s_i = %s_i + 1' % (base, base))
    lines += _indent(inner)
    for arg in parser.args:
        if arg.required:
            lines += ['if %s == 0:' % parser.flag(arg.dest), '    sys.exit(2)']
    return lines


def _ensure_sys(tree):
    for node in tree.body:
        if isinstance(node, ast.Import) and any(a.name == 'sys' for a in node.names):
            return
        if isinstance(node, ast.ImportFrom) and node.module == 'sys':
            return
    index = 0
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) \
            and isinstance(tree.body[0].value.value, str):
        index = 1
    while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) \
            and tree.body[index].module == '__future__':
        index += 1
    tree.body.insert(index, ast.parse('import sys').body[0])


class AttrReplace(ast.NodeTransformer):
    def __init__(self, argmaps):
        self.argmaps = argmaps

    def visit_FunctionDef(self, node):
        return node

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in self.argmaps:
            parser = self.argmaps[node.value.id]
            if not isinstance(node.ctx, ast.Load):
                refuse(node, 'argparse: assigning to args.%s is not built' % node.attr)
            if node.attr not in parser.by_dest:
                refuse(node, 'argparse: %s has no argument %r' % (node.value.id, node.attr))
            return ast.copy_location(ast.Name(id=parser.hidden(node.attr), ctx=ast.Load()), node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.argmaps:
            refuse(node, 'argparse: the namespace %r is used as a value; only args.<name> is built' % node.id)
        return node


class Nested(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.body = process_body(node.body)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.body = process_body(node.body)
        return node


def _parse_lines_ast(parser, args_name, call):
    source = '\n'.join(_parse_lines(parser, args_name, call))
    return ast.parse(source).body


def process_body(body):
    parsers = {}
    argmaps = {}
    parsed = set()
    out = []
    for stmt in body:
        handled = False
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            name = stmt.targets[0].id
            if _is_parser_call(stmt.value, _BINDER):
                parser = Parser(name)
                _parser_call(stmt.value, parser)
                parsers[name] = parser
                handled = True
            elif _is_parse_call(stmt.value, parsers):
                parser = parsers[stmt.value.func.value.id]
                if parser in parsed:
                    refuse(stmt, 'argparse: parse_args() is called twice on the parser %r; '
                                 'only one parse per parser is built' % parser.name)
                parsed.add(parser)
                argmaps[name] = parser
                out.extend(_parse_lines_ast(parser, name, stmt.value))
                handled = True
        if not handled and isinstance(stmt, ast.Expr) and _is_add_call(stmt.value, parsers):
            parser = parsers[stmt.value.func.value.id]
            arg = _add_argument(stmt.value, parser)
            out.extend(ast.parse('\n'.join(_init_lines(parser, arg))).body)
            handled = True
        if not handled:
            out.append(stmt)
    out = [Nested().visit(stmt) for stmt in out]
    out = [AttrReplace(argmaps).visit(stmt) for stmt in out]
    for stmt in out:
        for each in ast.walk(stmt):
            if not (isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load)):
                continue
            if each.id in parsers:
                refuse(each, 'argparse: the parser %r is used outside the forms that are built '
                             '(ArgumentParser(), add_argument() and parse_args())' % each.id)
            if each.id in argmaps:
                refuse(each, 'argparse: the namespace %r is used as a value; only args.<name> is built' % each.id)
    return out


_BINDER = None


def run(tree, text):
    global _BINDER
    binder = stdlib5.take_imports(tree, 'argparse', {'ArgumentParser'},
                                  unknown='ArgumentParser, add_argument and parse_args are the forms that are built')
    if not binder:
        return
    _BINDER = binder
    _ensure_sys(tree)
    tree.body = process_body(tree.body)
    stdlib5.leftover(tree, binder, 'ArgumentParser, add_argument and parse_args are the forms that are built')
