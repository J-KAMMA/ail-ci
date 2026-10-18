"""`datetime`: date, datetime, time and timedelta values, lowered onto one class and plain functions
(library batch 4).

Called from stdlib4.py on the program text before the tuple and collection passes. The four types are one
class `_AilDT` (see dtrt.py: `k` is the key every comparison and every difference works on, every field
exists), and what a program does with them becomes calls of module-level functions that are appended to the
program (only the ones used, dtrt.py is their source, run as plain Python by the test suite):

* constructors and class methods: date(y, m, d), datetime(...), time(...), timedelta(days=, ..., weeks=),
  date.fromisoformat, datetime.fromisoformat (CPython 3.12's accepted formats and error messages),
  datetime.strptime (the _strptime rules: the same alternatives in the same order, backtracking, `%z`
  matched and then refused because the result is aware), fromordinal, combine, min / max;
* methods by name, whatever the receiver: weekday, isoweekday, toordinal, isoformat, strftime (the C99
  directives, %f, %G %V %u, %e %k %l %P), replace(year=...), date(), time(), total_seconds;
* operators, where a static pass knows an operand is one of the four types (annotations, constructors,
  list / Optional annotations, loop and comprehension variables, function results, class fields): + - * /
  // % and unary -, comparisons (on the key), truth of a timedelta, str() / print / f-strings / `%s`;
  `x += td`; sorted / min / max / sort of a list of them (by key).
  An operator whose operand types the pass cannot tell is left as written (the compiler then refuses the
  class arithmetic by name); annotate the variable to build it.
* refused by name: now() / today() / utcnow() / fromtimestamp / timestamp() (the clock and the time zone
  are not reproducible), timezone / tzinfo / aware values, isocalendar(), a timedelta with float
  arguments, hashing values in sets / dicts.

Limits (documented, loud): a timedelta beyond about 53 million days is an OverflowError naming it; the
exceptions CPython raises that this language does not have (TypeError, AttributeError) are RuntimeError
with the same text; a UTC offset in an ISO string or `%z` gives a RuntimeError (the value would be aware);
total_seconds() and timedelta / timedelta are exact while the timedelta is under about 285 years.
"""
import ast
import copy
import re
import sys
from pathlib import Path

import stdlib4
from iterlower import _name, _mark, _call, _locate

CLASSES = ('date', 'datetime', 'timedelta', 'time')
KIND = {'date': 'date', 'datetime': 'datetime', 'timedelta': 'timedelta', 'time': 'time'}
CLASS_METHODS = {
    'date.fromisoformat': 'from_iso_date', 'datetime.fromisoformat': 'from_iso_datetime',
    'datetime.strptime': 'strptime', 'date.fromordinal': 'mk_ordinal', 'datetime.combine': 'combine',
    'date.fromisocalendar': 'from_isocalendar',
}
CLASS_CONSTANTS = {'date.min': 'date_min', 'date.max': 'date_max', 'datetime.min': 'datetime_min',
                   'datetime.max': 'datetime_max'}
CLOCK = ('date.today', 'datetime.now', 'datetime.today', 'datetime.utcnow', 'datetime.fromtimestamp',
         'datetime.utcfromtimestamp', 'date.fromtimestamp', 'time.fromisoformat', 'datetime.fromordinal')
# methods that are the same function whatever the receiver (only when the program defines none of that name)
METHODS = {'weekday': 'weekday', 'isoweekday': 'isoweekday', 'toordinal': 'toordinal', 'total_seconds': 'total_seconds',
           'strftime': 'fmt', 'date': 'date_of', 'time': 'time_of'}
UNBUILT_METHODS = {'timestamp': 'is the clock / time zone dependent (a naive value is read as local time)',
                   'isocalendar': 'returns a named tuple: use isoweekday() and strftime("%G %V")',
                   'astimezone': 'makes aware values', 'utcoffset': 'is for aware values', 'tzname': 'is for aware values',
                   'dst': 'is for aware values', 'timetuple': 'returns a struct_time', 'utctimetuple': 'is for aware values',
                   'ctime': 'is locale dependent: use strftime("%c")', 'fromutc': 'is for aware values'}
RUNTIME = None


def runtime():
    """(functions, constants, classes) of dtrt.py: name -> (node, names it uses)."""
    global RUNTIME
    if RUNTIME is None:
        text = (Path(__file__).parent / 'dtrt.py').read_text(encoding='utf-8')
        tree = ast.parse(text)
        top = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                top[node.name] = node
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                top[node.targets[0].id] = node
        uses = {}
        for name, node in top.items():
            uses[name] = {each.id for each in ast.walk(node) if isinstance(each, ast.Name) and each.id in top
                          and each.id != name}
            if isinstance(node, ast.FunctionDef):
                for each in ast.walk(node):
                    if isinstance(each, ast.Name) and each.id in top and each.id != name:
                        uses[name].add(each.id)
        RUNTIME = (top, uses)
    return RUNTIME


def rt_name(name):
    """The name a runtime function / constant / class has in the program."""
    top, _ = runtime()
    node = top[name]
    if isinstance(node, ast.ClassDef):
        return '_' + name
    if isinstance(node, ast.FunctionDef):
        return '_ail_dt_' + name
    return '_AIL_DT_' + name


def refuse(node, text):
    stdlib4.refuse(node, text)


