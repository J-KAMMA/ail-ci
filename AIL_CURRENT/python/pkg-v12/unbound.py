"""Definite assignment for the typed path: a local read where it may be unassigned raises CPython's UnboundLocalError.

    def f(a):
        if a > 0:
            z = a
        return z          # f(-1): UnboundLocalError: cannot access local variable 'z' where it is not associated with a value

A typed local always holds a value (a C variable), so the unassigned read used to give 0.  This pass runs on the tree
(typed path only: `pyfunc.to_c`, before the front end's other passes see it, so the legacy emitter and the IR lowering
both get the same Python) and does a must-assigned dataflow over each function:

* a read that is definitely assigned is left alone: a function without a possibly-unassigned read is not touched, and a
  program without such a function is byte-identical;
* otherwise the variable gets a flag local `_ail_set_<name>` (False at entry, True after each binding statement) and
  each such read becomes `name if (_ail_set_name or _ail_unbound_name()) else name`, where the generated
  `_ail_unbound_name` raises `UnboundLocalError(...)`.  An `x += 1` whose x may be unassigned checks first.  The
  classes `NameError` and `UnboundLocalError` (a subclass) are added as user exception classes (userexc.py) so that a
  handler for either, or for Exception, catches it.

What it refuses (`Unsupported`, so the program or function is taken by the general path, which is right already): a
possibly-unassigned variable that is bound by a walrus, import, def, class or `except ... as`; a name an enclosing
function reads from a nested def, lambda or class body without it being definitely assigned where the nested one
is made (and, for a def, at every reference to it); a function using `locals()`, `vars()`, `exec` or `eval`.
A generator or async function is left alone.

Mixed mode (a typed clone of a boxed function) never raises across the two exception stacks, so with
`info['_mixed_clone']` set the function is refused when a function reachable from the entry needs a flag.  A separately
compiled module (library / external) cannot carry the helpers, so it is refused too.

A script's top-level statements are made into one function by pyc._rewrite_script (it records the name in SCRIPT):
there the names are module globals, and CPython's error is `NameError: name 'z' is not defined`, which that function's
helpers (`_ail_undefined_<name>`) raise instead.

The expression form is used for every read, so the error comes at the moment CPython raises it (after the earlier
operands, inside a branch that is not taken it does not come at all).  A read that is the receiver of a container
operation (`xs.append(1)`, `d[0]`) is no longer the shape the typed path takes, so such a program is built by the
general path (right, slower).  Census: `python3 unbound.py file.py` lists the functions that would need flags.
"""
import ast
import copy

ALL = None          # the definitely-assigned "set" after a statement that does not complete (everything holds)
FLAG = '_ail_set_'
HELPER = '_ail_unbound_'
SCRIPT_HELPER = '_ail_undefined_'
MESSAGE = "cannot access local variable '%s' where it is not associated with a value"
SCRIPT_MESSAGE = "name '%s' is not defined"
SCRIPT = set()      # names of the functions pyc._rewrite_script made of a script's top-level statements (module scope)


def _inter(a, b):
    if a is ALL:
        return b
    if b is ALL:
        return a
    return a & b


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_COMPS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _own_nodes(fn):
    """Every node of `fn`'s own scope (not the insides of nested defs, lambdas and classes, which are listed as nodes)."""
    out = []
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        out.append(n)
        if isinstance(n, _SCOPES):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stack.extend(n.decorator_list)
                stack.extend(d for d in n.args.defaults if d is not None)
                stack.extend(d for d in n.args.kw_defaults if d is not None)
            elif isinstance(n, ast.Lambda):
                stack.extend(d for d in n.args.defaults if d is not None)
                stack.extend(d for d in n.args.kw_defaults if d is not None)
            else:
                stack.extend(n.decorator_list)
                stack.extend(n.bases)
                stack.extend(k.value for k in n.keywords)
            continue
        stack.extend(ast.iter_child_nodes(n))
    return out


