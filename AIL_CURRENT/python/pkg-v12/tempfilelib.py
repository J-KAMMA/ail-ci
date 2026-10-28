"""`tempfile` on the Python surface (library batch 22 follow-up): gettempdir / gettempprefix / mkdtemp /
mktemp / TemporaryDirectory, lowered onto os primitives plus a small Python prelude.

The names are Python's own, and the calls are rewritten here before the file pass so that every
default (suffix "", prefix "tmp", dir gettempdir(), ignore_cleanup_errors False, delete True) is filled
in at compile time. `TemporaryDirectory` is a context manager whose `__enter__` value is the path text
(CPython's manager also implements `__fspath__`), and `.name`, `.cleanup()` and `cleanup()` are built.
`mkstemp`, `NamedTemporaryFile`, `TemporaryFile`, `SpooledTemporaryFile`, `tempfile.tempdir` and the
internal name sequences are refused by name.
"""
import ast
from pathlib import Path

import stdlib5
from stdlib4 import Refused, refuse

HERE = Path(__file__).parent
HANDLED = {'gettempdir', 'gettempprefix', 'gettempdirb', 'gettempprefixb', 'mkdtemp', 'mktemp',
           'TemporaryDirectory', 'TMP_MAX'}
BUILT = ('tempfile.gettempdir, tempfile.gettempprefix, tempfile.gettempdirb, tempfile.gettempprefixb, '
         'tempfile.mkdtemp, tempfile.mktemp, tempfile.TemporaryDirectory and tempfile.TMP_MAX are built')
PARAMS = {
    'mkdtemp': (['suffix', 'prefix', 'dir'], ['', 'tmp', None]),
    'mktemp': (['suffix', 'prefix', 'dir'], ['', 'tmp', None]),
    'TemporaryDirectory': (['suffix', 'prefix', 'dir', 'ignore_cleanup_errors'], ['', 'tmp', None, False]),
}
NONE_HELPER = """

def _ail_tf_mktemp_none(suffix: str, prefix: str, dir: str, which: str) -> str:
    if which == "prefix":
        raise TypeError("unsupported operand type(s) for +: 'NoneType' and 'str'")
    raise TypeError('can only concatenate str (not "NoneType") to str')
    return ""
"""


def prelude(name):
    lines = (HERE / ('prelude_%s.py' % name)).read_text(encoding='utf-8').splitlines()
    start = 0
    while start < len(lines) and (lines[start].startswith('#') or not lines[start].strip()):
        start += 1
    return '\n'.join(lines[start:]) + '\n'


def C(value):
    return ast.Constant(value=value)


def N(name):
    return ast.Name(id=name, ctx=ast.Load())


def call(name, args):
    return ast.Call(func=N(name), args=list(args), keywords=[])


def default(name):
    if name == 'dir':
        return call('_ail_tf_gettempdir', [])
    return C(name)


def bound(call_node, name, params, defaults, kwonly=(), none_defaults=()):
    if any(isinstance(a, ast.Starred) for a in call_node.args) or any(k.arg is None for k in call_node.keywords):
        refuse(call_node, 'tempfile.%s with * or ** arguments is not built; name each argument' % name)
    if len(call_node.args) > len(params):
        refuse(call_node, 'tempfile.%s takes at most %d positional arguments' % (name, len(params)))
    given = dict(zip(params, call_node.args))
    extra = {}
    for keyword in call_node.keywords:
        if keyword.arg in given:
            refuse(call_node, "tempfile.%s got multiple values for argument '%s'" % (name, keyword.arg))
        if keyword.arg in params:
            given[keyword.arg] = keyword.value
        elif keyword.arg in kwonly:
            extra[keyword.arg] = keyword.value
        else:
            refuse(call_node, "tempfile.%s got an unexpected keyword argument '%s'" % (name, keyword.arg))
    result = []
    for key, fallback in zip(params, defaults):
        if key in given:
            value = given[key]
            if key in none_defaults and isinstance(value, ast.Constant) and value.value is None:
                if key == 'dir':
                    value = call('_ail_tf_gettempdir', [])
                elif key == 'prefix':
                    value = C('tmp')
                else:
                    value = C('')
            result.append(value)
        else:
            result.append(default(key) if fallback is None else C(fallback))
    for key in kwonly:
        result.append(extra[key] if key in extra else C(True))
    return result


def rewrite_text(source, notes=None):
    if 'tempfile' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    try:
        binder = stdlib5.take_imports(tree, 'tempfile', HANDLED, unknown=BUILT)
        if not binder:
            return source
        needs_none_helper = [False]

        def fix(node):
            found = binder.attr(node)
            if found == 'TMP_MAX':
                return C(238328)
            if isinstance(node, ast.Call):
                found = binder.attr(node.func)
                if found in ('gettempdir', 'gettempprefix', 'gettempdirb', 'gettempprefixb'):
                    if node.args or node.keywords:
                        refuse(node, 'tempfile.%s() takes no arguments' % found)
                    return ast.copy_location(call('_ail_tf_' + found, []), node)
                if found in PARAMS:
                    params, defaults = PARAMS[found]
                    args = [stdlib5.Replace(fix).visit(argument) for argument in node.args]
                    keywords = [ast.keyword(arg=w.arg, value=stdlib5.Replace(fix).visit(w.value)) for w in node.keywords]
                    node = ast.copy_location(ast.Call(func=node.func, args=args, keywords=keywords), node)
                    if found == 'TemporaryDirectory':
                        values = bound(node, found, params, defaults, kwonly=('delete',), none_defaults=params)
                    elif found == 'mktemp':
                        values = bound(node, found, params, defaults, none_defaults=('dir',))
                        suffix_node, prefix_node = values[0], values[1]
                        which = None
                        if isinstance(prefix_node, ast.Constant) and prefix_node.value is None:
                            which, prefix_node = 'prefix', C('')
                        elif isinstance(suffix_node, ast.Constant) and suffix_node.value is None:
                            which, suffix_node = 'suffix', C('')
                        if which is not None:
                            if isinstance(suffix_node, ast.Constant) and suffix_node.value is None:
                                suffix_node = C('')
                            needs_none_helper[0] = True
                            return ast.copy_location(call('_ail_tf_mktemp_none',
                                                          [suffix_node, prefix_node, values[2], C(which)]), node)
                    else:
                        values = bound(node, found, params, defaults, none_defaults=params)
                    target = '_ail_tf_new' if found == 'TemporaryDirectory' else '_ail_tf_' + found
                    return ast.copy_location(call(target, values), node)
            return None

        before = ast.dump(tree)
        tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
        for each in ast.walk(tree):
            found = binder.attr(each)
            if found is not None:
                refuse(each, 'tempfile.%s used here is not built: %s' % (found, BUILT))
        if ast.dump(tree) == before:
            return source
        helper = NONE_HELPER if needs_none_helper[0] else ''
        stdlib5.insert_after_imports(tree, prelude('tempfile') + helper)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree).rstrip('\n') + '\n'
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line or 1, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the tempfile rewrite could not handle this program (%s: %s); simplify the use or report it'
                          % (type(exc).__name__, exc)))
        return source
