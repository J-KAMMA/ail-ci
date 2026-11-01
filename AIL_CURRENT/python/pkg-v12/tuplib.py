"""Tuples in the Python syntax, lowered onto what the compiler already builds.

`return a, b`, `q, r = f(x)`, `divmod`, tuple-typed locals and parameters, `t[0]`, `for i, (a, b) in
enumerate(pairs)`, `list[tuple[int, int]]`, tuple comparison and printing, `dict[tuple[int, int], int]`,
`set[tuple[int, int]]`, `heappush(h, (d, v))`, `sorted(xs, key=lambda t: (t[1], -t[0]))`.

A tuple type is a class `_AilT_<codes>` with fields f0, f1, ... (tuplegen.py), a tuple expression a constructor
call, `t[k]` a field read, an unpack a few field reads.  A dict or set that mentions a tuple becomes an
insertion-ordered open-addressing table class (tuplegen.Table: plain Python-syntax source compiled by the
ordinary typed path).  Tuples are immutable, so sharing the instance is CPython's behaviour too.  The C runtime
gets nothing new.  A program whose tuple uses are all ones the compiler already builds (literal swaps, sort-key
tuples, `%` operands, lists of numeric tuples) is returned as written, byte for byte.

Anything not built is refused by name: the source is left as written and the reason goes to `notes`.

The pass runs twice over a program: the first run (output discarded) settles what a later statement tells
about an earlier empty `[]` / `{}` and the return types of unannotated functions; the second run emits.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from tupcommon import *  # noqa: E402,F401,F403
from tupexpr import Exprs  # noqa: E402
from tupcalls import Calls  # noqa: E402
from tupstmt import Stmts  # noqa: E402
from tuplam import Lams  # noqa: E402

CANDIDATE_NAMES = {'tuple', 'Tuple', 'modf', 'divmod', 'zip', 'partition', 'rpartition', 'heappush', 'heappop'}


def candidate(tree):
    """Cheap test: could this program use anything this pass lowers?"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and isinstance(node.ctx, ast.Load):
            return True
        if isinstance(node, ast.Name) and node.id in CANDIDATE_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in CANDIDATE_NAMES:
            return True
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            return True
        if isinstance(node, ast.Lambda):
            return True
    return False