def _params(args):
    return ([a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
            + ([args.vararg.arg] if args.vararg else []) + ([args.kwarg.arg] if args.kwarg else []))


def _pattern_names(p):
    out = []
    for n in ast.walk(p):
        if isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            out.append(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            out.append(n.rest)
    return out


def _target_names(t):
    return [n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]


def _scope_stores(scope):
    """Names a nested scope binds itself (parameters and stores of its own statements)."""
    names = set()
    if isinstance(scope, ast.Lambda):
        names.update(_params(scope.args))
        return names
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.update(_params(scope.args))
    for n in _own_nodes(scope):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
    return names


def _captured_loads(scope):
    """Names loaded anywhere inside a nested scope that the scope does not bind itself (over-approximate)."""
    bound = _scope_stores(scope)
    out = set()
    parts = [scope.body] if isinstance(scope, ast.Lambda) else scope.body
    for part in (parts if isinstance(parts, list) else [parts]):
        for n in ast.walk(part):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound:
                out.add(n.id)
    return out


class Analysis(object):
    """Result for one function: `bad` Name loads, `bad_aug` AugAssign statements, flagged names, `refusal` text."""

    def __init__(self):
        self.bad = []
        self.bad_aug = []
        self.flagged = set()
        self.refusal = None
        self.script = False       # the function is a script's top-level code: CPython says NameError, 'name is not defined'

    @property
    def helper(self):
        return SCRIPT_HELPER if self.script else HELPER


class _Flow(object):
    def __init__(self, fn):
        self.fn = fn
        self.res = Analysis()
        self.quiet = 0
        self.loops = []
        own = _own_nodes(fn)
        self.own = own
        params = set(_params(fn.args))
        declared = set()
        other = set()        # bound by def / class / import / except-as: always taken as assigned
        var = set()
        comp_targets = set()           # the variables of a comprehension are its own, not the function's
        for n in own:
            if isinstance(n, _COMPS):
                for g in n.generators:
                    comp_targets.update(id(x) for x in ast.walk(g.target))
        for n in own:
            if isinstance(n, ast.Name) and id(n) in comp_targets:
                continue
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                declared.update(n.names)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                var.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                other.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                other.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                other.add(n.name)
            elif isinstance(n, ast.match_case):
                var.update(_pattern_names(n.pattern))
        self.params = params
        self.tracked = var - params - declared - other
        self.nested = {n.name: n for n in own if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.refs = {}            # nested def name -> [state at each load in this scope]
        self.captures = []        # (scope node, state where it is made)
        self.deleted = {n.id for n in own if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del)}
        # every load of a nested def's name inside another nested scope escapes the reference analysis
        self.escaped = set()
        for n in own:
            if isinstance(n, _SCOPES):
                for name in _captured_loads(n):
                    if name in self.nested and not (isinstance(n, ast.FunctionDef) and n.name == name):
                        self.escaped.add(name)

    # ---- expressions: return the state after evaluating, record the reads that may be unassigned
    def read(self, node, A):
        if A is not ALL and node.id in self.tracked and node.id not in A and not self.quiet:
            self.res.bad.append(node)

    def expr(self, n, A):
        if n is None or A is ALL:
            return A
        t = type(n)
        if t is ast.Name:
            if isinstance(n.ctx, ast.Load):
                self.read(n, A)
                if n.id in self.nested:
                    self.refs.setdefault(n.id, []).append(A)
            return A
        if t is ast.BoolOp:
            A1 = self.expr(n.values[0], A)
            cur = A1
            for v in n.values[1:]:
                cur = self.expr(v, cur)
            return A1
        if t is ast.IfExp:
            A1 = self.expr(n.test, A)
            return _inter(self.expr(n.body, A1), self.expr(n.orelse, A1))
        if t is ast.NamedExpr:
            A1 = self.expr(n.value, A)
            return A1 | {n.target.id}
        if t in _COMPS:
            return self.comprehension(n, A)
        if t is ast.Lambda:
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                A = self.expr(d, A)
            self.captures.append((n, A))
            return A
        for child in ast.iter_child_nodes(n):
            A = self.expr(child, A)
        return A

    def comprehension(self, n, A):
        A1 = self.expr(n.generators[0].iter, A)
        bound = set()
        for g in n.generators:
            bound.update(_target_names(g.target))
        saved = self.tracked
        self.tracked = saved - bound
        try:
            for i, g in enumerate(n.generators):
                if i:
                    self.expr(g.iter, A1)
                for cond in g.ifs:
                    self.expr(cond, A1)
            if isinstance(n, ast.DictComp):
                self.expr(n.key, A1)
                self.expr(n.value, A1)
            else:
                self.expr(n.elt, A1)
        finally:
            self.tracked = saved
        return A1

    def store(self, t, A):
        if A is ALL:
            return A
        if isinstance(t, ast.Name):
            return A | {t.id}
        if isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                A = self.store(e, A)
            return A
        if isinstance(t, ast.Starred):
            return self.store(t.value, A)
        if isinstance(t, ast.Attribute):
            return self.expr(t.value, A)
        if isinstance(t, ast.Subscript):
            return self.expr(t.slice, self.expr(t.value, A))
        return self.expr(t, A)

    # ---- statements
    def block(self, stmts, A):
        for s in stmts:
            if A is ALL:
                return ALL
            A = self.stmt(s, A)
        return A

    def quiet_block(self, stmts, A):
        self.quiet += 1
        try:
            return self.block(stmts, A)
        finally:
            self.quiet -= 1

    @staticmethod
    def _dels(nodes):
        out = set()
        for part in nodes:
            for n in ast.walk(part):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del):
                    out.add(n.id)
        return out

    def stmt(self, s, A):
        t = type(s)
        if t is ast.Assign:
            A = self.expr(s.value, A)
            for tg in s.targets:
                A = self.store(tg, A)
            return A
        if t is ast.AnnAssign:
            if s.value is None:
                return A
            A = self.expr(s.value, A)
            return self.store(s.target, A)
        if t is ast.AugAssign:
            if isinstance(s.target, ast.Name):
                if s.target.id in self.tracked and s.target.id not in A and not self.quiet:
                    self.res.bad_aug.append(s)
                A = self.expr(s.value, A)
                return A | {s.target.id}
            A = self.expr(s.target, A)
            return self.expr(s.value, A)
        if t is ast.Delete:
            for tg in s.targets:
                if isinstance(tg, ast.Name):
                    if tg.id in self.tracked and tg.id not in A and not self.quiet:
                        self.res.bad.append(tg)
                    A = A - {tg.id}
                else:
                    A = self.expr(tg, A)
            return A
        if t is ast.If:
            A1 = self.expr(s.test, A)
            return _inter(self.block(s.body, A1), self.block(s.orelse, A1))
        if t is ast.While:
            return self.loop(s, A, None)
        if t in (ast.For, ast.AsyncFor):
            return self.loop(s, A, s.target)
        if t in (ast.Return, ast.Raise):
            for c in ast.iter_child_nodes(s):
                A = self.expr(c, A)
            return ALL
        if t is ast.Break:
            if self.loops:
                self.loops[-1].append(A)
            return ALL
        if t is ast.Continue:
            return ALL
        if t in (ast.Try, getattr(ast, 'TryStar', ast.Try)):
            return self.try_(s, A)
        if t in (ast.With, ast.AsyncWith):
            return self.with_(s, A)
        if t is ast.Match:
            return self.match(s, A)
        if t in (ast.FunctionDef, ast.AsyncFunctionDef):
            for d in s.decorator_list + s.args.defaults + [d for d in s.args.kw_defaults if d is not None]:
                A = self.expr(d, A)
            self.captures.append((s, A))
            return A
        if t is ast.ClassDef:
            for d in s.decorator_list + s.bases + [k.value for k in s.keywords]:
                A = self.expr(d, A)
            self.captures.append((s, A))
            return A
        for c in ast.iter_child_nodes(s):
            if isinstance(c, ast.expr):
                A = self.expr(c, A)
        if t is ast.Expr and _is_exit(s.value):
            return ALL
        if t is ast.Assert and isinstance(s.test, ast.Constant) and not s.test.value:
            return ALL
        return A

    def loop(self, s, A, target):
        if target is not None:
            A = self.expr(s.iter, A)
        head = A - self._dels(s.body + s.orelse + ([s.test] if target is None else []))
        if target is None:
            after_test = self.expr(s.test, head)
            infinite = isinstance(s.test, ast.Constant) and bool(s.test.value)
            start = after_test
        else:
            start = self.store(target, head)
            after_test = head
            infinite = False
        breaks = []
        self.loops.append(breaks)
        try:
            self.block(s.body, start)
        finally:
            self.loops.pop()
        normal = ALL if infinite else after_test
        if normal is not ALL and s.orelse:
            normal = self.block(s.orelse, normal)
        out = normal
        for b in breaks:
            out = _inter(out, b)
        return out

    def try_(self, s, A):
        entry = A - self._dels(s.body)
        body = self.block(s.body, A)
        if body is not ALL and s.orelse:
            body = self.block(s.orelse, body)
        normal = body
        hentry = A - self._dels(s.body)
        for h in s.handlers:
            ha = self.expr(h.type, hentry) if h.type is not None else hentry
            normal = _inter(normal, self.block(h.body, ha))
        if s.finalbody:
            weakest = A - self._dels([s])
            fin_entry = _inter(normal, weakest) if normal is not ALL else weakest
            self.block(s.finalbody, fin_entry)
            if normal is ALL:
                return ALL
            return self.quiet_block(s.finalbody, normal)
        return normal

    def with_(self, s, A):
        for item in s.items:
            A = self.expr(item.context_expr, A)
            if item.optional_vars is not None:
                A = self.store(item.optional_vars, A)
        body = self.block(s.body, A)
        swallow = not all(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name)
                          and i.context_expr.func.id == 'open' for i in s.items)
        if swallow:
            return _inter(body, A - self._dels(s.body))
        return body

    def match(self, s, A):
        A1 = self.expr(s.subject, A)
        out = ALL
        total = False
        for case in s.cases:
            entry = A1 | set(_pattern_names(case.pattern))
            for n in ast.walk(case.pattern):
                if isinstance(n, ast.MatchValue):
                    self.expr(n.value, A1)
                elif isinstance(n, ast.MatchClass):
                    self.expr(n.cls, A1)
            if case.guard is not None:
                self.expr(case.guard, entry)
            out = _inter(out, self.block(case.body, entry))
            if case.guard is None and _irrefutable(case.pattern):
                total = True
        if not total:
            out = _inter(out, A1)
        return out


