"""Scalar Optional (`int | None`, `Optional[str]`, ...) on the typed path, as a tagged value.

A value that may be None is two values: a present flag and the scalar (`x: int | None` is `x__p: bool` and
`x__v: int`, the scalar being the kind's zero while absent). A function returning `int | None` returns the pair
(`tuple[bool, int]`), a parameter `v: int | None` is two parameters, and the rest is rewritten into plain
bool / int / float / str code the compiler already builds (called from ail_syntax.python_surface, before the
tuple pass that lowers the pairs).

    x is None / x is not None / x == None / x != None      not x__p / x__p
    x == e / x != e            (x__p and x__v == e)  -- None == 3 is False; e must be free of calls
    x == y                     both present and equal, or both absent
    x = None / x = e / x = f(..)    the flag and the scalar are set together
    print(x), f"{x}", str(x), repr(x)   "None" while absent
    if x: / not x / x and ..   present and truthy
    g(x) with g(v: int | None)  g(x__p, x__v)      g(None) is g(False, 0)

Every other use of the value (arithmetic, a method, an argument to a plain parameter, a list element, a
return from a function that is not Optional, ...) needs the compiler to know the value is present: after
`if x is None: return`, inside `if x is not None:`, right of `x is not None and`, after an assignment of a
value. Where it does not know, CPython would raise TypeError / AttributeError (or store the None), so the
program is refused by name instead of guessing: "'x' may be None here".

Not built, refused by name (the source is left as written and the reason goes to `notes`): Optional scalar fields,
methods, list / dict elements, `int | float | None`, an Optional call inside `and` / `or` / `x if c else y` /
a comprehension / a `while` test, ordering comparisons and `in` of a value not known to be present.
"""
import ast
import copy

KINDS = ('int', 'float', 'bool', 'str')
ZERO = {'int': 0, 'float': 0.0, 'bool': False, 'str': ''}
# calls whose evaluation may be reordered with an Optional call hoisted ahead of the statement
SAFE_CALLS = frozenset(('print', 'str', 'repr', 'len', 'abs', 'min', 'max', 'bool', 'int', 'float', 'round', 'sum'))
PURE_BIN = (ast.Add, ast.Sub, ast.Mult, ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)


class Refused(Exception):
    def __init__(self, node, text):
        Exception.__init__(self, text)
        self.line = getattr(node, 'lineno', 1)
        self.text = text


def _is_none(e):
    return isinstance(e, ast.Constant) and e.value is None


def _name(i, ctx=None):
    return ast.Name(id=i, ctx=ctx or ast.Load())


def _const(v):
    return ast.Constant(value=v)


def scalar_optional(ann):
    """The kind of `int | None`, `None | str`, `Optional[float]`, `Union[bool, None]`; None otherwise."""
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        for scalar, other in ((ann.left, ann.right), (ann.right, ann.left)):
            if _is_none(other) and isinstance(scalar, ast.Name) and scalar.id in KINDS:
                return scalar.id
        return None
    if isinstance(ann, ast.Subscript):
        head = ann.value
        head = head.id if isinstance(head, ast.Name) else head.attr if isinstance(head, ast.Attribute) else None
        if head == 'Optional' and isinstance(ann.slice, ast.Name) and ann.slice.id in KINDS:
            return ann.slice.id
        if head == 'Union' and isinstance(ann.slice, ast.Tuple) and len(ann.slice.elts) == 2:
            a, b = ann.slice.elts
            for scalar, other in ((a, b), (b, a)):
                if _is_none(other) and isinstance(scalar, ast.Name) and scalar.id in KINDS:
                    return scalar.id
    return None


def _mentions_optional_scalar(ann):
    """Does an annotation hold a scalar-or-None anywhere inside (list[int | None], dict[str, Optional[int]])?"""
    for node in ast.walk(ann):
        if node is not ann or True:
            if scalar_optional(node) is not None:
                return True
    return False