def const_int(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and const_int(node.operand) is not None:
        return -const_int(node.operand)
    return None


class Type:
    """A static type: kind in date / datetime / timedelta / time; or a list / dict of those."""
    pass


def dt(kind, optional=False):
    return ('dt', kind, optional)


def lst(inner):
    return ('list', inner)


def dct(value):
    return ('dict', value)


def is_dt(t):
    return isinstance(t, tuple) and t[0] == 'dt'


def kind_of(t):
    return t[1] if is_dt(t) else None


def join(a, b):
    """The type of an expression that is `a` or `b`."""
    if a is None or b is None:
        return None
    if a == b:
        return a
    if is_dt(a) and is_dt(b):
        return dt(a[1] if a[1] == b[1] else 'any', a[2] or b[2])
    if a[0] == b[0] and a[0] in ('list', 'dict'):
        inner = join(a[1], b[1])
        return (a[0], inner) if inner is not None else None
    return None


class Scope:
    def __init__(self, parent=None, cls=None):
        self.parent = parent
        self.names = {}
        self.cls = cls

    def get(self, name):
        scope = self
        while scope is not None:
            if name in scope.names:
                return scope.names[name]
            scope = scope.parent
        return None


class Dt:
    def __init__(self, imports, tree, out):
        self.imports = imports
        self.tree = tree
        self.out = out
        self.used = set()            # runtime names used
        self.fields = {}             # class name -> {attr: type}
        self.field_by_name = {}      # attr -> type when every class that has it agrees
        self.returns = {}            # function name -> return type
        self.functions = {}
        self.defined = set()         # names the program defines itself (functions, methods, classes, fields)
        self.cls = None
        self.count = 0

    # -- names -------------------------------------------------------------------------------------------
    def path(self, node):
        """The datetime module path of a name / attribute (`date`, `datetime.strptime`, `date.min`), or None."""
        if isinstance(node, (ast.Name, ast.Attribute)):
            found = self.imports.resolve(node)
            if found is not None and found[0] == 'datetime':
                return found[1]
        return None

    def class_ref(self, node):
        path = self.path(node)
        return path if path in CLASSES else None

    def use(self, name):
        self.used.add(name)
        return _name(rt_name(name))

    def call(self, name, *args):
        return _call(self.use(name), *args)

    # -- annotations ---------------------------------------------------------------------------------------
    def ann_type(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                return self.ann_type(ast.parse(node.value, mode='eval').body)
            except SyntaxError:
                return None
        cls = self.class_ref(node)
        if cls is not None:
            return dt(cls)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = self.ann_type(node.left), self.ann_type(node.right)
            none_l = isinstance(node.left, ast.Constant) and node.left.value is None
            none_r = isinstance(node.right, ast.Constant) and node.right.value is None
            if none_r and is_dt(left):
                return dt(left[1], True)
            if none_l and is_dt(right):
                return dt(right[1], True)
            return None
        if isinstance(node, ast.Subscript):
            head = node.value
            name = head.id if isinstance(head, ast.Name) else (head.attr if isinstance(head, ast.Attribute) else None)
            inner = node.slice
            if name == 'Optional':
                t = self.ann_type(inner)
                return dt(t[1], True) if is_dt(t) else None
            if name in ('list', 'List', 'Sequence', 'Iterable'):
                t = self.ann_type(inner)
                return lst(t) if t is not None else None
            if name in ('dict', 'Dict') and isinstance(inner, ast.Tuple) and len(inner.elts) == 2:
                t = self.ann_type(inner.elts[1])
                return dct(t) if t is not None else None
        return None

    def rename_annotation(self, node):
        """The annotation with the module's classes replaced by the one class."""
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value, mode='eval').body
            except SyntaxError:
                return node
            if self.mentions(inner):
                return ast.copy_location(self.rename_annotation(inner), node)
            return node
        if self.class_ref(node) is not None:
            self.used.add('AilDT')
            return ast.copy_location(_name('_AilDT'), node)
        if isinstance(node, ast.Subscript):
            node.value = self.rename_annotation(node.value)
            if isinstance(node.slice, ast.Tuple):
                node.slice.elts = [self.rename_annotation(e) for e in node.slice.elts]
            else:
                node.slice = self.rename_annotation(node.slice)
            return node
        if isinstance(node, ast.BinOp):
            node.left = self.rename_annotation(node.left)
            node.right = self.rename_annotation(node.right)
            return node
        if isinstance(node, ast.Tuple):
            node.elts = [self.rename_annotation(e) for e in node.elts]
        return node

    def mentions(self, node):
        return any(self.class_ref(each) is not None for each in ast.walk(node)
                   if isinstance(each, (ast.Name, ast.Attribute)))

    # -- the program's own definitions -------------------------------------------------------------------------
    def collect(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defined.add(node.name)
            elif isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load):
                self.defined.add(node.attr)
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node
                self.returns[node.name] = self.ann_type(node.returns)
            elif isinstance(node, ast.ClassDef):
                self.fields[node.name] = fields = {}
                for each in node.body:
                    if isinstance(each, ast.AnnAssign) and isinstance(each.target, ast.Name):
                        t = self.ann_type(each.annotation)
                        if t is not None:
                            fields[each.target.id] = t
                    elif isinstance(each, ast.FunctionDef):
                        if each.name == '__init__':
                            params = {a.arg: self.ann_type(a.annotation) for a in each.args.args}
                            for sub in ast.walk(each):
                                if isinstance(sub, ast.Assign) and isinstance(sub.targets[0], ast.Attribute) \
                                        and isinstance(sub.targets[0].value, ast.Name) and sub.targets[0].value.id == 'self':
                                    if isinstance(sub.value, ast.Name) and params.get(sub.value.id) is not None:
                                        fields[sub.targets[0].attr] = params[sub.value.id]
                                elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute) \
                                        and isinstance(sub.target.value, ast.Name) and sub.target.value.id == 'self':
                                    t = self.ann_type(sub.annotation)
                                    if t is not None:
                                        fields[sub.target.attr] = t
                        self.returns[node.name + '.' + each.name] = self.ann_type(each.returns)
        seen = {}
        for fields in self.fields.values():
            for attr, t in fields.items():
                seen.setdefault(attr, set()).add(t)
        self.field_by_name = {attr: next(iter(types)) for attr, types in seen.items() if len(types) == 1}

    # -- expression types ----------------------------------------------------------------------------------------
    def expr_type(self, node, scope):
        if isinstance(node, ast.Name):
            return scope.get(node.id)
        if isinstance(node, ast.Constant):
            return None
        if isinstance(node, ast.Call):
            return self.call_type(node, scope)
        if isinstance(node, ast.Attribute):
            path = self.path(node)
            if path in CLASS_CONSTANTS:
                return dt(path.split('.')[0])
            if path in ('MINYEAR', 'MAXYEAR'):
                return None
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and scope.cls is not None:
                t = self.fields.get(scope.cls, {}).get(node.attr)
                if t is not None:
                    return t
            inner = self.expr_type(node.value, scope)
            if isinstance(node.value, ast.Name) and node.value.id in self.fields:
                return self.fields[node.value.id].get(node.attr)
            if is_dt(inner):
                return None            # year, days, ...: ints
            return self.field_by_name.get(node.attr)
        if isinstance(node, ast.Subscript):
            inner = self.expr_type(node.value, scope)
            if inner is not None and inner[0] == 'list':
                return inner if isinstance(node.slice, ast.Slice) else inner[1]
            if inner is not None and inner[0] == 'dict' and not isinstance(node.slice, ast.Slice):
                return inner[1]
            return None
        if isinstance(node, ast.IfExp):
            return join(self.expr_type(node.body, scope), self.expr_type(node.orelse, scope))
        if isinstance(node, ast.BoolOp):
            result = self.expr_type(node.values[0], scope)
            for each in node.values[1:]:
                result = join(result, self.expr_type(each, scope))
            return result
        if isinstance(node, ast.BinOp):
            return self.binop_type(node, scope)
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, (ast.USub, ast.UAdd)) and is_dt(self.expr_type(node.operand, scope)):
                return dt('timedelta')
            return None
        if isinstance(node, ast.ListComp):
            inner = Scope(scope, scope.cls)
            self.bind_generators(node.generators, inner)
            t = self.expr_type(node.elt, inner)
            return lst(t) if t is not None else None
        if isinstance(node, ast.List) and node.elts:
            t = self.expr_type(node.elts[0], scope)
            for each in node.elts[1:]:
                t = join(t, self.expr_type(each, scope))
            return lst(t) if t is not None else None
        if isinstance(node, ast.NamedExpr):
            return self.expr_type(node.value, scope)
        return None

    def binop_type(self, node, scope):
        left, right = self.expr_type(node.left, scope), self.expr_type(node.right, scope)
        lk, rk = kind_of(left), kind_of(right)
        op = node.op
        if lk is None and rk is None:
            return None
        if isinstance(op, ast.Add):
            if lk == 'timedelta' and rk is not None and rk != 'timedelta':
                return dt(rk)
            if lk == 'timedelta' and rk == 'timedelta':
                return dt('timedelta')
            return dt(lk) if lk is not None else (dt(rk) if rk is not None else None)
        if isinstance(op, ast.Sub):
            if lk in ('date', 'datetime', 'time', 'any') and rk == lk:
                return dt('timedelta')
            if lk in ('date', 'datetime') and rk == 'timedelta':
                return dt(lk)
            if lk == 'timedelta':
                return dt('timedelta')
            if lk in ('date', 'datetime') and rk == 'any':
                return dt('any')
            return dt('any') if (lk is not None or rk is not None) else None
        if isinstance(op, ast.Mult):
            return dt('timedelta')
        if isinstance(op, ast.Div):
            return None if rk == 'timedelta' else dt('timedelta')
        if isinstance(op, ast.FloorDiv):
            return None if rk == 'timedelta' else dt('timedelta')
        if isinstance(op, ast.Mod):
            return dt('timedelta')
        return None

    def call_type(self, node, scope):
        path = self.path(node.func)
        if path in CLASSES:
            return dt(path)
        if path in CLASS_METHODS:
            return dt('date' if path in ('date.fromisoformat', 'date.fromordinal', 'date.fromisocalendar') else 'datetime')
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in self.returns and func.id in self.functions:
                return self.returns[func.id]
            if func.id in ('max', 'min', 'abs') and node.args:
                if func.id == 'abs':
                    return self.expr_type(node.args[0], scope)
                first = self.expr_type(node.args[0], scope)
                if len(node.args) == 1 and first is not None and first[0] == 'list':
                    return first[1]
                if len(node.args) > 1:
                    t = first
                    for each in node.args[1:]:
                        t = join(t, self.expr_type(each, scope))
                    return t
                return None
            if func.id in ('sorted', 'reversed', 'list') and node.args:
                t = self.expr_type(node.args[0], scope)
                return t if t is not None and t[0] == 'list' else None
        if isinstance(func, ast.Attribute):
            recv = self.expr_type(func.value, scope)
            if func.attr == 'date' and not node.args and func.attr not in self.defined:
                return dt('date')
            if func.attr == 'time' and not node.args and func.attr not in self.defined:
                return dt('time')
            if func.attr == 'replace' and (node.keywords and not node.args or is_dt(recv)):
                return dt(kind_of(recv) or 'any')
            if isinstance(func.value, ast.Name) and func.value.id == 'self' and scope.cls is not None:
                return self.returns.get(scope.cls + '.' + func.attr)
            if func.attr in ('get', 'pop') and recv is not None and recv[0] == 'dict' and len(node.args) == 2:
                return recv[1]
            if isinstance(func.value, ast.Name) and func.value.id in self.functions:
                return None
        return None

    def bind_generators(self, generators, scope):
        for gen in generators:
            it = self.expr_type(gen.iter, scope)
            elem = None
            if it is not None and it[0] == 'list':
                elem = it[1]
            elif it is not None and it[0] == 'dict':
                elem = None
            self.bind_target(gen.target, elem, scope)

    def bind_target(self, target, t, scope):
        if isinstance(target, ast.Name):
            scope.names[target.id] = t
        elif isinstance(target, (ast.Tuple, ast.List)):
            for each in target.elts:
                self.bind_target(each, None, scope)

    # -- scopes: the types of a function's names --------------------------------------------------------------------
    def function_scope(self, fn, parent, cls):
        scope = Scope(parent, cls)
        for arg in (*fn.args.args, *fn.args.kwonlyargs, *fn.args.posonlyargs):
            scope.names[arg.arg] = getattr(arg, '_dt_ann', None) or self.ann_type(arg.annotation)
        if fn.args.vararg:
            scope.names[fn.args.vararg.arg] = None
        if fn.args.kwarg:
            scope.names[fn.args.kwarg.arg] = None
        self.infer_body(fn.body, scope, 3)
        return scope

    def infer_body(self, body, scope, rounds):
        for _ in range(rounds):
            changed = False
            for node in self.walk_statements(body):
                if isinstance(node, ast.Assign):
                    t = self.expr_type(node.value, scope)
                    for target in node.targets:
                        changed |= self.assign_name(target, t, scope)
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    t = getattr(node, '_dt_ann', None) or self.ann_type(node.annotation)
                    if t is None and node.value is not None:
                        t = self.expr_type(node.value, scope)
                    changed |= self.assign_name(node.target, t, scope, True)
                elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    t = self.expr_type(ast.BinOp(left=node.target, op=node.op, right=node.value), scope)
                    changed |= self.assign_name(node.target, t, scope)
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    it = self.expr_type(node.iter, scope)
                    elem = it[1] if it is not None and it[0] == 'list' else None
                    if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                            and node.iter.func.id == 'enumerate' and node.iter.args:
                        base = self.expr_type(node.iter.args[0], scope)
                        if isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2:
                            self.bind_target(node.target.elts[0], None, scope)
                            changed |= self.assign_name(node.target.elts[1], base[1] if base is not None and base[0] == 'list' else None, scope)
                            continue
                    changed |= self.assign_name(node.target, elem, scope)
                elif isinstance(node, ast.NamedExpr):
                    changed |= self.assign_name(node.target, self.expr_type(node.value, scope), scope)
            if not changed:
                break

    def assign_name(self, target, t, scope, forced=False):
        if not isinstance(target, ast.Name):
            return False
        old = scope.names.get(target.id, 'unset')
        if old == 'unset':
            scope.names[target.id] = t
            return True
        if forced:
            new = t
        else:
            new = join(old, t) if old is not None and t is not None else (old if t is None and old is not None else t)
            if old is not None and t is not None:
                new = join(old, t)
            elif old is None:
                new = None
        if new != old:
            scope.names[target.id] = new
            return True
        return False

    def walk_statements(self, body):
        """Every node of a function body that binds a name, not entering nested functions or classes."""
        stack = list(body)
        while stack:
            node = stack.pop(0)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            yield node
            stack = list(ast.iter_child_nodes(node)) + stack

    # -- the walk --------------------------------------------------------------------------------------------------------
    def run(self):
        self.reject()
        self.collect()
        # the types the annotations say, before their names are replaced
        for node in ast.walk(self.tree):
            if isinstance(node, ast.arg):
                node._dt_ann = self.ann_type(node.annotation)
            elif isinstance(node, ast.AnnAssign):
                node._dt_ann = self.ann_type(node.annotation)
        # annotations everywhere
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                    if arg.annotation is not None:
                        arg.annotation = self.rename_annotation(arg.annotation)
                for arg in (node.args.vararg, node.args.kwarg):
                    if arg is not None and arg.annotation is not None:
                        arg.annotation = self.rename_annotation(arg.annotation)
                if node.returns is not None:
                    node.returns = self.rename_annotation(node.returns)
            elif isinstance(node, ast.AnnAssign):
                node.annotation = self.rename_annotation(node.annotation)
        module_scope = Scope()
        self.infer_body(self.tree.body, module_scope, 3)
        self.scope_stack = [module_scope]
        self.tree.body = [self.stmt(node, module_scope) for node in self.tree.body]
        self.attach()

    def reject(self):
        for node in ast.walk(self.tree):
            path = self.path(node) if isinstance(node, (ast.Name, ast.Attribute)) else None
            if path is None:
                continue
            if path in CLOCK:
                refuse(node, 'datetime.%s reads the clock or the time zone, which a deterministic program cannot '
                       'repeat; read the date from the input (date.fromisoformat(line))' % path)
            if path in ('timezone', 'tzinfo', 'UTC', 'timezone.utc', 'timezone.min', 'timezone.max') \
                    or path.startswith('timezone.'):
                refuse(node, 'datetime.%s: timezone-aware values are not built (naive date / datetime / '
                       'time / timedelta are)' % path)

    # -- statements ------------------------------------------------------------------------------------------------------
    def stmt(self, node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = self.function_scope(node, scope, scope.cls)
            node.decorator_list = [self.expr(d, scope) for d in node.decorator_list]
            for arg, default in zip(reversed(node.args.args), reversed(node.args.defaults)):
                pass
            node.args.defaults = [self.expr(d, scope) for d in node.args.defaults]
            node.args.kw_defaults = [self.expr(d, scope) if d is not None else None for d in node.args.kw_defaults]
            node.body = [self.stmt(each, inner) for each in node.body]
            return node
        if isinstance(node, ast.ClassDef):
            cls_scope = Scope(scope, node.name)
            node.body = [self.stmt(each, cls_scope) for each in node.body]
            return node
        if isinstance(node, ast.AugAssign):
            t = self.expr_type(node.target, scope)
            v = self.expr_type(node.value, scope)
            if is_dt(t) or is_dt(v):
                load = copy.deepcopy(node.target)
                for each in ast.walk(load):
                    if hasattr(each, 'ctx'):
                        each.ctx = ast.Load()
                value = self.expr(ast.BinOp(left=load, op=node.op, right=node.value), scope)
                return ast.copy_location(ast.Assign(targets=[node.target], value=value), node)
        if isinstance(node, (ast.If, ast.While)):
            node.test = self.test(node.test, scope)
        if isinstance(node, ast.Assert):
            node.test = self.test(node.test, scope)
        for field, value in ast.iter_fields(node):
            if field == 'test' and isinstance(node, (ast.If, ast.While, ast.Assert)):
                continue
            if isinstance(value, ast.expr):
                setattr(node, field, self.expr(value, scope, store=field in ('target', 'targets')))
            elif isinstance(value, list):
                new = []
                for each in value:
                    if isinstance(each, ast.stmt):
                        new.append(self.stmt(each, scope))
                    elif isinstance(each, ast.expr):
                        new.append(self.expr(each, scope, store=field in ('targets',)))
                    elif isinstance(each, (ast.ExceptHandler, ast.withitem, ast.match_case, ast.keyword)):
                        new.append(self.generic(each, scope))
                    else:
                        new.append(each)
                setattr(node, field, new)
        return node

    def generic(self, node, scope):
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.expr(value, scope))
            elif isinstance(value, list):
                setattr(node, field, [self.stmt(e, scope) if isinstance(e, ast.stmt) else
                                      self.expr(e, scope) if isinstance(e, ast.expr) else e for e in value])
        return node

    def test(self, node, scope):
        """A condition: a timedelta is false when it is zero."""
        t = self.expr_type(node, scope)
        value = self.expr(node, scope)
        if is_dt(t) and t[1] in ('timedelta', 'any') and not t[2]:
            return ast.copy_location(self.call('nonzero', value), node)
        return value

    # -- expressions -----------------------------------------------------------------------------------------------------
    def expr(self, node, scope, store=False):
        if store or node is None:
            return node
        method = getattr(self, 'x_' + type(node).__name__, None)
        if method is not None:
            return method(node, scope)
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.expr(value, scope))
            elif isinstance(value, list):
                setattr(node, field, [self.expr(e, scope) if isinstance(e, ast.expr) else e for e in value])
        return node

    def x_Lambda(self, node, scope):
        inner = Scope(scope, scope.cls)
        for arg in node.args.args:
            inner.names.setdefault(arg.arg, getattr(arg, '_dt_type', None))
        node.body = self.expr(node.body, inner)
        return node

    def x_ListComp(self, node, scope):
        return self.comprehension(node, scope, ('elt',))

    x_SetComp = x_GeneratorExp = x_ListComp

    def x_DictComp(self, node, scope):
        return self.comprehension(node, scope, ('key', 'value'))

    def comprehension(self, node, scope, fields):
        inner = Scope(scope, scope.cls)
        for gen in node.generators:
            gen.iter = self.expr(gen.iter, inner)
            it = self.expr_type(gen.iter, inner)
            elem = it[1] if it is not None and it[0] == 'list' else None
            self.bind_target(gen.target, elem, inner)
            gen.ifs = [self.test(c, inner) for c in gen.ifs]
        for field in fields:
            setattr(node, field, self.expr(getattr(node, field), inner))
        return node

    def x_IfExp(self, node, scope):
        node.test = self.test(node.test, scope)
        node.body = self.expr(node.body, scope)
        node.orelse = self.expr(node.orelse, scope)
        return node

    def x_BoolOp(self, node, scope):
        node.values = [self.test(v, scope) if isinstance(v, (ast.Name, ast.Attribute, ast.Call, ast.Subscript)) and
                       kind_of(self.expr_type(v, scope)) in ('timedelta', 'any') else self.expr(v, scope) for v in node.values]
        return node

    def x_UnaryOp(self, node, scope):
        t = self.expr_type(node.operand, scope)
        operand = self.expr(node.operand, scope)
        if isinstance(node.op, ast.Not):
            if is_dt(t) and t[1] in ('timedelta', 'any') and not t[2]:
                node.operand = self.call('nonzero', operand)
                return node
            node.operand = operand
            return node
        if is_dt(t):
            if isinstance(node.op, ast.USub):
                return ast.copy_location(self.call('neg', operand), node)
            if isinstance(node.op, ast.UAdd):
                return operand
        node.operand = operand
        return node

    def x_BinOp(self, node, scope):
        left_t, right_t = self.expr_type(node.left, scope), self.expr_type(node.right, scope)
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            node.right = self.str_operands(node.right, scope)
            node.left = self.expr(node.left, scope)
            return node
        left, right = self.expr(node.left, scope), self.expr(node.right, scope)
        lk, rk = kind_of(left_t), kind_of(right_t)
        if lk is None and rk is None:
            node.left, node.right = left, right
            return node
        op = node.op
        if isinstance(op, ast.Add):
            return ast.copy_location(self.call('add', left, right), node)
        if isinstance(op, ast.Sub):
            return ast.copy_location(self.call('sub', left, right), node)
        if isinstance(op, ast.Mult):
            if lk is not None and rk is not None:
                refuse(node, 'timedelta * timedelta is not defined')
            if lk is not None:
                return ast.copy_location(self.call('mul', left, right), node)
            return ast.copy_location(self.call('mul', right, left), node)
        if isinstance(op, (ast.Div, ast.FloorDiv)):
            if lk is None:
                refuse(node, 'a number divided by a timedelta is not defined')
            if rk is not None:
                return ast.copy_location(self.call('truediv_td' if isinstance(op, ast.Div) else 'floordiv_td', left, right), node)
            return ast.copy_location(self.call('truediv_int' if isinstance(op, ast.Div) else 'floordiv_int', left, right), node)
        if isinstance(op, ast.Mod):
            return ast.copy_location(self.call('mod', left, right), node)
        node.left, node.right = left, right
        return node

    def x_Compare(self, node, scope):
        operands = [node.left, *node.comparators]
        types = [self.expr_type(o, scope) for o in operands]
        new = [self.expr(o, scope) for o in operands]
        order = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
        if any(is_dt(t) for t in types) and all(isinstance(op, order) for op in node.ops) \
                and not any(isinstance(o, ast.Constant) and o.value is None for o in operands):
            new = [ast.Attribute(value=o, attr='k', ctx=ast.Load()) for o in new]
        node.left, node.comparators = new[0], new[1:]
        return node

    def x_JoinedStr(self, node, scope):
        values = []
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                t = self.expr_type(part.value, scope)
                inner = self.expr(part.value, scope)
                spec = part.format_spec
                if is_dt(t):
                    conv = part.conversion
                    if spec is not None:
                        if not (isinstance(spec, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in spec.values)):
                            refuse(part, 'a datetime format spec has to be a literal like {d:%Y-%m-%d}')
                        text = ''.join(v.value for v in spec.values)
                        if t[1] == 'timedelta':
                            refuse(part, 'a timedelta takes no format spec in CPython (TypeError)')
                        inner = self.call('fmt', inner, ast.Constant(value=text))
                        part = ast.FormattedValue(value=inner, conversion=-1, format_spec=None)
                    elif conv == 114:
                        part = ast.FormattedValue(value=self.call('rep', inner), conversion=-1, format_spec=None)
                    else:
                        part = ast.FormattedValue(value=self.call('text', inner), conversion=-1, format_spec=None)
                    values.append(part)
                    continue
                part.value = inner
                if part.format_spec is not None:
                    part.format_spec = self.expr(part.format_spec, scope)
            values.append(part)
        node.values = values
        return node

    def str_operands(self, node, scope):
        """The right operand of `"%s" % x`: dt values become their text."""
        items = node.elts if isinstance(node, ast.Tuple) else [node]
        out = []
        for each in items:
            if is_dt(self.expr_type(each, scope)):
                out.append(self.call('text', self.expr(each, scope)))
            else:
                out.append(self.expr(each, scope))
        if isinstance(node, ast.Tuple):
            node.elts = out
            return node
        return out[0]

    def x_Attribute(self, node, scope):
        path = self.path(node)
        if path in CLASS_CONSTANTS:
            return ast.copy_location(self.call(CLASS_CONSTANTS[path]), node)
        if path in CLASSES:
            refuse(node, 'datetime.%s used as a value is not built (call it: %s(...), or annotate with it)'
                   % (path, path))
        node.value = self.expr(node.value, scope)
        return node

    def x_Name(self, node, scope):
        path = self.path(node)
        if path in CLASSES:
            refuse(node, 'datetime.%s used as a value is not built (call it: %s(...), or annotate with it)'
                   % (path, path))
        return node

    def value_arguments(self, node, names, what):
        """The arguments of `node` by parameter name (positional then keyword)."""
        got = {}
        if len(node.args) > len(names):
            refuse(node, '%s: too many arguments' % what)
        for name, value in zip(names, node.args):
            got[name] = value
        for keyword in node.keywords:
            if keyword.arg not in names:
                refuse(node, '%s: the argument %s is not built' % (what, keyword.arg))
            if keyword.arg in got:
                refuse(node, '%s: %s given twice' % (what, keyword.arg))
            got[keyword.arg] = keyword.value
        return got

    def int_args(self, got, order, defaults, what, node):
        out = []
        for name in order:
            value = got.get(name)
            if value is None:
                out.append(ast.Constant(value=defaults[name]))
            else:
                if isinstance(value, ast.Constant) and isinstance(value.value, float):
                    refuse(node, '%s: %s is a float; a timedelta with float arguments is not built, use '
                           'integers (e.g. seconds=90 or microseconds=1500000)' % (what, name))
                if isinstance(value, ast.Constant) and (isinstance(value.value, (str, bytes)) or value.value is None):
                    refuse(node, '%s: %s has to be an int' % (what, name))
                out.append(value)
        return out

    def constructor(self, node, cls, scope):
        got = self.value_arguments(node, {
            'date': ['year', 'month', 'day'],
            'datetime': ['year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond', 'tzinfo'],
            'time': ['hour', 'minute', 'second', 'microsecond', 'tzinfo'],
            'timedelta': ['days', 'seconds', 'microseconds', 'milliseconds', 'minutes', 'hours', 'weeks'],
        }[cls], cls)
        if 'tzinfo' in got and not (isinstance(got['tzinfo'], ast.Constant) and got['tzinfo'].value is None):
            refuse(node, '%s(..., tzinfo=...): timezone-aware values are not built' % cls)
        got.pop('tzinfo', None)
        for key in list(got):
            got[key] = self.expr(got[key], scope)
        if cls == 'date':
            for name in ('year', 'month', 'day'):
                if name not in got:
                    refuse(node, 'date() needs year, month and day')
            return self.call('mk_date', *self.int_args(got, ['year', 'month', 'day'], {}, cls, node))
        if cls == 'datetime':
            for name in ('year', 'month', 'day'):
                if name not in got:
                    refuse(node, 'datetime() needs year, month and day')
            return self.call('mk_datetime', *self.int_args(
                got, ['year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond'],
                {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}, cls, node))
        if cls == 'time':
            return self.call('mk_time', *self.int_args(
                got, ['hour', 'minute', 'second', 'microsecond'],
                {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}, cls, node))
        return self.call('mk_timedelta', *self.int_args(
            got, ['days', 'seconds', 'microseconds', 'milliseconds', 'minutes', 'hours', 'weeks'],
            {'days': 0, 'seconds': 0, 'microseconds': 0, 'milliseconds': 0, 'minutes': 0, 'hours': 0, 'weeks': 0},
            cls, node))

    def class_method(self, node, path, scope):
        name = CLASS_METHODS[path]
        if path == 'datetime.combine':
            got = self.value_arguments(node, ['date', 'time', 'tzinfo'], path)
            if 'tzinfo' in got:
                refuse(node, 'datetime.combine(..., tzinfo): timezone-aware values are not built')
            return self.call(name, self.expr(got['date'], scope), self.expr(got['time'], scope))
        if path == 'datetime.strptime':
            got = self.value_arguments(node, ['date_string', 'format'], path)
            return self.call(name, self.expr(got['date_string'], scope), self.expr(got['format'], scope))
        if path == 'date.fromisocalendar':
            got = self.value_arguments(node, ['year', 'week', 'day'], path)
            return self.call(name, *[self.expr(got[k], scope) for k in ('year', 'week', 'day')])
        got = self.value_arguments(node, ['date_string'] if 'iso' in path else ['ordinal'], path)
        return self.call(name, self.expr(next(iter(got.values())), scope))

    def x_Call(self, node, scope):
        func = node.func
        path = self.path(func)
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            if path is not None or isinstance(func, ast.Attribute) and (func.attr in METHODS or func.attr in
                                                                         ('isoformat', 'replace', 'strftime')):
                refuse(node, 'datetime calls with * or ** arguments are not built')
        if path in CLASSES:
            return ast.copy_location(self.constructor(node, path, scope), node)
        if path in CLASS_METHODS:
            return ast.copy_location(self.class_method(node, path, scope), node)
        if path is not None and path not in CLASS_CONSTANTS:
            refuse(node, 'datetime.%s is not built' % path)
        # types are read from the call as written, then the arguments are rewritten
        types = [self.expr_type(a, scope) for a in node.args]
        kw_types = {k.arg: self.expr_type(k.value, scope) for k in node.keywords}
        if isinstance(func, ast.Name) and func.id not in self.defined:
            return self.builtin_call(node, scope, types, kw_types)
        if isinstance(func, ast.Attribute):
            return self.method_call(node, scope, types, kw_types)
        node.func = self.expr(func, scope)
        node.args = [self.expr(a, scope) for a in node.args]
        node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in node.keywords]
        return node

    def key_lambda(self):
        """lambda _x: _x.k"""
        return ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='_dt_x')], kwonlyargs=[],
                                             kw_defaults=[], defaults=[]),
                          body=ast.Attribute(value=_name('_dt_x'), attr='k', ctx=ast.Load()))

    def typed_key(self, keyword, element):
        """The key= keyword with its lambda's parameter known to be `element`."""
        value = keyword.value
        if isinstance(value, ast.Lambda) and value.args.args and element is not None:
            value.args.args[0]._dt_type = element
        return ast.keyword(arg='key', value=self.expr(value, Scope(None)) if False else value)

    def text_of(self, value, t):
        """str(value) of a datetime-family value (None for an Optional)."""
        call = self.call('text', copy.deepcopy(value))
        if t[2]:
            return ast.IfExp(test=ast.Compare(left=copy.deepcopy(value), ops=[ast.IsNot()],
                                              comparators=[ast.Constant(value=None)]),
                             body=call, orelse=ast.Constant(value='None'))
        return call

    def builtin_call(self, node, scope, types, kw_types):
        name = node.func.id
        args = node.args
        if name == 'print':
            new = []
            for a, t in zip(args, types):
                value = self.expr(a, scope)
                new.append(self.text_of(value, t) if is_dt(t) else value)
            node.args = new
            node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in node.keywords]
            return node
        if name in ('str', 'repr') and len(args) == 1 and is_dt(types[0]) and not node.keywords:
            value = self.expr(args[0], scope)
            if name == 'str':
                return ast.copy_location(self.text_of(value, types[0]), node)
            return ast.copy_location(self.call('rep', value), node)
        if name == 'format' and len(args) >= 1 and is_dt(types[0]) and len(args) <= 2 and not node.keywords:
            value = self.expr(args[0], scope)
            if len(args) == 1:
                return ast.copy_location(self.call('text', value), node)
            if types[0][1] == 'timedelta':
                refuse(node, 'a timedelta takes no format spec in CPython (TypeError)')
            return ast.copy_location(self.call('fmt', value, self.expr(args[1], scope)), node)
        if name == 'abs' and len(args) == 1 and is_dt(types[0]):
            return ast.copy_location(self.call('absval', self.expr(args[0], scope)), node)
        if name == 'bool' and len(args) == 1 and is_dt(types[0]) and types[0][1] in ('timedelta', 'any') and not types[0][2]:
            return ast.copy_location(self.call('nonzero', self.expr(args[0], scope)), node)
        if name in ('sorted', 'min', 'max') and args:
            first = types[0]
            if name in ('min', 'max') and len(args) == 1 and not node.keywords and first is not None \
                    and first[0] == 'list' and is_dt(first[1]):
                return ast.copy_location(self.call(name + '_list', self.expr(args[0], scope)), node)
            if len(args) == 1 and first is not None and first[0] == 'list' and is_dt(first[1]):
                keys = [k for k in node.keywords if k.arg == 'key']
                node.args = [self.expr(args[0], scope)]
                node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in node.keywords
                                 if k.arg != 'key']
                if keys:
                    refuse(node, '%s(list of dates, key=...): key a function of the value\'s fields '
                           '(lambda d: d.toordinal()) or leave key out' % name)
                node.keywords.append(ast.keyword(arg='key', value=self.key_lambda()))
                return node
            if name in ('min', 'max') and len(args) >= 2 and any(is_dt(t) for t in types):
                if node.keywords:
                    refuse(node, '%s() of several datetimes with keywords is not built' % name)
                result = self.expr(args[0], scope)
                for each in args[1:]:
                    result = self.call('pick_' + name, result, self.expr(each, scope))
                return ast.copy_location(result, node)
            if len(args) >= 1 and any(isinstance(k, str) for k in kw_types) and 'key' in kw_types:
                elem = first[1] if first is not None and first[0] == 'list' else None
                node.args = [self.expr(a, scope) for a in args]
                node.keywords = [self.typed_key(k, elem) if k.arg == 'key' else
                                 ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in node.keywords]
                return node
        if name == 'sum' and len(args) == 2 and is_dt(types[1]):
            refuse(node, 'sum() of timedeltas is not built: start total = timedelta() and add in a for loop '
                   '(total += d)')
        if name in ('map', 'filter') and len(args) == 2 and isinstance(args[0], ast.Lambda):
            it = types[1]
            if it is not None and it[0] == 'list':
                args[0].args.args[0]._dt_type = it[1] if args[0].args.args else None
        node.args = [self.expr(a, scope) for a in args]
        node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in node.keywords]
        return node

    def method_call(self, node, scope, types, kw_types):
        func = node.func
        attr = func.attr
        recv_t = self.expr_type(func.value, scope)
        recv = self.expr(func.value, scope)
        args, keywords = node.args, node.keywords
        user = attr in self.defined
        if attr in UNBUILT_METHODS and not user and (is_dt(recv_t) or attr in ('timestamp', 'isocalendar', 'astimezone')):
            refuse(node, '.%s() %s' % (attr, UNBUILT_METHODS[attr]))
        if not user:
            if attr in ('weekday', 'isoweekday', 'toordinal', 'total_seconds') and not args and not keywords:
                return ast.copy_location(self.call(METHODS[attr], recv), node)
            if attr in ('date', 'time') and not args and not keywords and (is_dt(recv_t) or recv_t is None):
                if is_dt(recv_t) and recv_t[1] not in ('datetime', 'any'):
                    refuse(node, '.%s() is a datetime method' % attr)
                if is_dt(recv_t) or self.looks_datetime(func.value):
                    return ast.copy_location(self.call(METHODS[attr], recv), node)
            if attr == 'strftime' and len(args) + len(keywords) == 1:
                value = args[0] if args else keywords[0].value
                return ast.copy_location(self.call('fmt', recv, self.expr(value, scope)), node)
            if attr == 'isoformat' and not (is_dt(recv_t) is False and recv_t is not None):
                got = {}
                names = ['sep', 'timespec']
                if is_dt(recv_t) and recv_t[1] == 'time':
                    names = ['timespec']                    # time.isoformat(timespec)
                elif len(args) == 1 and not (is_dt(recv_t) and recv_t[1] in ('date', 'datetime')) \
                        and isinstance(args[0], ast.Constant) and args[0].value in (
                            'auto', 'hours', 'minutes', 'seconds', 'milliseconds', 'microseconds'):
                    names = ['timespec']
                if len(args) > len(names):
                    refuse(node, 'isoformat: too many arguments')
                for name, value in zip(names, args):
                    got[name] = value
                for k in keywords:
                    if k.arg not in ('sep', 'timespec'):
                        refuse(node, 'isoformat: the argument %s is not built' % k.arg)
                    got[k.arg] = k.value
                return ast.copy_location(self.call('iso', recv, self.expr(got['sep'], scope) if 'sep' in got
                                                   else ast.Constant(value='T'),
                                                   self.expr(got['timespec'], scope) if 'timespec' in got
                                                   else ast.Constant(value='auto')), node)
            if attr == 'replace':
                names = ['year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond']
                if keywords and all(k.arg in names + ['tzinfo', 'fold'] for k in keywords) and not args or \
                        (is_dt(recv_t) and not any(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in args)):
                    if any(k.arg in ('tzinfo', 'fold') for k in keywords):
                        refuse(node, 'replace(tzinfo= / fold=): timezone-aware values are not built')
                    slots = [ast.Constant(value=-1)] * 7
                    slots = list(slots)
                    for index, value in enumerate(args):
                        slots[index] = self.expr(value, scope)
                    for k in keywords:
                        slots[names.index(k.arg)] = self.expr(k.value, scope)
                    return ast.copy_location(self.call('replace', recv, *slots), node)
            if attr == 'sort' and recv_t is not None and recv_t[0] == 'list' and is_dt(recv_t[1]):
                node.func = ast.Attribute(value=recv, attr='sort', ctx=ast.Load())
                node.args = []
                node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in keywords
                                 if k.arg != 'key']
                if any(k.arg == 'key' for k in keywords):
                    refuse(node, 'sort(key=...) of a list of dates: key a function of the fields (lambda d: '
                           'd.toordinal()) is not built; sort without key')
                node.keywords.append(ast.keyword(arg='key', value=self.key_lambda()))
                return node
            if attr == 'sort' and recv_t is not None and recv_t[0] == 'list':
                pass
        # an ordinary method: the arguments are rewritten, lambdas know the element type
        if attr == 'sort' and recv_t is not None and recv_t[0] == 'list':
            for k in keywords:
                if k.arg == 'key' and isinstance(k.value, ast.Lambda) and k.value.args.args:
                    k.value.args.args[0]._dt_type = recv_t[1]
        node.func = ast.Attribute(value=recv, attr=attr, ctx=ast.Load())
        node.args = [self.expr(a, scope) for a in args]
        node.keywords = [ast.keyword(arg=k.arg, value=self.expr(k.value, scope)) for k in keywords]
        return node

    def looks_datetime(self, node):
        """A receiver whose type the pass does not know but that is built here from a datetime constructor."""
        return isinstance(node, ast.Call) and (self.path(node.func) in CLASSES or self.path(node.func) in CLASS_METHODS)

    # -- the helper source -----------------------------------------------------------------------------------------------
    def attach(self):
        if not self.used:
            return
        top, uses = runtime()
        need, stack = set(), list(self.used)
        while stack:
            name = stack.pop()
            if name in need:
                continue
            need.add(name)
            stack.extend(uses.get(name, ()))
        mapping = {name: rt_name(name) for name in top}

        class Rename(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in mapping:
                    return ast.copy_location(ast.Name(id=mapping[node.id], ctx=node.ctx), node)
                return node

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                node.name = mapping.get(node.name, node.name)
                return node

            def visit_ClassDef(self, node):
                self.generic_visit(node)
                node.name = mapping.get(node.name, node.name)
                return node
        nodes = []
        for name, node in top.items():
            if name in need:
                copy_node = copy.deepcopy(node)
                nodes.append(Rename().visit(copy_node))
        self.out.append('\n\n\n'.join(ast.unparse(n) for n in nodes))


def rewrite(imports, tree, out):
    Dt(imports, tree, out).run()
