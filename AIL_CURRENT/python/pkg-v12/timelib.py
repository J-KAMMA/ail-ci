"""`time.sleep`, `time.localtime`, `time.gmtime`, `time.strftime`, `time.mktime` (stage G9, the wall clock).

Called from stdlib4.rewrite_text on the program text, before ail_syntax.py maps the rest of the `time` module
(`time.time()`, `time.time_ns()`, `perf_counter`, ... are single C primitives there). What is rewritten here is
lowered to the functions of dtrt.py (`# -- clock`), which dtlib.Dt.attach appends to the program together with
the datetime functions they share; a program that uses none of these names is not touched.

* `time.sleep(x)`                        -> sleep_for(x): CPython's checks, then the C sleep (which only advances the
                                            clock when AIL_CLOCK pins it)
* `time.localtime()` / `(t)`             -> tm_local_now() / tm_local(t): a `_AilTM` (time.struct_time, its fields
                                            tm_year ... tm_isdst, tm_zone, tm_gmtoff); the OS time zone, TZ respected
* `time.gmtime()` / `(t)`                -> tm_gm_now() / tm_gm(t)
* `time.strftime(fmt)` / `(fmt, t)`      -> tm_strftime(fmt, now) / tm_strftime(fmt, t): the datetime directives, plus
                                            %z and %Z from the struct
* `time.mktime(t)`                       -> tm_mktime(t); a 9-tuple of ints written out -> mktime_fields(...)
* `time.struct_time` as an annotation    -> the `_AilTM` class

Refused by name: struct_time(...) calls, strftime with a tuple (its zone is not defined), asctime, ctime, tzset,
altzone / daylight / timezone / tzname.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib4
from iterlower import _name, _call

BUILT = ('sleep', 'localtime', 'gmtime', 'strftime', 'mktime')
# time.time() and time.time_ns() are C primitives named by ail_syntax.py; here they are only respelled so that
# the datetime pass cannot take `time.time()` for a datetime's `.time()`
CLOCK = {'time': '_ail_time', 'time_ns': '_ail_time_ns'}
REFUSED = {
    'asctime': 'asctime is not built: use time.strftime("%a %b %e %H:%M:%S %Y", t)',
    'ctime': 'ctime is not built: use time.strftime("%a %b %e %H:%M:%S %Y", time.localtime(t))',
    'tzset': 'tzset is not built: the TZ variable is read when the program starts',
    'altzone': 'altzone is not built: read tm_gmtoff of time.localtime(t)',
    'daylight': 'daylight is not built: read tm_isdst of time.localtime(t)',
    'timezone': 'timezone is not built: read tm_gmtoff of time.localtime(t)',
    'tzname': 'tzname is not built: read tm_zone of time.localtime(t)',
    'struct_time': 'struct_time(...) is not built: time.localtime(t) and time.gmtime(t) make the values',
    'strptime': 'strptime is not built: use datetime.datetime.strptime',
    'process_time': 'process_time is not built: use time.perf_counter()',
    'thread_time': 'thread_time is not built: use time.perf_counter()',
}


def refuse(node, text):
    stdlib4.refuse(node, 'time.' + text)


def time_names(tree):
    """(module aliases, {local name: attribute}) of the top-level `import time` / `from time import ...`."""
    aliases, names = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'time':
                    aliases.add(alias.asname or 'time')
        elif isinstance(node, ast.ImportFrom) and node.module == 'time' and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = alias.name
    return aliases, names


def uses_any(tree, with_clock=False):
    """Whether the program uses a name this pass lowers. time.time() and time.time_ns() count only when the
    datetime pass runs too: there a call of `.time()` would be taken for the datetime method."""
    built = BUILT + ('struct_time',) + (tuple(CLOCK) if with_clock else ())
    aliases, names = time_names(tree)
    if not aliases and not names:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases \
                and node.attr in built:
            return True
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and names.get(node.id) in built:
            return True
    return False


class Lower(ast.NodeTransformer):
    def __init__(self, aliases, names, used, rt_name):
        self.aliases, self.names, self.used, self.rt_name = aliases, names, used, rt_name

    def call(self, name, *args):
        self.used.add(name)
        return _call(_name(self.rt_name(name)), *args)

    def which(self, func):
        """The `time` attribute a call's function names, or None."""
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in self.aliases:
            return func.attr
        if isinstance(func, ast.Name) and func.id in self.names:
            return self.names[func.id]
        return None

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id in self.aliases:
            if node.attr == 'struct_time':
                self.used.add('AilTM')
                return ast.copy_location(_name(self.rt_name('AilTM')), node)
            if node.attr in REFUSED:
                refuse(node, REFUSED[node.attr])
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.names:
            attr = self.names[node.id]
            if attr == 'struct_time':
                self.used.add('AilTM')
                return ast.copy_location(_name(self.rt_name('AilTM')), node)
            if attr in REFUSED:
                refuse(node, REFUSED[attr])
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        attr = self.which(node.func)
        if attr in CLOCK and not node.args and not node.keywords:
            return ast.copy_location(_call(_name(CLOCK[attr])), node)
        if attr not in BUILT:
            return node
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            refuse(node, '%s with * or ** arguments is not built' % attr)
        args = list(node.args)
        got = {}
        for keyword in node.keywords:
            got[keyword.arg] = keyword.value
        if attr == 'sleep':
            if got or len(args) != 1:
                refuse(node, 'sleep(seconds) takes the seconds as one positional argument')
            return ast.copy_location(self.call('sleep_for', args[0]), node)
        if attr in ('localtime', 'gmtime'):
            names = {'secs'}
            if set(got) - names or len(args) + len(got) > 1:
                refuse(node, '%s(secs) takes the seconds as one argument' % attr)
            value = args[0] if args else got.get('secs')
            prefix = 'tm_local' if attr == 'localtime' else 'tm_gm'
            if value is None or (isinstance(value, ast.Constant) and value.value is None):
                return ast.copy_location(self.call(prefix + '_now'), node)
            return ast.copy_location(self.call(prefix, value), node)
        if attr == 'mktime':
            if got or len(args) != 1:
                refuse(node, 'mktime(t) takes one positional argument')
            value = args[0]
            if isinstance(value, ast.Tuple):
                if len(value.elts) != 9 or any(isinstance(e, ast.Starred) for e in value.elts):
                    refuse(node, 'mktime(tuple) needs a tuple of 9 ints written out')
                e = value.elts
                return ast.copy_location(self.call('mktime_fields', e[0], e[1], e[2], e[3], e[4], e[5], e[8]), node)
            return ast.copy_location(self.call('tm_mktime', value), node)
        # strftime(format[, t])
        if set(got) - {'format', 't'} or not (1 <= len(args) + len(got) <= 2):
            refuse(node, 'strftime(format, t) takes the format and an optional struct_time')
        fmt = args[0] if args else got.get('format')
        t = args[1] if len(args) > 1 else got.get('t')
        if fmt is None:
            refuse(node, 'strftime needs a format')
        if t is None:
            t = self.call('tm_local_now')
        elif isinstance(t, ast.Tuple):
            refuse(node, 'strftime(format, tuple) is not built: its %Z / %z are undefined for a bare tuple; '
                   'pass time.localtime(t) or time.gmtime(t)')
        elif isinstance(t, ast.Constant) and t.value is None:
            t = self.call('tm_local_now')
        return ast.copy_location(self.call('tm_strftime', fmt, t), node)


def run(tree, used, rt_name):
    """Rewrite the calls in `tree`; the runtime names they need are added to `used`."""
    aliases, names = time_names(tree)
    Lower(aliases, names, used, rt_name).visit(tree)
    # drop what a `from time import ...` named and is now lowered away
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'time' and not node.level:
            keep = [a for a in node.names if a.name not in BUILT and a.name != 'struct_time']
            if len(keep) != len(node.names):
                if not keep:
                    continue
                node.names = keep
        body.append(node)
    tree.body = body