class Lower(Stmts, Calls, Lams, Exprs):
    def __init__(self, source, hints=None, rets=None):
        self.source = source
        self.tree = ast.parse(source)
        self.gen = G.Gen()
        self.hints = {} if hints is None else hints
        self.rets_in = {} if rets is None else rets
        self.rets_out = {}
        self.forced = False
        self.quiet = 0
        self.nohoist = 0
        self.fresh_names = set()
        self.errors = []
        self.counter = 0
        self.names = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)} | {
            n.arg for n in ast.walk(self.tree) if isinstance(n, ast.arg)}
        self.classes = {}
        self.ctor_fields = {}
        self.methods = {}
        self.funcs = {}
        self.sigs = {}
        self.consts = {}
        self.rowconst = {}
        self.tupconst = {}
        self.modalias = {}
        self.fromnames = {}
        self.env = {}
        self.alias = {}
        self.pre = []
        self.pending = []
        self.rets = []
        self.cur = None
        self.fnkey = '<module>'
        self.lam_alias = {}
        self.lamdefs = []
        self.lam_counter = 0
        self.specs = {}
        self.pristine = {}
        self.binds = {}

    # ------------------------------------------------------------------------------------------
    def collect(self):
        tree = self.tree
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.classes[node.name] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in ('heapq', 'math', 'sys', 'functools', 'bisect'):
                        self.modalias[a.asname or a.name] = a.name
            elif isinstance(node, ast.ImportFrom) and node.module in ('heapq', 'math', 'functools', 'bisect'):
                for a in node.names:
                    self.fromnames[a.asname or a.name] = (node.module, a.name)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.pristine[node.name] = fresh_copy(node)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.collect_class(node)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = self.make_sig(node, None)

    def make_sig(self, fn, owner):
        sig = Sig(fn, owner)
        args = fn.args
        plain = [*args.posonlyargs, *args.args]
        ndef = len(args.defaults)
        for i, a in enumerate(plain):
            if owner and i == 0:
                t = ('cls', owner)
            else:
                try:
                    t = self.sig_ann(a.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                    t = None
            sig.params.append((a.arg, t, i >= len(plain) - ndef))
        for a, dflt in zip(args.kwonlyargs, args.kw_defaults):
            try:
                t = self.ann(a.annotation)
            except Refused as exc:
                self.errors.append(exc.args[0])
                t = None
            sig.params.append((a.arg, t, dflt is not None))
        try:
            sig.ret = self.sig_ann(fn.returns) if fn.returns is not None else None
        except Refused as exc:
            self.errors.append(exc.args[0])
        key = (owner or '') + '.' + fn.name
        if fn.returns is None and key in self.rets_in:
            sig.ret = self.rets_in[key]
        self.sigs[id(fn)] = sig
        return sig

    def collect_class(self, node):
        name = node.name
        fields = self.classes[name]
        dataclass = any((isinstance(d, ast.Name) and d.id == 'dataclass') or
                        (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'dataclass')
                        or (isinstance(d, ast.Attribute) and d.attr == 'dataclass') for d in node.decorator_list)
        order = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                try:
                    fields[item.target.id] = self.ann(item.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                order.append((item.target.id, fields.get(item.target.id)))
        init = next((i for i in node.body if isinstance(i, ast.FunctionDef) and i.name == '__init__'), None)
        if init is not None:
            sig = self.make_sig(init, name)
            self.methods[(name, '__init__')] = sig
            params = {p[0]: p[1] for p in sig.params}
            self.ctor_fields[name] = [(p[0], p[1]) for p in sig.params[1:]]
            for sub in ast.walk(init):
                if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Attribute) \
                        and isinstance(sub.targets[0].value, ast.Name) and sub.targets[0].value.id == 'self':
                    v = sub.value
                    fields.setdefault(sub.targets[0].attr, params.get(v.id) if isinstance(v, ast.Name) else None)
                elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute):
                    try:
                        fields[sub.target.attr] = self.ann(sub.annotation)
                    except Refused:
                        pass
        elif dataclass or order:
            self.ctor_fields[name] = order
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name != '__init__':
                self.methods[(name, item.name)] = self.make_sig(item, name)

    # ------------------------------------------------------------------------------------------
    def function(self, fn, owner=None):
        sig = self.sigs[id(fn)]
        self.cur = sig
        self.fnkey = (owner or '') + '.' + fn.name
        self.env = {}
        self.alias = {}
        self.lam_alias = {}
        self.closure_reads = self.nested_scope_reads(fn)
        self.scan_binds(fn)
        self.rets = []
        self.pending = []
        args = fn.args
        plain = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        for a, p in zip(plain, sig.params):
            if a.annotation is not None:
                try:
                    a.annotation, t = self.sig_map_ann(a.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                    continue
                if is_tuple(t) or is_table(t) or (isinstance(t, tuple) and t[0] == 'opt' and has_tuple(t)):
                    self.force()
            self.env[a.arg] = p[1]
        try:
            args.defaults = [self.exv(d, p[1])[0] for d, p in zip(
                args.defaults, sig.params[len(args.posonlyargs) + len(args.args) - len(args.defaults):])]
        except Refused as exc:
            self.errors.append(exc.args[0])
        if fn.returns is not None:
            try:
                fn.returns, rt = self.sig_map_ann(fn.returns)
                if is_tuple(rt) or is_table(rt) or (isinstance(rt, tuple) and rt[0] == 'opt' and has_tuple(rt)):
                    self.force()
            except Refused as exc:
                self.errors.append(exc.args[0])
        fn.body = self.stmts(fn.body)
        if fn.returns is None:
            seen = [t for t in self.rets if t not in (None, 'none')]
            if seen and all(known(t) for t in seen) and len({code(t) for t in seen}) == 1 and has_tuple(seen[0]):
                self.rets_out[self.fnkey] = seen[0]
                if self.fnkey in self.rets_in:
                    self.use_type(seen[0])
                    fn.returns = ast.parse(ann_text(seen[0]), mode='eval').body
                    self.force()
        for key, t in self.pending:
            dt = deep(t)
            if dt is not None and known(dt):
                self.hints[key] = dt
        self.cur = None

    def class_(self, node):
        name = node.name
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                try:
                    item.annotation, t = self.map_ann(item.annotation)
                    if has_tuple(t):
                        self.force()
                    if item.value is not None:
                        item.value = self.exv(item.value, t, 'row')[0]
                except Refused as exc:
                    self.errors.append(exc.args[0])
            elif isinstance(item, ast.FunctionDef):
                self.function(item, name)

    def module_stmt(self, node):
        """Module-level statements other than def / class."""
        if isinstance(node, ast.ImportFrom) and node.module == 'functools' and all(
                a.name == 'reduce' for a in node.names):
            return []
        if isinstance(node, ast.Import) and all(a.name == 'functools' for a in node.names):
            return []
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return [node]
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return self.module_assign(node)
        self.cur = None
        self.fnkey = '<module>'
        self.env = {}
        self.alias = {}
        return self.stmts([node])

    def module_assign(self, node):
        nm = node.targets[0].id
        v = node.value
        cols = None
        if isinstance(v, ast.List) and v.elts and all(isinstance(e, ast.Tuple) for e in v.elts):
            cols = [e.elts for e in v.elts]
        elif isinstance(v, ast.Tuple) and v.elts:
            cols = [v.elts]
        if cols is not None:
            arity = len(cols[0])
            ok = all(len(c) == arity for c in cols) and arity >= 1
            types = []
            if ok:
                for i in range(arity):
                    ts = set()
                    for c in cols:
                        e = c[i]
                        k = e.operand if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)) else e
                        if isinstance(k, ast.Constant) and type(k.value) in (int, float):
                            ts.add(type(k.value))
                        else:
                            ok = False
                    if ok and len(ts) != 1:
                        ok = False
                    if ok:
                        types.append(INT if ts == {int} else FLT)
            if not ok:
                self.errors.append((node.lineno, 'a module-level tuple constant must be numbers only, one type per '
                                    'position (DIRS = [(0, 1), (1, 0)]); build other tuples inside a function'))
                return [node]
            if isinstance(v, ast.List) and not (rowconst_in_place(self.tree, nm)
                                                and rowconst_module_in_place(self.tree, nm, node)):
                # kept as columns, the list is rebuilt wherever it is used as a value: a function that
                # changes it, or a name bound to it, would change a copy (DIFFERENCES C68); a module-level
                # del / item store / mutating call would drop the change the same way
                self.errors.append((node.lineno, 'the module-level list %s is used in a way that is not an '
                                    'in-place read (passed, bound, returned or mutated); a list of number tuples '
                                    'is built here only when it is read in place (for, %s[i], len(%s)); build it '
                                    'in main() and pass it down' % (nm, nm, nm)))
                return [node]
            t = ('tuple', tuple(types))
            self.force()
            self.use_type(t)
            out = []
            for i in range(arity):
                col = ast.List(elts=[c[i] for c in cols], ctx=ast.Load()) if isinstance(v, ast.List) else c[i]
                out.append(ast.Assign(targets=[ast.Name(id='%s__c%d' % (nm, i), ctx=ast.Store())], value=col,
                                      lineno=node.lineno))
            if isinstance(v, ast.List):
                self.rowconst[nm] = t
                self.consts[nm] = ('list', t)
                self.gen.rowconst(nm, t)
            else:
                self.tupconst[nm] = t
                self.consts[nm] = t
            return out
        self.cur = None
        self.fnkey = '<module>'
        self.env = {}
        t = self.typeof(v)
        if t is not None and has_tuple(t):
            self.errors.append((node.lineno, 'a module-level constant holding tuples must be a literal list of '
                                'number tuples (DIRS = [(0, 1), (1, 0)]); build other tuples inside a function'))
        elif t is None and any(isinstance(n, ast.Tuple) for n in ast.walk(v)):
            # The type could not be told and the value mentions a tuple, so another use of that tuple (for
            # example a frozenset of tuples as a dict key, whose table the pass refuses) may have been lowered
            # to a tuple class while this constant stayed a plain object. Leave the whole program as written.
            self.errors.append((node.lineno, 'a module-level constant whose type cannot be told and that holds a '
                                'tuple is not built; build it inside a function'))
        self.consts[nm] = t
        return [node]

    def process(self):
        self.collect()
        body = []
        for node in self.tree.body:
            try:
                if isinstance(node, ast.FunctionDef):
                    self.function(node)
                    body.append(node)
                elif isinstance(node, ast.ClassDef):
                    self.class_(node)
                    body.append(node)
                else:
                    body.extend(self.module_stmt(node))
            except Refused as exc:
                self.errors.append(exc.args[0])
                body.append(node)
        while self.lamdefs:
            node = self.lamdefs.pop(0)
            try:
                self.function(node)
            except Refused as exc:
                self.errors.append(exc.args[0])
            body.append(node)
        self.tree.body = body

    def text(self):
        ast.fix_missing_locations(self.tree)
        out = ast.unparse(self.tree)
        helpers = self.gen.source()
        return out.rstrip('\n') + ('\n\n\n' + helpers if helpers else '') + '\n'