def _is_exit(call):
    """`sys.exit(...)`, `exit(...)` or `quit(...)`: the statement does not complete."""
    if not isinstance(call, ast.Call):
        return False
    f = call.func
    return ((isinstance(f, ast.Attribute) and f.attr == 'exit' and isinstance(f.value, ast.Name) and f.value.id == 'sys')
            or (isinstance(f, ast.Name) and f.id in ('exit', 'quit')))


def _irrefutable(p):
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or _irrefutable(p.pattern)
    if isinstance(p, ast.MatchOr):
        return any(_irrefutable(q) for q in p.patterns)
    return False


def analyze(fn):
    """The possibly-unassigned reads of function `fn` (an ast.FunctionDef), or None when it is left alone."""
    own = _own_nodes(fn)
    if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in own) or isinstance(fn, ast.AsyncFunctionDef):
        return None
    flow = _Flow(fn)
    res = flow.res
    res.script = fn.name in SCRIPT
    dynamic = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id in ('locals', 'vars', 'eval', 'exec') for n in own)
    flow.block(fn.body, set(flow.params) | (set(flow.nested) | {n.name for n in own if isinstance(n, ast.ClassDef)}))
    # nested scopes that read tracked locals of this function
    for scope, A in flow.captures:
        if A is ALL:
            continue
        for name in _captured_loads(scope) & flow.tracked:
            if name in A and name not in flow.deleted:
                continue
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and name not in flow.deleted:
                refs = flow.refs.get(scope.name, [])
                if (scope.name not in flow.escaped and refs and all(r is ALL or name in r for r in refs)):
                    continue
            res.refusal = ('%r is read by a nested %s before this function has assigned it (CPython: NameError, '
                           'free variable)' % (name, 'def' if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
                                                else 'lambda' if isinstance(scope, ast.Lambda) else 'class body'))
            return res
    res.flagged = {n.id for n in res.bad} | {s.target.id for s in res.bad_aug}
    if res.flagged and dynamic:
        res.refusal = 'locals()/vars()/eval/exec in a function with a possibly-unassigned local'
    if res.flagged:
        for n in flow.own:
            if isinstance(n, ast.NamedExpr) and n.target.id in res.flagged:
                res.refusal = '%r may be unassigned and is bound by a walrus' % n.target.id
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del) and n.id in res.flagged:
                res.refusal = '%r may be unassigned and is deleted' % n.id
            elif isinstance(n, ast.AsyncFor):
                res.refusal = 'async for'
    return res