def _calls(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _assigned(stmts):
    """Names stored anywhere inside `stmts` (nested functions excluded)."""
    out = set()

    def walk(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        if isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        for c in ast.iter_child_nodes(n):
            walk(c)
    for s in stmts:
        walk(s)
    return out


def _terminates(stmts):
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    if isinstance(last, ast.If):
        return _terminates(last.body) and bool(last.orelse) and _terminates(last.orelse)
    return False


def _has_break(stmts):
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.Break):
                return True
    return False


class FuncInfo:
    def __init__(self, node):
        self.node = node
        self.params = []                       # (name, kind or None, default node or None)
        a = node.args
        if a.vararg or a.kwarg or a.posonlyargs:
            raise Refused(node, '%s() takes *args / **kwargs / positional-only parameters, which are not built '
                          'together with an Optional' % node.name)
        plain = a.args
        defaults = [None] * (len(plain) - len(a.defaults)) + list(a.defaults)
        for arg, default in zip(plain, defaults):
            kind = scalar_optional(arg.annotation) if arg.annotation is not None else None
            self.params.append((arg.arg, kind, default))
        for arg, default in zip(a.kwonlyargs, a.kw_defaults):
            kind = scalar_optional(arg.annotation) if arg.annotation is not None else None
            self.params.append((arg.arg, kind, default))
        for arg in a.kwonlyargs:
            if arg.annotation is not None and scalar_optional(arg.annotation) is not None:
                raise Refused(node, '%s(): a keyword-only Optional parameter is not built' % node.name)
        self.kwonly = len(a.kwonlyargs)
        # defaults up to the last Optional parameter that has one are written out at every call (a pair of
        # parameters cannot follow a parameter with a default, and a str default is not built)
        self.strip_to = max([i for i, (_, k, d) in enumerate(self.params) if k and d is not None], default=-1)
        self.ret = scalar_optional(node.returns) if node.returns is not None else None
        self.optional = self.ret is not None or any(k for _, k, _ in self.params)


class Lowerer:
    def __init__(self, tree):
        self.tree = tree
        self.funcs = {}
        self.counter = 0
        self.names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}

    # ---- program level ----
    def check_none_flow(self):
        for node in ast.walk(self.tree):
            elts = []
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                elts = node.elts
            elif isinstance(node, ast.Dict):
                elts = [x for x in node.keys + node.values if x is not None]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                elts = node.args
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                elts = [node.elt]
            elif isinstance(node, ast.DictComp):
                elts = [node.key, node.value]
            elif isinstance(node, ast.Assign) and any(isinstance(t, (ast.Subscript, ast.Attribute))
                                                      for t in node.targets):
                elts = [node.value]
            for x in elts:
                if _is_none(x):
                    raise Refused(x, 'None stored in a list / tuple / dict / set, or passed to a method, cannot be '
                                  'followed by the Optional rewrite; use a sentinel value there')

    def check_placement(self):
        self.check_none_flow()
        """Optional scalars may only be annotations of a top-level function's parameters / return and of
        locals in function bodies; anywhere else the program is refused by name."""
        allowed = set()
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                for a in node.args.args + node.args.kwonlyargs:
                    if a.annotation is not None and scalar_optional(a.annotation) is not None:
                        allowed.add(id(a.annotation))
                if node.returns is not None and scalar_optional(node.returns) is not None:
                    allowed.add(id(node.returns))
        for node in ast.walk(self.tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if scalar_optional(node.annotation) is not None:
                    allowed.add(id(node.annotation))
        for node in ast.walk(self.tree):
            anns = []
            if isinstance(node, ast.arg) and node.annotation is not None:
                anns.append(node.annotation)
            elif isinstance(node, ast.AnnAssign):
                anns.append(node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
                anns.append(node.returns)
            for ann in anns:
                if _mentions_optional_scalar(ann):
                    where = [n for n in ast.walk(ann) if scalar_optional(n) is not None]
                    if not any(id(n) in allowed for n in where) or any(id(n) not in allowed for n in where):
                        raise Refused(node, 'an Optional scalar (`%s`) is built as a parameter, a return type or a '
                                      'local of a plain function; not as a field, a method, a nested function, or '
                                      'inside list[...] / dict[...]' % ast.unparse(ann))
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = FuncInfo(node)
        # nested defs and methods may not mention an Optional scalar annotation
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node not in self.tree.body:
                for a in node.args.args + node.args.kwonlyargs:
                    if a.annotation is not None and scalar_optional(a.annotation) is not None:
                        raise Refused(node, 'a method or nested function with an Optional scalar parameter is not built')
                if node.returns is not None and scalar_optional(node.returns) is not None:
                    raise Refused(node, 'a method or nested function returning an Optional scalar is not built')
        self.opt_funcs = {n for n, f in self.funcs.items() if f.optional}

    def run(self):
        self.check_placement()
        # module-level statements may not use an Optional function (they would need module-level temporaries)
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and n.id in self.opt_funcs and n.id != 'main':
                    raise Refused(node, '%s() takes or returns an Optional and is used outside a function; '
                                  'call it from inside a function' % n.id)
        body = []
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                body.append(self.function(node))
            elif isinstance(node, ast.ClassDef):
                node = copy.deepcopy(node)
                node.body = [self.function(m) if isinstance(m, ast.FunctionDef) else m for m in node.body]
                body.append(node)
            else:
                body.append(node)
        self.tree.body = body
        return self.tree

    # ---- one function ----
    def function(self, node):
        info = self.funcs.get(node.name) if node in self.tree.body else None
        opt = {}
        for a in node.args.args + node.args.kwonlyargs:
            kind = scalar_optional(a.annotation) if a.annotation is not None else None
            if kind:
                opt[a.arg] = kind
        for n in ast.walk(node):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                kind = scalar_optional(n.annotation)
                if kind:
                    if opt.get(n.target.id, kind) != kind:
                        raise Refused(n, '%r is annotated with two different Optional kinds' % n.target.id)
                    opt[n.target.id] = kind
        has_nested = any(isinstance(n, (ast.FunctionDef, ast.Lambda, ast.AsyncFunctionDef)) and n is not node
                         for n in ast.walk(node))
        # names that take an Optional call / another Optional name: fixpoint
        changed = True
        while changed:
            changed = False
            for n in ast.walk(node):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                    kind = self.expr_kind(n.value, opt)
                    t = n.targets[0].id
                    if kind and t not in opt:
                        opt[t] = kind
                        changed = True
        uses_opt_call = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in self.opt_funcs
                            for n in ast.walk(node))
        if not opt and not uses_opt_call and not (info and info.ret):
            return node
        if has_nested and opt:
            raise Refused(node, '%s() has a nested function or lambda and an Optional variable; not built' % node.name)
        self.opt = opt
        # a parameter cannot be reassigned on the typed path: an Optional parameter that the body assigns
        # is copied into a local pair on entry
        stored = _assigned(node.body)
        self.local_params = {a.arg for a in node.args.args + node.args.kwonlyargs
                             if a.arg in opt and a.arg in stored}
        self.scan_function(node)
        self.fn = node
        self.info = info
        self.all_names = frozenset(opt)
        self.hoist_ok = True
        self.pre = []
        new = copy.copy(node)
        new.args = self.new_args(node, info)
        if info and info.ret:
            new.returns = ast.Subscript(value=_name('tuple'), slice=ast.Tuple(
                elts=[_name('bool'), _name(info.ret)], ctx=ast.Load()), ctx=ast.Load())
        facts = frozenset()
        entry = []
        for a in node.args.args + node.args.kwonlyargs:
            if a.arg in self.local_params:
                entry.append(ast.AnnAssign(target=_name(a.arg + '__lp', ast.Store()), annotation=_name('bool'),
                                           value=_name(a.arg + '__p'), simple=1))
                entry.append(ast.AnnAssign(target=_name(a.arg + '__lv', ast.Store()), annotation=_name(opt[a.arg]),
                                           value=_name(a.arg + '__v'), simple=1))
        body, out = self.block(node.body, facts)
        body = entry + body
        if info and info.ret and not _terminates(node.body):
            body = body + [ast.Return(value=self.none_pair(info.ret))]
        new.body = body or [ast.Pass()]
        return new

    def new_args(self, node, info):
        a = node.args
        if info is None or not any(k for _, k, _ in info.params):
            return a
        out = copy.copy(a)
        plain, defaults = [], []
        total = a.args
        dfl = [None] * (len(total) - len(a.defaults)) + list(a.defaults)
        for index, (arg, default) in enumerate(zip(total, dfl)):
            kind = scalar_optional(arg.annotation) if arg.annotation is not None else None
            if kind:
                plain.append(ast.arg(arg=arg.arg + '__p', annotation=_name('bool')))
                plain.append(ast.arg(arg=arg.arg + '__v', annotation=_name(kind)))
                if default is not None:
                    self.default_pair(default, kind)       # checked here, supplied by every call
            else:
                plain.append(arg)
                if default is not None and index > info.strip_to:
                    defaults.append(default)
        out.args = plain
        out.defaults = defaults
        kwonly, kwd = [], []
        for arg, default in zip(a.kwonlyargs, a.kw_defaults):
            kind = scalar_optional(arg.annotation) if arg.annotation is not None else None
            if kind:
                kwonly.append(ast.arg(arg=arg.arg + '__p', annotation=_name('bool')))
                kwonly.append(ast.arg(arg=arg.arg + '__v', annotation=_name(kind)))
                if default is not None:
                    self.default_pair(default, kind)
                kwd.extend([None, None])
            else:
                kwonly.append(arg)
                kwd.append(default)
        out.kwonlyargs = kwonly
        out.kw_defaults = kwd
        return out

    def default_pair(self, default, kind):
        if _is_none(default):
            return _const(False), _const(ZERO[kind])
        if isinstance(default, ast.Constant) and not isinstance(default.value, type(None)):
            return _const(True), default
        raise Refused(default, 'a default for an Optional parameter must be None or a literal')

    MAYBE_NONE_METHODS = frozenset(('get', 'setdefault', 'match', 'search', 'fullmatch', 'group', 'groupdict',
                                    'first', 'peek'))
    NONNULL_BUILTINS = frozenset(('len', 'int', 'float', 'str', 'bool', 'abs', 'min', 'max', 'sum', 'round', 'ord',
                                  'chr', 'repr', 'sorted', 'list', 'range', 'divmod', 'pow', 'hex', 'bin', 'oct',
                                  'tuple', 'set', 'dict', 'format', 'any', 'all', 'input', 'enumerate', 'zip',
                                  'reversed', 'isinstance', 'hash',
                                  # G11: the sqlite3 column readers never return None (a NULL is tested first)
                                  '_ail_sq_ci', '_ail_sq_cf', '_ail_sq_cs', '_ail_sq_cb'))

    def scan_function(self, node):
        self.assigns = {}
        self.untyped = {a.arg for a in node.args.args + node.args.kwonlyargs if a.annotation is None
                        and a.arg not in ('self', 'cls')}
        for n in ast.walk(node):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        self.assigns.setdefault(t.id, []).append(n.value)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                self.assigns.setdefault(n.target.id, []).append(n.value)

    def nonnull(self, e, seen=None):
        """Can `e` be shown not to evaluate to None? (A value wrapped as present must never be None.)"""
        seen = seen if seen is not None else set()
        if isinstance(e, ast.Constant):
            return e.value is not None
        if isinstance(e, (ast.JoinedStr, ast.Compare, ast.BinOp, ast.UnaryOp, ast.List, ast.Tuple, ast.Set,
                          ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)):
            return True
        if isinstance(e, ast.BoolOp):
            return all(self.nonnull(v, seen) for v in e.values)
        if isinstance(e, ast.IfExp):
            return self.nonnull(e.body, seen) and self.nonnull(e.orelse, seen)
        if isinstance(e, (ast.Subscript, ast.Attribute)):
            return True
        if isinstance(e, ast.Name):
            if e.id in self.opt:
                return False
            if e.id in seen:
                return True
            if e.id in self.untyped:
                return False
            seen.add(e.id)
            if e.id in self.assigns:
                return all(self.nonnull(v, seen) for v in self.assigns[e.id])
            return True                      # a parameter, a loop variable, a global constant
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Name):
                info = self.funcs.get(f.id)
                if info is not None:
                    return info.ret is None and info.node.returns is not None and not _is_none(info.node.returns)
                return f.id in self.NONNULL_BUILTINS
            if isinstance(f, ast.Attribute):
                if f.attr in self.MAYBE_NONE_METHODS:
                    return False
                if f.attr == 'pop' and len(e.args) > 1:
                    return False
                return True
        return False

    def wrapped(self, e):
        if not self.nonnull(e):
            raise Refused(e, 'cannot show that `%s` is not None where it becomes an Optional value; give it a name '
                          'whose assignments are all non-None expressions, or test it with `is None` first'
                          % ast.unparse(e))
        return e

    def pn(self, name):
        return name + ('__lp' if name in self.local_params else '__p')

    def vn(self, name):
        return name + ('__lv' if name in self.local_params else '__v')

    def none_pair(self, kind):
        return ast.Tuple(elts=[_const(False), _const(ZERO[kind])], ctx=ast.Load())

    # ---- kinds ----
    def expr_kind(self, e, opt):
        """The Optional kind an expression has (a name, an Optional call), else None."""
        if isinstance(e, ast.Name) and e.id in opt:
            return opt[e.id]
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in self.funcs:
            return self.funcs[e.func.id].ret
        return None

    def optish(self, e):
        """Is `e` a None, an Optional name or a call of an Optional-returning function?"""
        return (_is_none(e) or (isinstance(e, ast.Name) and e.id in self.opt)
                or (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in self.funcs
                    and self.funcs[e.func.id].ret is not None))

    def temp(self):
        self.counter += 1
        while True:
            base = '_opt%d' % self.counter
            if base + 'p' not in self.names:
                self.names.add(base + 'p')
                return base
            self.counter += 1

    def opt_of(self, e, facts):
        """(kind, p expr, v expr) for an Optional-typed expression; ('none', False, 0) for None. A call is
        hoisted into a pair of temporaries ahead of the statement."""
        if _is_none(e):
            return None, _const(False), _const(0)
        if isinstance(e, ast.Name):
            return self.opt[e.id], _name(self.pn(e.id)), _name(self.vn(e.id))
        if not self.hoist_ok:
            raise Refused(e, 'the Optional result of %s() is used where it cannot be evaluated ahead of the '
                          'statement (inside and / or, a conditional expression, a comprehension, a while test, or '
                          'beside another call); assign it to a name first' % e.func.id)
        call = self.call(e, facts, as_value=True)
        base = self.temp()
        p, v = _name(base + 'p', ast.Store()), _name(base + 'v', ast.Store())
        self.pre.append(ast.Assign(targets=[ast.Tuple(elts=[p, v], ctx=ast.Store())], value=call))
        return self.funcs[e.func.id].ret, _name(base + 'p'), _name(base + 'v')

    # ---- narrowing ----
    def tests(self, e):
        """(names present when `e` is true, names present when `e` is false)."""
        e0 = frozenset()
        if isinstance(e, ast.Name) and e.id in self.opt:
            return frozenset((e.id,)), e0
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            t, f = self.tests(e.operand)
            return f, t
        if isinstance(e, ast.Compare) and len(e.ops) == 1:
            left, right, op = e.left, e.comparators[0], e.ops[0]
            if _is_none(left):
                left, right = right, left
            if _is_none(right) and isinstance(left, ast.Name) and left.id in self.opt:
                if isinstance(op, (ast.IsNot, ast.NotEq)):
                    return frozenset((left.id,)), e0
                if isinstance(op, (ast.Is, ast.Eq)):
                    return e0, frozenset((left.id,))
            return e0, e0
        if isinstance(e, ast.BoolOp):
            ts = [self.tests(v) for v in e.values]
            if isinstance(e.op, ast.And):
                true = frozenset().union(*[t for t, _ in ts])
                false = None
                acc = frozenset()
                for t, f in ts:
                    cand = f | acc
                    false = cand if false is None else false & cand
                    acc = acc | t
                return true, false or e0
            false = frozenset().union(*[f for _, f in ts])
            true = None
            acc = frozenset()
            for t, f in ts:
                cand = t | acc
                true = cand if true is None else true & cand
                acc = acc | f
            return true or e0, false
        return e0, e0

    # ---- statements ----
    def block(self, stmts, facts):
        out = []
        for s in stmts:
            new, facts = self.stmt(s, facts)
            out.extend(new)
        return out, facts

    def lower_expr(self, e, facts, test=False, hoist=True):
        """Lower one statement-level expression; its hoisted statements are returned in front."""
        saved_pre, self.pre = self.pre, []
        saved_ok = self.hoist_ok
        others = [c for c in _calls(e) if not (isinstance(c.func, ast.Name)
                                               and (c.func.id in SAFE_CALLS or c.func.id in self.opt_funcs
                                                    or c.func.id in self.funcs and self.funcs[c.func.id].ret))]
        self.hoist_ok = hoist and not others
        try:
            result = self.ex(e, facts, test)
            pre = self.pre
        finally:
            self.pre = saved_pre
            self.hoist_ok = saved_ok
        return pre, result

    def stmt(self, s, facts):
        m = getattr(self, 'st_' + type(s).__name__, None)
        if m is not None:
            return m(s, facts)
        # statements without an expression of interest
        if isinstance(s, (ast.Pass, ast.Break, ast.Continue, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
            return [s], facts
        if isinstance(s, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            return [s], facts
        mentioned = [n for n in ast.walk(s) if isinstance(n, ast.Name) and n.id in self.opt]
        calls = self.opt_calls_in(s)
        if mentioned or calls:
            raise Refused(s, 'a %s statement that uses an Optional value is not built' % type(s).__name__.lower())
        return [s], facts

    def opt_calls_in(self, s):
        return [n for n in ast.walk(s) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in self.funcs and self.funcs[n.func.id].optional]

    def st_Expr(self, s, facts):
        pre, v = self.lower_expr(s.value, facts)
        return pre + [ast.Expr(value=v)], facts

    def st_Raise(self, s, facts):
        pre = []
        new = copy.copy(s)
        if s.exc is not None:
            p, new.exc = self.lower_expr(s.exc, facts)
            pre += p
        return pre + [new], facts

    def st_Assert(self, s, facts):
        pre, test = self.lower_expr(s.test, facts, test=True)
        new = copy.copy(s)
        new.test = test
        if s.msg is not None:
            p, new.msg = self.lower_expr(s.msg, facts)
            pre += p
        t, _ = self.tests(s.test)
        return pre + [new], facts | t

    def st_Delete(self, s, facts):
        for n in ast.walk(s):
            if isinstance(n, ast.Name) and n.id in self.opt:
                raise Refused(s, 'del of an Optional variable is not built')
        return [s], facts

    def st_Return(self, s, facts):
        info = self.info
        if info is not None and info.ret:
            return self.return_opt(s.value, info.ret, facts, s), facts
        if s.value is None:
            return [s], facts
        pre, v = self.lower_expr(s.value, facts)
        return pre + [ast.Return(value=v)], facts

    def return_opt(self, value, kind, facts, node):
        """Statements returning `value` from a function whose result is `kind | None`."""
        if value is None or _is_none(value):
            return [ast.Return(value=self.none_pair(kind))]
        if isinstance(value, ast.IfExp) and (self.optish(value.body) or self.optish(value.orelse)
                                              or isinstance(value.body, ast.IfExp) or isinstance(value.orelse, ast.IfExp)):
            pre, test = self.lower_expr(value.test, facts, test=True)
            t, f = self.tests(value.test)
            return pre + [ast.If(test=test, body=self.return_opt(value.body, kind, facts | t, node),
                                 orelse=self.return_opt(value.orelse, kind, facts | f, node))]
        if isinstance(value, ast.Name) and value.id in self.opt:
            return [ast.Return(value=ast.Tuple(elts=[_name(self.pn(value.id)), _name(self.vn(value.id))],
                                               ctx=ast.Load()))]
        if isinstance(value, ast.Call) and self.optish(value):
            pre, _ = [], None
            saved, self.pre = self.pre, []
            try:
                call = self.call(value, facts, as_value=True)
                hoisted = self.pre
            finally:
                self.pre = saved
            return hoisted + [ast.Return(value=call)]
        self.wrapped(value)
        pre, v = self.lower_expr(value, facts)
        return pre + [ast.Return(value=ast.Tuple(elts=[_const(True), v], ctx=ast.Load()))]

    def assign_opt(self, name, value, facts, node):
        """Statements for `name = value` where `name` is an Optional variable; returns (stmts, facts)."""
        kind = self.opt[name]
        p, v = self.pn(name), self.vn(name)

        def store(n):
            return _name(n, ast.Store())
        if _is_none(value):
            return [ast.Assign(targets=[store(p)], value=_const(False)),
                    ast.Assign(targets=[store(v)], value=_const(ZERO[kind]))], facts - {name}
        if isinstance(value, ast.IfExp) and (self.optish(value.body) or self.optish(value.orelse)
                                              or isinstance(value.body, ast.IfExp) or isinstance(value.orelse, ast.IfExp)):
            pre, test = self.lower_expr(value.test, facts, test=True)
            t, f = self.tests(value.test)
            a, fa = self.assign_opt(name, value.body, facts | t, node)
            b, fb = self.assign_opt(name, value.orelse, facts | f, node)
            return pre + [ast.If(test=test, body=a, orelse=b)], fa & fb
        if self.optish(value):
            if isinstance(value, ast.Name):
                if value.id == name:
                    return [], facts
                src_present = value.id in facts
                return ([ast.Assign(targets=[store(p)], value=_name(self.pn(value.id))),
                         ast.Assign(targets=[store(v)], value=_name(self.vn(value.id)))],
                        (facts | {name}) if src_present else facts - {name})
            saved, self.pre = self.pre, []
            try:
                call = self.call(value, facts, as_value=True)
                hoisted = self.pre
            finally:
                self.pre = saved
            return (hoisted + [ast.Assign(targets=[ast.Tuple(elts=[store(p), store(v)], ctx=ast.Store())], value=call)],
                    facts - {name})
        self.wrapped(value)
        pre, expr = self.lower_expr(value, facts)
        return (pre + [ast.Assign(targets=[store(v)], value=expr), ast.Assign(targets=[store(p)], value=_const(True))],
                facts | {name})

    def st_Assign(self, s, facts):
        opt_targets = [t for t in s.targets if isinstance(t, ast.Name) and t.id in self.opt]
        if opt_targets:
            if len(s.targets) != 1:
                raise Refused(s, 'a chained assignment to an Optional variable is not built')
            return self.assign_opt(opt_targets[0].id, s.value, facts, s)
        for t in s.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name) and n.id in self.opt:
                    raise Refused(s, 'an Optional variable inside a tuple / subscript assignment target is not built')
        pre, v = self.lower_expr(s.value, facts)
        new = copy.copy(s)
        new.value = v
        tp = []
        targets = []
        for t in s.targets:
            if isinstance(t, ast.Name):
                targets.append(t)
            else:
                p, nt = self.lower_target(t, facts)
                tp += p
                targets.append(nt)
        new.targets = targets
        return pre + tp + [new], facts

    def lower_target(self, t, facts):
        """A subscript / attribute target: its index and base are ordinary value uses."""
        if isinstance(t, ast.Subscript):
            p1, base = self.lower_expr(t.value, facts)
            p2, sl = self.lower_expr(t.slice, facts)
            new = copy.copy(t)
            new.value, new.slice = base, sl
            return p1 + p2, new
        if isinstance(t, ast.Attribute):
            p1, base = self.lower_expr(t.value, facts)
            new = copy.copy(t)
            new.value = base
            return p1, new
        return [], t

    def st_AnnAssign(self, s, facts):
        if isinstance(s.target, ast.Name) and s.target.id in self.opt and scalar_optional(s.annotation):
            name, kind = s.target.id, self.opt[s.target.id]
            decl = [ast.AnnAssign(target=_name(self.pn(name), ast.Store()), annotation=_name('bool'),
                                  value=_const(False), simple=1),
                    ast.AnnAssign(target=_name(self.vn(name), ast.Store()), annotation=_name(kind),
                                  value=_const(ZERO[kind]), simple=1)]
            if s.value is None or _is_none(s.value):
                return decl, facts - {name}
            body, out = self.assign_opt(name, s.value, facts, s)
            return decl + body, out
        if s.value is None:
            return [s], facts
        pre, v = self.lower_expr(s.value, facts)
        new = copy.copy(s)
        new.value = v
        return pre + [new], facts

    def st_AugAssign(self, s, facts):
        if isinstance(s.target, ast.Name) and s.target.id in self.opt:
            name = s.target.id
            if name not in facts:
                raise Refused(s, "'%s' may be None here; test `%s is not None` (or return / continue when it is "
                              "None) before using its value" % (name, name))
            pre, v = self.lower_expr(s.value, facts)
            return pre + [ast.AugAssign(target=_name(self.vn(name), ast.Store()), op=s.op, value=v)], facts
        p1, target = self.lower_target(s.target, facts) if not isinstance(s.target, ast.Name) else ([], s.target)
        pre, v = self.lower_expr(s.value, facts)
        new = copy.copy(s)
        new.target, new.value = target, v
        return p1 + pre + [new], facts

    def st_If(self, s, facts):
        pre, test = self.lower_expr(s.test, facts, test=True)
        t, f = self.tests(s.test)
        body, bout = self.block(s.body, facts | t)
        orelse, eout = self.block(s.orelse, facts | f)
        if _terminates(s.body) and s.orelse and _terminates(s.orelse):
            out = self.all_names
        elif _terminates(s.body):
            out = eout
        elif s.orelse and _terminates(s.orelse):
            out = bout
        else:
            out = bout & eout
        return pre + [ast.If(test=test, body=body or [ast.Pass()], orelse=orelse)], out

    def st_While(self, s, facts):
        entry = facts - _assigned([s])
        pre, test = self.lower_expr(s.test, entry, test=True, hoist=False)
        t, f = self.tests(s.test)
        body, _ = self.block(s.body, entry | t)
        orelse, _ = self.block(s.orelse, entry | f)
        out = entry if _has_break(s.body) else entry | f
        return [ast.While(test=test, body=body or [ast.Pass()], orelse=orelse)], out

    def st_For(self, s, facts):
        for n in ast.walk(s.target):
            if isinstance(n, ast.Name) and n.id in self.opt:
                raise Refused(s, 'a loop variable that is also an Optional variable is not built')
        pre, it = self.lower_expr(s.iter, facts)
        entry = facts - _assigned([s])
        body, _ = self.block(s.body, entry)
        orelse, _ = self.block(s.orelse, entry)
        new = copy.copy(s)
        new.iter, new.body, new.orelse = it, body or [ast.Pass()], orelse
        return pre + [new], entry

    def st_Try(self, s, facts):
        entry = facts - _assigned([s])
        new = copy.copy(s)
        new.body, _ = self.block(s.body, facts)
        handlers = []
        for h in s.handlers:
            nh = copy.copy(h)
            nh.body, _ = self.block(h.body, entry)
            handlers.append(nh)
        new.handlers = handlers
        new.orelse, _ = self.block(s.orelse, entry)
        new.finalbody, _ = self.block(s.finalbody, entry)
        return [new], entry

    def st_With(self, s, facts):
        pre = []
        items = []
        for item in s.items:
            if item.optional_vars is not None:
                for n in ast.walk(item.optional_vars):
                    if isinstance(n, ast.Name) and n.id in self.opt:
                        raise Refused(s, 'a with-target that is an Optional variable is not built')
            p, ce = self.lower_expr(item.context_expr, facts)
            pre += p
            items.append(ast.withitem(context_expr=ce, optional_vars=item.optional_vars))
        entry = facts - _assigned([s])
        body, _ = self.block(s.body, facts)
        new = copy.copy(s)
        new.items, new.body = items, body
        return pre + [new], entry

    # ---- expressions ----
    def need_present(self, name, node):
        raise Refused(node, "'%s' may be None here; test `%s is not None` (or return / continue when it is None) "
                      "before using its value" % (name, name))

    def conv(self, e, facts):
        """The text `print` / `str` would show for an Optional-typed expression."""
        kind, p, v = self.opt_of(e, facts)
        if kind is None:                       # the None constant
            return _const('None')
        shown = v if kind == 'str' else ast.Call(func=_name('str'), args=[v], keywords=[])
        return ast.IfExp(test=p, body=shown, orelse=_const('None'))

    def truth(self, e, facts):
        kind, p, v = self.opt_of(e, facts)
        if kind == 'bool':
            body = v
        elif kind == 'str':
            body = ast.Compare(left=v, ops=[ast.NotEq()], comparators=[_const('')])
        elif kind == 'float':
            body = ast.Compare(left=v, ops=[ast.NotEq()], comparators=[_const(0.0)])
        else:
            body = ast.Compare(left=v, ops=[ast.NotEq()], comparators=[_const(0)])
        return ast.BoolOp(op=ast.And(), values=[p, body])

    def pure(self, e):
        """Free of calls and subscripts, so evaluating it only when needed makes no difference."""
        for n in ast.walk(e):
            if isinstance(n, (ast.Call, ast.Subscript, ast.Lambda, ast.ListComp, ast.GeneratorExp, ast.SetComp,
                              ast.DictComp, ast.Await, ast.Yield, ast.NamedExpr)):
                return False
            if isinstance(n, ast.BinOp) and not isinstance(n.op, PURE_BIN):
                return False
            if isinstance(n, ast.Name) and n.id in self.opt:
                return False
        return True

    def ex(self, e, facts, test=False):
        m = getattr(self, 'ex_' + type(e).__name__, None)
        if m is not None:
            return m(e, facts, test)
        return self.generic(e, facts)

    def generic(self, e, facts):
        new = copy.copy(e)
        for field, value in ast.iter_fields(e):
            if isinstance(value, ast.expr):
                setattr(new, field, self.ex(value, facts))
            elif isinstance(value, list):
                items = []
                for item in value:
                    if isinstance(item, ast.expr):
                        items.append(self.ex(item, facts))
                    elif isinstance(item, ast.keyword):
                        k = copy.copy(item)
                        k.value = self.ex(item.value, facts)
                        items.append(k)
                    elif isinstance(item, ast.comprehension):
                        items.append(self.comprehension(item, facts))
                    else:
                        items.append(item)
                setattr(new, field, items)
        return new

    def comprehension(self, c, facts):
        for n in ast.walk(c.target):
            if isinstance(n, ast.Name) and n.id in self.opt:
                raise Refused(c.target, 'a comprehension variable that is also an Optional variable is not built')
        saved = self.hoist_ok
        self.hoist_ok = False
        try:
            new = copy.copy(c)
            new.iter = self.ex(c.iter, facts)
            new.ifs = [self.ex(i, facts, True) for i in c.ifs]
        finally:
            self.hoist_ok = saved
        return new

    def ex_ListComp(self, e, facts, test):
        return self.comp(e, facts, ('elt',))

    ex_SetComp = ex_GeneratorExp = ex_ListComp

    def ex_DictComp(self, e, facts, test):
        return self.comp(e, facts, ('key', 'value'))

    def comp(self, e, facts, fields):
        saved = self.hoist_ok
        self.hoist_ok = False
        try:
            new = copy.copy(e)
            new.generators = [self.comprehension(c, facts) for c in e.generators]
            for f in fields:
                setattr(new, f, self.ex(getattr(e, f), facts))
        finally:
            self.hoist_ok = saved
        return new

    def ex_Lambda(self, e, facts, test):
        for n in ast.walk(e):
            if isinstance(n, ast.Name) and n.id in self.opt or self.opt_calls_in(e):
                raise Refused(e, 'a lambda that uses an Optional value is not built')
        return e

    def ex_Name(self, e, facts, test):
        if e.id in self.opt and isinstance(e.ctx, ast.Load):
            if test:
                return self.truth(e, facts)
            if e.id in facts:
                return _name(self.vn(e.id))
            self.need_present(e.id, e)
        return e

    def ex_Constant(self, e, facts, test):
        return e

    def ex_UnaryOp(self, e, facts, test):
        if isinstance(e.op, ast.Not):
            return ast.UnaryOp(op=ast.Not(), operand=self.ex(e.operand, facts, True))
        return self.generic(e, facts)

    def ex_BoolOp(self, e, facts, test):
        values = []
        acc = facts
        saved = self.hoist_ok
        try:
            for i, v in enumerate(e.values):
                if i:
                    self.hoist_ok = False
                values.append(self.ex(v, acc, test))
                t, f = self.tests(v)
                acc = acc | (t if isinstance(e.op, ast.And) else f)
        finally:
            self.hoist_ok = saved
        return ast.BoolOp(op=e.op, values=values)

    def ex_IfExp(self, e, facts, test):
        t, f = self.tests(e.test)
        cond = self.ex(e.test, facts, True)
        saved = self.hoist_ok
        self.hoist_ok = False
        try:
            body = self.ex(e.body, facts | t, test)
            orelse = self.ex(e.orelse, facts | f, test)
        finally:
            self.hoist_ok = saved
        for branch, known in ((e.body, facts | t), (e.orelse, facts | f)):
            if self.optish(branch) and not (isinstance(branch, ast.Name) and branch.id in known):
                raise Refused(e, 'a conditional expression with an Optional (or None) branch is built only as the '
                              'value of an assignment or a return; write an if statement')
        return ast.IfExp(test=cond, body=body, orelse=orelse)

    def ex_Compare(self, e, facts, test):
        operands = [e.left] + e.comparators
        # the literal None counts as Optional-ish, but a comparison whose only Optional-ish operand is that literal
        # ( with a class instance) is not an Optional comparison: leave it to the typed path (G11)
        if any(self.optish(x) for x in operands) and (
                any(self.optish(x) and not _is_none(x) for x in operands) or all(_is_none(x) for x in operands)):
            if len(e.ops) != 1:
                raise Refused(e, 'a chained comparison of an Optional value is not built')
            op, left, right = e.ops[0], e.left, e.comparators[0]
            if isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
                negate = isinstance(op, (ast.IsNot, ast.NotEq))
                if _is_none(left) and _is_none(right):
                    return _const(not negate)
                lo, ro = self.optish(left), self.optish(right)
                if lo and ro and isinstance(op, (ast.Is, ast.IsNot)) and not (_is_none(left) or _is_none(right)):
                    raise Refused(e, "`is` / `is not` of two Optional values is not built (CPython compares identity); "
                                  "use == / !=")
                if lo and ro:
                    if _is_none(left) or _is_none(right):
                        _, p, _ = self.opt_of(right if _is_none(left) else left, facts)
                        return p if negate else ast.UnaryOp(op=ast.Not(), operand=p)
                    _, lp, lv = self.opt_of(left, facts)
                    _, rp, rv = self.opt_of(right, facts)
                    same = ast.BoolOp(op=ast.Or(), values=[
                        ast.BoolOp(op=ast.And(), values=[lp, rp, ast.Compare(left=lv, ops=[ast.Eq()], comparators=[rv])]),
                        ast.BoolOp(op=ast.And(), values=[ast.UnaryOp(op=ast.Not(), operand=lp),
                                                         ast.UnaryOp(op=ast.Not(), operand=rp)])])
                    return ast.UnaryOp(op=ast.Not(), operand=same) if negate else same
                if isinstance(op, (ast.Is, ast.IsNot)):
                    raise Refused(e, '`is` / `is not` of an Optional value with something other than None is not built')
                opt_side, other = (left, right) if lo else (right, left)
                if not self.pure(other):
                    raise Refused(e, 'an Optional value compared with an expression that calls or indexes; assign '
                                  'the expression to a name first')
                if _is_none(opt_side):
                    return _const(negate)
                _, p, v = self.opt_of(opt_side, facts)
                o = self.ex(other, facts)
                cmp = ast.Compare(left=v, ops=[ast.Eq()], comparators=[o]) if opt_side is left else \
                    ast.Compare(left=o, ops=[ast.Eq()], comparators=[v])
                eq = ast.BoolOp(op=ast.And(), values=[p, cmp])
                return ast.UnaryOp(op=ast.Not(), operand=eq) if negate else eq
        return self.generic(e, facts)

    def ex_JoinedStr(self, e, facts, test):
        values = []
        for v in e.values:
            if (isinstance(v, ast.FormattedValue) and self.optish(v.value) and not _is_none(v.value)
                    and v.format_spec is None and v.conversion in (-1, 115)):
                values.append(ast.FormattedValue(value=self.conv(v.value, facts), conversion=-1, format_spec=None))
            elif isinstance(v, ast.FormattedValue):
                nv = copy.copy(v)
                nv.value = self.ex(v.value, facts)
                nv.format_spec = self.ex(v.format_spec, facts) if v.format_spec is not None else None
                values.append(nv)
            else:
                values.append(v)
        return ast.JoinedStr(values=values)

    def ex_Call(self, e, facts, test):
        return self.call(e, facts, as_value=False, test=test)

    def call(self, e, facts, as_value, test=False):
        f = e.func
        if isinstance(f, ast.Name):
            name = f.id
            info = self.funcs.get(name)
            if info is not None and info.node in self.tree.body and name not in self.opt:
                if info.ret and not as_value:
                    raise Refused(e, "%s() returns an Optional; assign the result to a name and test it with "
                                  "`is None` before using it as a value" % name)
                return self.user_call(e, info, facts)
            if name == 'print':
                args = [self.conv(a, facts) if self.optish(a) and not _is_none(a) else self.ex(a, facts)
                        for a in e.args]
                kws = [ast.keyword(arg=k.arg, value=self.ex(k.value, facts)) for k in e.keywords]
                return ast.Call(func=f, args=args, keywords=kws)
            if name in ('str', 'repr') and len(e.args) == 1 and not e.keywords \
                    and self.optish(e.args[0]) and not _is_none(e.args[0]):
                kind, p, v = self.opt_of(e.args[0], facts)
                shown = v if (name == 'str' and kind == 'str') else ast.Call(func=f, args=[v], keywords=[])
                return ast.IfExp(test=p, body=shown, orelse=_const('None'))
            if name == 'bool' and len(e.args) == 1 and not e.keywords and self.optish(e.args[0]) \
                    and not _is_none(e.args[0]):
                return self.truth(e.args[0], facts)
            if name in ('isinstance', 'type', 'id', 'hash', 'format', 'callable', 'getattr', 'hasattr', 'repr', 'str'):
                for a in e.args:
                    if self.optish(a):
                        raise Refused(e, '%s() of an Optional value is not built' % name)
        return self.generic_call(e, facts)

    def generic_call(self, e, facts):
        new = copy.copy(e)
        new.func = self.ex(e.func, facts) if not isinstance(e.func, ast.Name) else e.func
        new.args = [self.ex(a, facts) for a in e.args]
        new.keywords = [ast.keyword(arg=k.arg, value=self.ex(k.value, facts)) for k in e.keywords]
        return new

    def arg_pair(self, a, facts, kind=None):
        if _is_none(a) and kind:
            return _const(False), _const(ZERO[kind])
        if self.optish(a):
            kind, p, v = self.opt_of(a, facts)
            return p, v
        if isinstance(a, ast.IfExp) and (self.optish(a.body) or self.optish(a.orelse)):
            raise Refused(a, 'a conditional expression with an Optional (or None) branch as an argument is not built; '
                          'assign it to a name first')
        self.wrapped(a)
        return _const(True), self.ex(a, facts)

    def user_call(self, e, info, facts):
        new = copy.copy(e)
        args = []
        for i, a in enumerate(e.args):
            if isinstance(a, ast.Starred):
                raise Refused(e, '*args in a call of %s(), which takes an Optional, is not built' % info.node.name)
            kind = info.params[i][1] if i < len(info.params) else None
            if kind:
                p, v = self.arg_pair(a, facts, kind)
                args.extend([p, v])
            else:
                args.append(self.ex(a, facts))
        kws = []
        by_name = {n: k for n, k, _ in info.params}
        for k in e.keywords:
            if k.arg is None:
                raise Refused(e, '**kwargs in a call of %s(), which takes an Optional, is not built' % info.node.name)
            if by_name.get(k.arg):
                p, v = self.arg_pair(k.value, facts, by_name[k.arg])
                kws.append(ast.keyword(arg=k.arg + '__p', value=p))
                kws.append(ast.keyword(arg=k.arg + '__v', value=v))
            else:
                kws.append(ast.keyword(arg=k.arg, value=self.ex(k.value, facts)))
        given = {info.params[i][0] for i in range(min(len(e.args), len(info.params)))} | {k.arg for k in e.keywords}
        for index, (name, kind, default) in enumerate(info.params):
            if default is not None and index <= info.strip_to and name not in given:
                if kind:
                    p, v = self.default_pair(default, kind)
                    kws.append(ast.keyword(arg=name + "__p", value=p))
                    kws.append(ast.keyword(arg=name + "__v", value=v))
                else:
                    kws.append(ast.keyword(arg=name, value=copy.deepcopy(default)))
        new.args, new.keywords = args, kws
        return new


def _pad(tree, source_lines):
    """Unparse the module one top-level statement at a time, keeping each statement on its own first line."""
    out = []
    line = 1
    for node in tree.body:
        text = ast.unparse(node)
        start = min([getattr(node, 'lineno', line)] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        while line < start:
            out.append('')
            line += 1
        out.append(text)
        line += text.count('\n') + 1
    return '\n'.join(out) + '\n'


def candidate(tree):
    for node in ast.walk(tree):
        ann = None
        if isinstance(node, ast.arg):
            ann = node.annotation
        elif isinstance(node, ast.AnnAssign):
            ann = node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ann = node.returns
        if ann is not None and _mentions_optional_scalar(ann):
            return True
    return False


def rewrite(source, notes=None):
    """The program with its scalar Optionals lowered to flag + value pairs; the source as written when it has none
    (or when a use is not built -- the reason is then added to `notes`)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not candidate(tree):
        return source
    try:
        lowered = Lowerer(tree).run()
        ast.fix_missing_locations(lowered)
        return _pad(lowered, source.split('\n'))
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError, AssertionError) as exc:
        if notes is not None:
            notes.append((1, 'the Optional rewrite could not handle this program (%s: %s); simplify the Optional '
                          'use or report it' % (type(exc).__name__, exc)))
        return source


if __name__ == '__main__':
    import sys
    from pathlib import Path
    notes = []
    print(rewrite(Path(sys.argv[1]).read_text(encoding='utf-8'), notes))
    for n in notes:
        print('NOTE', n, file=sys.stderr)