_ISINSTANCE_TYPE_NAMES = frozenset((
    'int', 'float', 'str', 'bool', 'bytes', 'bytearray', 'list', 'tuple', 'dict',
    'set', 'frozenset', 'range', 'object'))

# The builtin exception classes an isinstance() type tuple may name (the names pyboxed2.EXC_IDS
# knows; a user exception class is in `defs` below).
_ISINSTANCE_EXC_NAMES = frozenset((
    'Exception', 'TypeError', 'ValueError', 'ZeroDivisionError', 'IndexError', 'KeyError',
    'AttributeError', 'StopIteration', 'NameError', 'OverflowError', 'UnboundLocalError',
    'RuntimeError', 'AssertionError', 'NotImplementedError', 'EOFError', 'OSError',
    'ConnectionError', 'BlockingIOError', 'ChildProcessError', 'BrokenPipeError',
    'ConnectionAbortedError', 'ConnectionRefusedError', 'ConnectionResetError',
    'FileExistsError', 'FileNotFoundError', 'InterruptedError', 'IsADirectoryError',
    'NotADirectoryError', 'PermissionError', 'ProcessLookupError', 'TimeoutError'))

_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _collect_bindings(node, binds, globals_, nonlocals_, root=False):
    """Every name bound in one lexical scope, not descending into a nested scope.

    `root` is the node whose own binding must not count: a function's name binds in the enclosing
    scope, and a comprehension's target binds in the comprehension, not the containing function.
    """
    if not root:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            binds.add(node.name)
            return
        if isinstance(node, ast.ClassDef):
            binds.add(node.name)
            return
        if isinstance(node, ast.Lambda) or isinstance(node, _COMPREHENSIONS):
            return
    if isinstance(node, ast.Global):
        globals_.update(node.names)
        return
    if isinstance(node, ast.Nonlocal):
        nonlocals_.update(node.names)
        return
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        binds.add(node.id)
    elif isinstance(node, _FUNCS):
        args = node.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
            if arg is not None:
                binds.add(arg.arg)
    elif isinstance(node, ast.alias):
        binds.add(node.asname or node.name.split('.')[0])
    elif isinstance(node, ast.ExceptHandler) and node.name:
        binds.add(node.name)
    elif isinstance(node, ast.MatchAs) and node.name:
        binds.add(node.name)
    elif isinstance(node, ast.MatchStar) and node.name:
        binds.add(node.name)
    elif isinstance(node, ast.MatchMapping) and node.rest:
        binds.add(node.rest)
    for child in ast.iter_child_nodes(node):
        _collect_bindings(child, binds, globals_, nonlocals_, False)