def functions(tree):
    """Every def of the module, methods and nested ones included, outermost first."""
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def census(tree):
    """{function name: sorted names that need a flag} for the functions of `tree` that need one (a refusal counts)."""
    out = {}
    for fn in functions(tree):
        res = analyze(fn)
        if res is not None and (res.flagged or res.refusal):
            out[fn.name] = sorted(res.flagged) if not res.refusal else ['!' + res.refusal]
    return out


# ---- the rewrite --------------------------------------------------------------------------------------------

class _Rewrite(ast.NodeTransformer):
    def __init__(self, fn, res):
        self.fn = fn
        self.res = res
        self.bad = {id(n) for n in res.bad}
        self.bad_aug = {id(s) for s in res.bad_aug}
        self.flagged = res.flagged

    def flag_set(self, names, at, value=True):
        out = []
        for name in sorted(names):
            if name in self.flagged:
                node = ast.Assign(targets=[ast.Name(id=FLAG + name, ctx=ast.Store())],
                                  value=ast.Constant(value=value))
                ast.copy_location(node, at)
                out.append(node)
        return out

    def check_stmt(self, name, at):
        node = ast.Expr(value=ast.Call(func=ast.Name(id=self.res.helper + name, ctx=ast.Load()), args=[], keywords=[]))
        test = ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=FLAG + name, ctx=ast.Load()))
        node = ast.If(test=test, body=[node], orelse=[])
        for n in ast.walk(node):
            ast.copy_location(n, at)
        return node

    def visit_FunctionDef(self, node):
        # a nested def is its own scope (it is refused above when it reads a name that needs a flag); what is
        # evaluated here, at its definition, is its decorators and defaults
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        return node

    def visit_ClassDef(self, node):
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(d) for d in node.bases]
        for k in node.keywords:
            k.value = self.visit(k.value)
        return node

    def body(self, stmts):
        out = []
        for s in stmts:
            r = self.visit(s)
            if isinstance(r, list):
                out.extend(r)
            else:
                out.append(r)
        return out

    def _chain_root(self, node):
        """The Name a pure attribute chain (r.a.b) starts from when that read is flagged, else None."""
        while isinstance(node, ast.Attribute):
            node = node.value
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) in self.bad:
            return node
        return None

    def _guarded(self, node, root):
        """node with its flagged root read checked first. A class value cannot be a conditional expression, so the
        whole attribute read (or method call) is the conditional and the checked root stays a plain name."""
        name = root.id
        test = ast.BoolOp(op=ast.Or(), values=[
            ast.Name(id=FLAG + name, ctx=ast.Load()),
            ast.Call(func=ast.Name(id=self.res.helper + name, ctx=ast.Load()), args=[], keywords=[])])
        self.bad.discard(id(root))
        plain = copy.deepcopy(node)
        new = ast.IfExp(test=test, body=node, orelse=plain)
        for n in ast.walk(new):
            ast.copy_location(n, root)
        return new

    def visit_Attribute(self, node):
        root = self._chain_root(node)
        if root is not None and isinstance(node.ctx, ast.Load):
            return self._guarded(node, root)
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            root = self._chain_root(node.func)
            if root is not None:
                node.args = [self.visit(a) for a in node.args]
                node.keywords = [self.visit(k) for k in node.keywords]
                return self._guarded(node, root)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if id(node) in self.bad and isinstance(node.ctx, ast.Load):
            name = node.id
            test = ast.BoolOp(op=ast.Or(), values=[
                ast.Name(id=FLAG + name, ctx=ast.Load()),
                ast.Call(func=ast.Name(id=self.res.helper + name, ctx=ast.Load()), args=[], keywords=[])])
            new = ast.IfExp(test=test, body=ast.Name(id=name, ctx=ast.Load()), orelse=ast.Name(id=name, ctx=ast.Load()))
            for n in ast.walk(new):
                ast.copy_location(n, node)
            return new
        return node

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        node.targets = [self.visit(t) for t in node.targets]
        names = {n for t in node.targets for n in _target_names(t)}
        return [node] + self.flag_set(names, node)

    def visit_AnnAssign(self, node):
        if node.value is None:
            return node
        node.value = self.visit(node.value)
        node.target = self.visit(node.target)
        return [node] + self.flag_set(set(_target_names(node.target)), node)

    def visit_AugAssign(self, node):
        pre = []
        if id(node) in self.bad_aug:
            pre = [self.check_stmt(node.target.id, node)]
        node.value = self.visit(node.value)
        node.target = self.visit(node.target) if not isinstance(node.target, ast.Name) else node.target
        post = self.flag_set(set(_target_names(node.target)), node) if isinstance(node.target, ast.Name) else []
        return pre + [node] + post

    def visit_For(self, node):
        node.iter = self.visit(node.iter)
        node.target = self.visit(node.target)
        node.body = self.flag_set(set(_target_names(node.target)), node) + self.body(node.body)
        node.orelse = self.body(node.orelse)
        return node

    def visit_With(self, node):
        names = set()
        for item in node.items:
            item.context_expr = self.visit(item.context_expr)
            if item.optional_vars is not None:
                names.update(_target_names(item.optional_vars))
        node.body = self.flag_set(names, node) + self.body(node.body)
        return node

    def visit_Match(self, node):
        node.subject = self.visit(node.subject)
        for case in node.cases:
            if case.guard is not None:
                case.guard = self.visit(case.guard)
            case.body = self.flag_set(set(_pattern_names(case.pattern)), node) + self.body(case.body)
        return node

    def visit_If(self, node):
        node.test = self.visit(node.test)
        node.body = self.body(node.body)
        node.orelse = self.body(node.orelse)
        return node

    def visit_While(self, node):
        node.test = self.visit(node.test)
        node.body = self.body(node.body)
        node.orelse = self.body(node.orelse)
        return node

    def visit_Try(self, node):
        node.body = self.body(node.body)
        for h in node.handlers:
            if h.type is not None:
                h.type = self.visit(h.type)
            h.body = self.body(h.body)
        node.orelse = self.body(node.orelse)
        node.finalbody = self.body(node.finalbody)
        return node


def _helper_def(name, script):
    if script:
        src = ('def %s%s() -> bool:\n    raise NameError(%r)\n    return False\n'
               % (SCRIPT_HELPER, name, SCRIPT_MESSAGE % name))
    else:
        src = ('def %s%s() -> bool:\n    raise UnboundLocalError(%r)\n    return False\n'
               % (HELPER, name, MESSAGE % name))
    return ast.parse(src).body[0]


def _reachable(tree, entry):
    """Names of the module's functions reachable from `entry` through plain calls (everything when entry is None)."""
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if entry is None or entry not in fns:
        return set(fns)
    seen, todo = set(), [entry]
    while todo:
        name = todo.pop()
        if name in seen or name not in fns:
            continue
        seen.add(name)
        for n in ast.walk(fns[name]):
            if isinstance(n, ast.Name) and n.id in fns and n.id not in seen:
                todo.append(n.id)
    return seen


def _owner_names(tree):
    """{id(def): name of the top-level def it sits in} for every def (a method: None, which counts as reachable)."""
    out = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.ClassDef)):
            for n in ast.walk(top):
                if isinstance(n, ast.FunctionDef):
                    out[id(n)] = top.name if isinstance(top, ast.FunctionDef) else None
    return out


def rewrite(tree, Unsupported, entry=None, info=None, library=False):
    """Make every possibly-unassigned local read raise (see the module docstring).  Returns the number of functions
    that needed flags; the tree of a program without any is not touched."""
    work = []
    for fn in functions(tree):
        res = analyze(fn)
        if res is not None and (res.flagged or res.refusal):
            work.append((fn, res))
    if not work:
        return 0
    mixed = bool(info and info.get('_mixed_clone'))
    if mixed:
        reach = _reachable(tree, entry)
        owner = _owner_names(tree)
        work = [(fn, res) for fn, res in work if owner.get(id(fn)) in reach or owner.get(id(fn)) is None]
        if not work:
            return 0
    for fn, res in work:
        if res.refusal:
            raise Unsupported('%s: %s' % (fn.name, res.refusal))
    if not work:
        return 0
    if mixed:
        raise Unsupported('%s: a local may be read before it is assigned (a typed clone cannot raise '
                          'UnboundLocalError into boxed code)' % work[0][0].name)
    if library:
        raise Unsupported('%s: a local may be read before it is assigned; a separately compiled module cannot carry '
                          'the UnboundLocalError it needs -- assign it first' % work[0][0].name)
    names = set()
    for fn, res in work:
        names |= {(name, res.script) for name in res.flagged}
    return _apply(tree, work, names, info)