def _scope(kind, node, root=False):
    binds, globals_, nonlocals_ = set(), set(), set()
    _collect_bindings(node, binds, globals_, nonlocals_, root)
    return (kind, binds - globals_ - nonlocals_, globals_, nonlocals_)


def _module_bindings(tree):
    """The binding nodes of each name in module scope (not inside a def, class or comprehension)."""
    out = {}

    def add(name, node):
        out.setdefault(name, []).append(node)

    def walk(node, root=False):
        if not root:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node.name, node)
                return
            if isinstance(node, ast.ClassDef):
                add(node.name, node)
                return
            if isinstance(node, ast.Lambda) or isinstance(node, _COMPREHENSIONS):
                return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            add(node.id, node)
        elif isinstance(node, ast.alias):
            add(node.asname or node.name.split('.')[0], node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            add(node.name, node)
        elif isinstance(node, ast.MatchAs) and node.name:
            add(node.name, node)
        elif isinstance(node, ast.MatchStar) and node.name:
            add(node.name, node)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            add(node.rest, node)
        for child in ast.iter_child_nodes(node):
            walk(child, False)

    walk(tree, True)
    return out


def _shadowed(name, chain):
    """Whether `name` in this scope chain denotes anything but the module binding."""
    crossed_function = False
    for kind, binds, globals_, nonlocals_ in reversed(chain):
        if kind == 'module':
            return False
        if kind == 'comp':
            if name in binds:
                return True
        elif kind == 'function':
            if name in globals_:
                return False
            if name in nonlocals_ or name in binds:
                return True
            crossed_function = True
        elif kind == 'class' and not crossed_function and name in binds:
            return True
    return False


def _isinstance_uses(tree):
    """Every isinstance() call with the scope chain and top-level statement index of its use."""
    uses = []

    def walk(node, chain, top_index):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'isinstance' and len(node.args) == 2 and not node.keywords):
            uses.append((node, chain, top_index))
        if isinstance(node, _FUNCS):
            inner = chain + [_scope('function', node, True)]
        elif isinstance(node, ast.ClassDef):
            inner = chain + [_scope('class', node, True)]
        elif isinstance(node, _COMPREHENSIONS):
            binds = set()
            for gen in node.generators:
                _collect_bindings(gen.target, binds, set(), set(), False)
            inner = chain + [('comp', binds, set(), set())]
        else:
            inner = chain
        for child in ast.iter_child_nodes(node):
            walk(child, inner, top_index)

    module = ('module', set(), set(), set())
    for index, stmt in enumerate(tree.body):
        walk(stmt, [module], index)
    return uses