def _inits(fn, res):
    out = []
    for name in sorted(res.flagged):
        node = ast.Assign(targets=[ast.Name(id=FLAG + name, ctx=ast.Store())], value=ast.Constant(value=False))
        ast.copy_location(node, fn)
        out.append(node)
    return out


def _apply(tree, work, names, info):
    for fn, res in work:
        rw = _Rewrite(fn, res)
        body = rw.body(fn.body)
        head = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            head = 1
        fn.body = body[:head] + _inits(fn, res) + body[head:]
    declared = {n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    add = []
    if 'NameError' not in declared:
        add.append(ast.parse('class NameError(Exception):\n    pass\n').body[0])
    if 'UnboundLocalError' not in declared and any(not script for _, script in names):
        add.append(ast.parse('class UnboundLocalError(NameError):\n    pass\n').body[0])
    for name, script in sorted(names):
        if (SCRIPT_HELPER if script else HELPER) + name not in declared:
            add.append(_helper_def(name, script))
    tree.body[0:0] = add
    ast.fix_missing_locations(tree)
    if info is not None:
        info['unbound_flags'] = {fn.name: sorted(res.flagged) for fn, res in work}
    return len(work)


if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        found = census(ast.parse(open(path, encoding='utf-8').read()))
        for name, names in sorted(found.items()):
            print('%s: %s: %s' % (path, name, ', '.join(names)))