def _module_reads(tree):
    """The (node, scope chain) of every name read in the program (a read of a module binding is one
    whose chain does not shadow the name)."""
    reads = {}

    def walk(node, chain):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            reads.setdefault(node.id, []).append((node, chain))
        if isinstance(node, _FUNCS):
            inner = chain + [_scope('function', node, True)]
        elif isinstance(node, ast.ClassDef):
            inner = chain + [_scope('class', node, True)]
        elif isinstance(node, _COMPREHENSIONS):
            binds = set()
            for gen in node.generators:
                _collect_bindings(gen.target, binds, set(), set(), False)
            inner = chain + [('comp', binds, set(), set())]
        else:
            inner = chain
        for child in ast.iter_child_nodes(node):
            walk(child, inner)

    walk(tree, [('module', set(), set(), set())])
    return reads


def _expand_isinstance_type_constants(tree):
    """Replace a module-level constant used as isinstance()'s second argument with its value.

    `TYPES = (int, str)` is a tuple of type objects, not a tuple the lowering can build (its
    elements are not numbers), and `K = SomeClass` is a plain alias.  Both are common in a
    program that tests against a set of types.  Expanding the use before the tuple pass keeps
    the constant from being mistaken for a numeric tuple, and leaves the ordinary type names
    for the typed and general paths to compile.  A type-tuple or alias assignment is dropped
    when no other read of the name remains; other module assignments are left untouched.

    The value CPython captured at the assignment is what the use must see, not a re-read of the
    expression at the use.  When every name in the value is a builtin type or a class bound once
    before the assignment, the names can be written at the use directly (the typed path then
    settles them).  Otherwise the value is snapshotted into fresh module names at the assignment
    (`T = (A,)` before `A = B`, `T = box.t` before `box.t` changes, or a forward reference that
    must raise NameError), and the use reads those names: the general path keeps CPython's value
    and its NameError.

    An expansion only replaces a use where the name really denotes that module constant, not
    where a parameter, local, comprehension target or class-body binding shadows it.  Every other
    use keeps the name, so the runtime path sees the value CPython sees (or its NameError).
    """
    defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    if 'isinstance' in defs:
        return False
    candidates = {}
    for index, stmt in enumerate(tree.body):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name, target, value = stmt.targets[0].id, stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            name, target, value = stmt.target.id, stmt.target, stmt.value
        else:
            continue
        candidates.setdefault(name, []).append((index, target, value))
    bindings = _module_bindings(tree)
    binding_positions = {}
    for index, stmt in enumerate(tree.body):
        one = ast.Module(body=[stmt], type_ignores=[])
        for name, nodes in _module_bindings(one).items():
            for node in nodes:
                binding_positions.setdefault(name, []).append((index, node))
    forbidden = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            forbidden.update(node.names)
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            forbidden.add(node.target.id)
    constants, where = {}, {}
    for name, found in candidates.items():
        if len(found) != 1 or name in forbidden:
            continue
        index, target, value = found[0]
        if bindings.get(name) != [target]:
            continue
        constants[name] = value
        where[name] = index

    def is_type(node, seen):
        if isinstance(node, ast.Name):
            if (node.id in _ISINSTANCE_TYPE_NAMES or node.id in _ISINSTANCE_EXC_NAMES
                    or node.id in defs):
                return True
            if node.id in constants and node.id not in seen:
                return is_type(constants[node.id], seen | {node.id})
            return False
        if isinstance(node, ast.Attribute):
            return True
        if isinstance(node, ast.Tuple):
            return bool(node.elts) and all(is_type(e, seen) for e in node.elts)
        return False

    module_allowed = {name for name, value in constants.items() if is_type(value, frozenset())}

    def expand_value(node, seen):
        # Resolve inside a module constant with module scope, whatever a local at the use means.
        if isinstance(node, ast.Tuple):
            out = []
            for e in node.elts:
                out.extend(expand_value(e, seen))
            return out
        if isinstance(node, ast.Name) and node.id in module_allowed and node.id not in seen:
            return expand_value(constants[node.id], seen | {node.id})
        return [node]

    def stable_name(nid, assign_index, seen):
        if nid in _ISINSTANCE_TYPE_NAMES or nid in _ISINSTANCE_EXC_NAMES:
            return not binding_positions.get(nid)
        if nid in defs:
            found = binding_positions.get(nid, ())
            return len(found) == 1 and found[0][0] < assign_index
        if nid in constants and nid not in seen:
            return (where[nid] < assign_index
                    and stable_value(constants[nid], assign_index, seen | {nid}))
        return False

    def stable_value(node, assign_index, seen):
        if isinstance(node, ast.Tuple):
            return bool(node.elts) and all(stable_value(e, assign_index, seen) for e in node.elts)
        if isinstance(node, ast.Name):
            return stable_name(node.id, assign_index, seen)
        return False

    def direct_nodes(name, chain):
        value = constants[name]
        if not stable_value(value, where[name], frozenset((name,))):
            return None
        leaves = expand_value(value, frozenset((name,)))
        if not all(isinstance(e, ast.Name) and not _shadowed(e.id, chain) for e in leaves):
            return None
        return leaves

    uses = _isinstance_uses(tree)
    replaceable = set()
    for call, chain, index in uses:
        for node in ast.walk(call.args[1]):
            if (isinstance(node, ast.Name) and node.id in module_allowed
                    and not _shadowed(node.id, chain)):
                replaceable.add(id(node))
    reads0 = _module_reads(tree)

    def can_drop(name):
        return not any(not _shadowed(name, chain) and id(node) not in replaceable
                       for node, chain in reads0.get(name, ()))

    used_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}

    def fresh(base):
        name, k = base, 1
        while name in used_names:
            name = '%s_%d' % (base, k)
            k += 1
        used_names.add(name)
        return name

    snapshot_names = {}
    forward_aliases = {}

    def forward_alias(nid):
        # A name bound only later in the module: read it through a module-level alias installed at
        # that binding, so the snapshot before it sees an unbound name (NameError), not the class
        # object this emitter creates at startup.
        if nid not in forward_aliases:
            found = binding_positions.get(nid, ())
            index = found[0][0] if found else len(tree.body)
            forward_aliases[nid] = (fresh('_ail_defined_%s' % nid), index)
        return forward_aliases[nid][0]

    def snapshot_leaf_nodes(node, name, seen):
        if isinstance(node, ast.Tuple):
            out = []
            for e in node.elts:
                out.extend(snapshot_leaf_nodes(e, name, seen))
            return out
        if (isinstance(node, ast.Name) and node.id in module_allowed and node.id not in seen
                and where[node.id] < where[name]):
            return snapshot_leaf_nodes(constants[node.id], name, seen | {node.id})
        return [node]

    def forward_unbound(node, name):
        if not isinstance(node, ast.Name):
            return False
        nid = node.id
        if nid in _ISINSTANCE_TYPE_NAMES or nid in _ISINSTANCE_EXC_NAMES:
            return False
        return not any(index < where[name] for index, _ in binding_positions.get(nid, ()))

    def snapshot_for(name):
        if name not in snapshot_names:
            leaves = snapshot_leaf_nodes(constants[name], name, frozenset((name,)))
            items = []
            for i, leaf in enumerate(leaves):
                hidden = fresh('_ail_snap_%s_%d' % (name, i))
                if forward_unbound(leaf, name):
                    # CPython reads the name at the assignment and it is not bound yet: keep the
                    # NameError at the same point (the class objects are hoisted here, so a plain
                    # snapshot of the name would silently find the later class).
                    leaf = ast.copy_location(
                        ast.Name(id=forward_alias(leaf.id), ctx=ast.Load()), leaf)
                items.append((hidden, leaf))
            snapshot_names[name] = items
        return snapshot_names[name]

    def target_of(stmt):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            return stmt.targets[0].id
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            return stmt.target.id
        return None

    changed = False
    for call, chain, index in uses:
        spec = call.args[1]

        def expand_use(node):
            if isinstance(node, ast.Tuple):
                out = []
                for e in node.elts:
                    out.extend(expand_use(e))
                return out
            if (isinstance(node, ast.Name) and node.id in module_allowed
                    and not _shadowed(node.id, chain)):
                direct = direct_nodes(node.id, chain)
                if direct is not None and where[node.id] < index:
                    return direct
                if can_drop(node.id):
                    return [ast.Name(id=hidden, ctx=ast.Load())
                            for hidden, _ in snapshot_for(node.id)]
            return [node]

        expanded = expand_use(spec)
        if not expanded or not all(isinstance(e, (ast.Name, ast.Attribute)) for e in expanded):
            continue
        if len(expanded) == 1 and expanded[0] is spec:
            continue
        new = expanded[0] if len(expanded) == 1 else ast.Tuple(elts=expanded, ctx=ast.Load())
        call.args[1] = ast.copy_location(new, spec)
        changed = True
    if not changed:
        return False
    # A snapshot is evaluated where the assignment was, so the original expression runs once (and
    # still raises the NameError CPython raises) even though the assignment itself is dropped.
    if snapshot_names or forward_aliases:
        by_index = {}
        for nid, (alias, index) in forward_aliases.items():
            by_index.setdefault(index, []).append((alias, nid))
        body = []
        for index, stmt in enumerate(tree.body):
            target = target_of(stmt)
            if target in snapshot_names:
                for hidden, leaf in snapshot_names[target]:
                    body.append(ast.copy_location(ast.Assign(
                        targets=[ast.Name(id=hidden, ctx=ast.Store())], value=leaf), stmt))
            body.append(stmt)
            for alias, nid in by_index.get(index, ()):
                # The snapshot before this point already raised NameError, so the alias only has
                # to become bound here: it need not read the name (whose value the general path
                # may not be able to build as a plain value).  The subscript keeps the emitter
                # from hoisting this constant assignment above the snapshot.
                value = ast.Subscript(value=ast.List(elts=[ast.Constant(value=None)], ctx=ast.Load()),
                                      slice=ast.Constant(value=0), ctx=ast.Load())
                body.append(ast.copy_location(ast.Assign(
                    targets=[ast.Name(id=alias, ctx=ast.Store())], value=value), stmt))
        tree.body = body
    # A constant may name another one (`NESTED = ((float, bool), TYPES)`).  Drop the assignments
    # whose every use was replaced, repeating so a constant reached only through a dropped one
    # goes too.  Only a type tuple or alias is dropped: an unrelated unused module assignment can
    # still have a side effect (`X = print("hi")`) and must keep running.  The values themselves
    # are left alone, so a constant that is also read elsewhere keeps its nesting.  A use left in
    # place (shadowed, or with another read) still counts as a read, so its assignment stays and a
    # name that cannot be built here is refused by name instead.
    droppable = {name for name, value in constants.items() if is_type(value, frozenset())}
    while True:
        reads = _module_reads(tree)
        body = []
        dropped = False
        for stmt in tree.body:
            target = target_of(stmt)
            if target in droppable and not any(not _shadowed(target, chain)
                                               for _, chain in reads.get(target, ())):
                dropped = True
                continue
            body.append(stmt)
        tree.body = body
        if not dropped:
            break
    return True

def rewrite(source, notes=None):
    """The program with its tuples lowered; the source as written when no tuple use needs it (or when one is not
    built -- the reason is then added to `notes`)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if _expand_isinstance_type_constants(tree):
        ast.fix_missing_locations(tree)
        source = ast.unparse(tree)
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return source
    if not candidate(tree):
        return source
    import numidentity
    if numidentity.tuple_refusal(source) is not None:
        return source                  # leave the tuple `is` for numidentity's refusal (it names the difference)
    import dictviews
    view = dictviews.escape(tree)
    if view is not None:             # a dict view shown as a value: the general path has it, this pass would show a list
        if notes is not None:
            notes.append((getattr(view, 'lineno', 1), dictviews.refusal(view)))
        return source
    try:
        first = Lower(source)
        first.process()
        second = Lower(source, first.hints, first.rets_out)
        second.process()
        if second.errors:
            # the compiler refuses the program with its own message; these name what was not built
            if notes is not None:
                notes.extend(sorted(set(second.errors)))
            return source
        if not second.forced:
            return source
        return second.text()
    except Refused as exc:
        if notes is not None:
            notes.append(exc.args[0])
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError, AssertionError) as exc:
        if notes is not None:
            notes.append((1, 'the tuple rewrite could not handle this program (%s: %s); simplify the tuple use '
                          'or report it' % (type(exc).__name__, exc)))
        return source


if __name__ == '__main__':
    src = Path(sys.argv[1]).read_text(encoding='utf-8')
    notes = []
    out = rewrite(src, notes)
    print(out)
    for n in notes:
        print('NOTE', n, file=sys.stderr)
