"""`list[list[T]]`: nested lists, lowered to a list of row objects before compilation.

A row is a hidden struct with one list field -- `class _AilRow_int: v: list[int]` -- so a nested
list is an ordinary `list[_AilRow_int]` and every existing path for lists of structs (locals,
fields, parameters, results, refcounted freeing, unwinding on exceptions) carries it unchanged.
This pass rewrites the module AST once, with types it settles itself from the AIL source's
annotations and initializers:

    g[i][j]          -> g[i].v[j]          (read, write, +=: O(1), no copy of either list)
    g[i].append(x)   -> g[i].v.append(x)   (and every other list method, len, for, in, slices)
    g.append(xs)     -> g.append(_AilRow_int(xs))   (a plain list stored as a row is copied)
    [[0] * w for _ in range(h)]  -> a loop appending `_AilRow_int([0] * w)` to a temporary

Python's aliasing is kept where a row stays a row: `let r = g[i];`, `for r in g`, `g[j] = g[i]`
and `g.append(g[i])` share the row, so `r.append(x)` is seen through `g`. A row read where a
plain `list[T]` is expected (`let r: list[T] = g[i];`, an argument, a result) is that list --
copied by the usual list value rules. `[[...]] * n` is refused: in Python every row would be the
same list, the classic bug; the comprehension says what is meant.

Types the pass cannot settle are left alone, so the compiler's own refusals still apply. A
function returning `list[list[int]]` whose results are not nested lists this pass knows of
(the older pool-handle grids, `let result = []; result.append(row)`) is also left alone.
"""
import ast
import copy

ROW_PREFIX = '_AilRow_'
SCALARS = ('int', 'float', 'str')
_STR_METHODS = {'strip', 'lstrip', 'rstrip', 'lower', 'upper', 'replace', 'join', 'format',
                'title', 'capitalize', 'zfill', 'ljust', 'rjust', 'center', 'decode', 'casefold'}
_INT_METHODS = {'index', 'count', 'find', 'rfind', 'startswith', 'endswith', 'isdigit', 'isalpha',
                'isspace', 'isupper', 'islower', 'isalnum'}


def _nest(t):
    return isinstance(t, tuple) and t[0] == 'nest'


def _row(t):
    return isinstance(t, tuple) and t[0] == 'row'


def _plain_list(t):
    return isinstance(t, tuple) and t[0] == 'list'


def _listlike(t):
    return _row(t) or _plain_list(t)


def _struct(t):
    return isinstance(t, tuple) and t[0] == 'S'


def _elem(t):
    if _nest(t):
        return ('row', t[1])
    if _listlike(t):
        return t[1]
    if t == 'str':
        return 'str'
    if t in ('bytes', 'range'):
        return 'int'
    return None


def _empty_list(node):
    return isinstance(node, ast.List) and not node.elts


def _runs_no_code(node):
    return not any(isinstance(n, (ast.Call, ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp,
                                  ast.Lambda, ast.NamedExpr)) for n in ast.walk(node))


def _describe(t):
    text = _element_text(t[1])
    return 'a list[list[%s]]' % text if _nest(t) else 'a list[%s] row' % text


def row_class(element):
    return ROW_PREFIX + (element[1] if _struct(element) else element)


def _element_text(element):
    return element[1] if _struct(element) else element


class NestedLists:
    def __init__(self, tree, unsupported, library, entry=None):
        self.tree = tree
        self.Unsupported = unsupported
        self.library = library
        self.entry = entry
        self.structs = {}            # name -> {'fields': {f: type}, 'methods': {m: (params, ret)}}
        self.funcs = {}              # name -> (params [(name, type)], ret)
        self.rows = {}               # row class name -> element type
        self.counter = 0
        self.legacy = set()          # functions returning list[list[int]] left to the older grids

    # ---------------------------------------------------------------- annotations
    def ann(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode='eval').body
            except SyntaxError:
                return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self.ann(node.left)
        if isinstance(node, ast.Name):
            name = node.id
            if name.startswith('__ail_checked_') and name.endswith('__'):
                name = name[len('__ail_checked_'):-2]
            if name in ('int', 'float', 'str', 'bytes'):
                return name
            if name == 'flist':
                return ('list', 'float')
            if name in self.structs:
                return ('S', name)
            if name in self.rows:
                return ('row', self.rows[name])
            return None
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in ('list', '__ail_checked_list')):
            inner = self.ann(node.slice)
            if _plain_list(inner) or _row(inner):
                return ('nest', inner[1])
            if inner is not None and not _listlike(inner) and not _nest(inner):
                return ('list', inner)
        return None

    def nested_element(self, node):
        """The T of a `list[list[T]]` annotation node, else None; unsupported T refused."""
        if not (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in ('list', '__ail_checked_list')):
            return None
        inner = node.slice
        if not (isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name)
                and inner.value.id == 'list'):
            return None
        leaf = inner.slice
        if isinstance(leaf, ast.Name) and (leaf.id in SCALARS or leaf.id in self.structs):
            return leaf.id if leaf.id in SCALARS else ('S', leaf.id)
        raise self.Unsupported('list[list[%s]]: a nested list holds rows of int, float, str or a '
                               'struct; keep a list of structs for anything else' % ast.unparse(leaf))

    def row_ann(self, element, checked=False):
        self.rows.setdefault(row_class(element), element)
        return ast.Subscript(value=ast.Name(id='__ail_checked_list' if checked else 'list', ctx=ast.Load()),
                             slice=ast.Name(id=row_class(element), ctx=ast.Load()), ctx=ast.Load())

    def convert_ann(self, node, checked=False):
        element = self.nested_element(node)
        if element is None:
            return node
        return ast.copy_location(self.row_ann(element, checked or node.value.id == '__ail_checked_list'), node)

    # ---------------------------------------------------------------- module scan
    def scan(self):
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                self.structs[node.name] = {'fields': {}, 'methods': {}}
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                info = self.structs[node.name]
                for member in node.body:
                    if not isinstance(member, ast.FunctionDef):
                        continue
                    if member.name == '__init__':
                        for arg in member.args.args[1:]:
                            info['fields'][arg.arg] = self.ann(arg.annotation)
                    else:
                        info['methods'][member.name] = (
                            [(a.arg, self.ann(a.annotation)) for a in member.args.args[1:]],
                            self.ann(member.returns))
            elif isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = ([(a.arg, self.ann(a.annotation)) for a in node.args.args],
                                         self.ann(node.returns))

    def field_type(self, base_type, attr):
        if _struct(base_type) and base_type[1] in self.structs:
            return self.structs[base_type[1]]['fields'].get(attr)
        if base_type is None:
            found = {repr(info['fields'][attr]) : info['fields'][attr]
                     for info in self.structs.values() if attr in info['fields']}
            if len(found) == 1:
                return next(iter(found.values()))
        return None

    # ---------------------------------------------------------------- expression types
    def ty(self, e, env):
        if isinstance(e, ast.Constant):
            v = e.value
            return ('int' if isinstance(v, (bool, int)) else 'float' if isinstance(v, float)
                    else 'str' if isinstance(v, str) else 'bytes' if isinstance(v, bytes) else None)
        if isinstance(e, ast.JoinedStr):
            return 'str'
        if isinstance(e, ast.Name):
            return env.get(e.id)
        if isinstance(e, ast.Attribute):
            if isinstance(e.value, ast.Name) and e.value.id == 'sys' and e.attr == 'argv':
                return ('list', 'str')
            base = self.ty(e.value, env)
            if _row(base) and e.attr == 'v':
                return ('list', base[1])
            return self.field_type(base, e.attr)
        if isinstance(e, ast.Subscript):
            base = self.ty(e.value, env)
            if isinstance(e.slice, ast.Slice):
                if _nest(base) or _plain_list(base) or base in ('str', 'bytes'):
                    return base
                if _row(base):
                    return ('list', base[1])
                return None
            return _elem(base)
        if isinstance(e, ast.List):
            types = [self.ty(x, env) for x in e.elts]
            if types and all(_listlike(t) or (t is None and _empty_list(x)) for t, x in zip(types, e.elts)):
                known = [t[1] for t in types if t is not None and t[1] is not None]
                return ('nest', known[0] if known else None)
            known = [t for t in types if t is not None]
            if known and not _nest(known[0]):
                return ('list', known[0])
            return ('list', None) if not types else None
        if isinstance(e, ast.ListComp):
            inner = dict(env)
            for gen in e.generators:
                self.bind_target(gen.target, _elem(self.ty(gen.iter, inner))
                                 if not self.is_enumerate(gen.iter) else ('enum', self.ty(gen.iter.args[0], inner)), inner)
            t = self.ty(e.elt, inner)
            if _listlike(t) or (t is None and _empty_list(e.elt)):
                return ('nest', t[1] if t else None)
            if t is not None and not _nest(t):
                return ('list', t)
            return None
        if isinstance(e, ast.BinOp):
            left, right = self.ty(e.left, env), self.ty(e.right, env)
            if isinstance(e.op, ast.Mult):
                if _listlike(left) or _nest(left):
                    return ('list', left[1]) if _listlike(left) else left
                if _listlike(right) or _nest(right):
                    return ('list', right[1]) if _listlike(right) else right
            if isinstance(e.op, ast.Add) and (_listlike(left) or _nest(left)):
                return ('list', left[1]) if _listlike(left) else left
            if 'str' in (left, right):
                return 'str'
            if 'float' in (left, right) or isinstance(e.op, ast.Div):
                return 'float'
            if left == 'int' and right == 'int':
                return 'int'
            return None
        if isinstance(e, ast.UnaryOp):
            return 'int' if isinstance(e.op, ast.Not) else self.ty(e.operand, env)
        if isinstance(e, (ast.Compare, ast.BoolOp)):
            return 'int'
        if isinstance(e, ast.IfExp):
            return self.ty(e.body, env) or self.ty(e.orelse, env)
        if isinstance(e, ast.Call):
            return self.call_type(e, env)
        return None

    def is_enumerate(self, node):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'enumerate' and len(node.args) == 1)

    def call_type(self, e, env):
        f = e.func
        if isinstance(f, ast.Name):
            name = f.id
            if name in self.structs:
                return ('S', name)
            if name in self.rows:
                return ('row', self.rows[name])
            if name in self.funcs:
                return self.funcs[name][1]
            if name in ('len', 'int', 'ord', 'hash'):
                return 'int'
            if name == 'float':
                return 'float'
            if name in ('str', 'chr', 'input', 'repr'):
                return 'str'
            if name in ('abs',) and e.args:
                return self.ty(e.args[0], env)
            if name in ('sorted', 'list', 'reversed') and e.args:
                t = self.ty(e.args[0], env)
                return t if _nest(t) else ('list', _elem(t)) if _elem(t) is not None else None
            if name in ('min', 'max', 'sum') and e.args:
                t = self.ty(e.args[0], env)
                if len(e.args) == 1:
                    return _elem(t) if name != 'sum' or _elem(t) else 'int'
                return t
            if name == 'range':
                return 'range'
            if name == 'heappop' and e.args:
                return _elem(self.ty(e.args[0], env))
            return None
        if isinstance(f, ast.Attribute):
            base = self.ty(f.value, env)
            m = f.attr
            if _struct(base) and base[1] in self.structs:
                method = self.structs[base[1]]['methods'].get(m)
                return method[1] if method else None
            if _nest(base) or _listlike(base):
                if m == 'pop':
                    return _elem(base)
                if m == 'copy':
                    return base if _nest(base) else ('list', base[1])
                if m in ('index', 'count'):
                    return 'int'
                return None
            if m in ('split', 'splitlines', 'rsplit'):
                return ('list', 'str')
            if m in _STR_METHODS:
                return 'str'
            if m in _INT_METHODS:
                return 'int'
            if m == 'encode':
                return 'bytes'
        return None

    def bind_target(self, target, t, env, force=False):
        if isinstance(target, ast.Name):
            old = env.get(target.id)
            if (not force and old != t and (_nest(old) or _row(old)) and (_nest(t) or _row(t))
                    and old[1] is not None and t[1] is not None):
                raise self.Unsupported('`%s` holds %s here but %s elsewhere in the function; a local keeps '
                                       'one type -- use another name' % (target.id, _describe(t), _describe(old)))
            if t is not None and (force or old is None):
                env[target.id] = t
        elif isinstance(target, ast.Tuple) and isinstance(t, tuple) and t[0] == 'enum' and len(target.elts) == 2:
            self.bind_target(target.elts[0], 'int', env, force)
            self.bind_target(target.elts[1], _elem(t[1]), env, force)

    # ---------------------------------------------------------------- per-function environment
    def statements(self, body):
        for s in body:
            yield s
            for field in ('body', 'orelse', 'finalbody'):
                yield from self.statements(getattr(s, field, []) or [])
            for handler in getattr(s, 'handlers', []) or []:
                yield from self.statements(handler.body)

    def environment(self, fn, owner):
        env = {}
        for arg in fn.args.args:
            env[arg.arg] = self.ann(arg.annotation)
        if owner is not None and fn.args.args:
            env[fn.args.args[0].arg] = ('S', owner)
        annotated = set()
        for s in self.statements(fn.body):
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                env[s.target.id] = self.ann(s.annotation)
                annotated.add(s.target.id)
        def bind(s):
            if (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
                    and s.targets[0].id not in annotated):
                current = env.get(s.targets[0].id)
                t = self.ty(s.value, env)
                if current is None or (_nest(current) and current[1] is None and _nest(t) and t[1]):
                    if t is not None:
                        env[s.targets[0].id] = t
                elif _row(t) or _nest(t):
                    self.bind_target(s.targets[0], t, env)
            elif isinstance(s, ast.For):
                if self.is_enumerate(s.iter):
                    self.bind_target(s.target, ('enum', self.ty(s.iter.args[0], env)), env)
                else:
                    self.bind_target(s.target, _elem(self.ty(s.iter, env)), env)
        for _ in range(4):
            for s in self.statements(fn.body):
                try:
                    bind(s)
                except self.Unsupported as error:
                    error.source_line = getattr(s, 'lineno', None)
                    raise
        # `let g = [[] for _ in range(n)];` says nothing about T: take it from what is appended
        # to or stored in a row, else int.
        for name, t in list(env.items()):
            if _nest(t) and t[1] is None:
                env[name] = ('nest', self.infer_element(fn, name, env) or 'int')
        return env

    def infer_element(self, fn, name, env):
        for n in ast.walk(fn):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.args
                    and isinstance(n.func.value, ast.Subscript)
                    and isinstance(n.func.value.value, ast.Name) and n.func.value.value.id == name):
                if n.func.attr in ('append', 'insert'):
                    t = self.ty(n.args[-1], env)
                    if t in SCALARS or _struct(t):
                        return t
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.args
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == name
                    and n.func.attr == 'append'):
                t = self.ty(n.args[0], env)
                if _listlike(t) and t[1] is not None:
                    return t[1]
            if isinstance(n, ast.Assign):
                for target in n.targets:
                    if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Subscript)
                            and isinstance(target.value.value, ast.Name) and target.value.value.id == name):
                        t = self.ty(n.value, env)
                        if t in SCALARS or _struct(t):
                            return t
        return None

    # ---------------------------------------------------------------- rewriting
    def fresh(self, stem):
        self.counter += 1
        return '_ail_%s%d' % (stem, self.counter)

    def run(self):
        self.scan()
        # Annotations on struct fields and signatures; struct field types become row lists.
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef) and member.name == '__init__':
                        for arg in member.args.args[1:]:
                            arg.annotation = self.convert_ann(arg.annotation)
        self.decide_legacy()
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and self.signature_legacy(node):
                params, ret = self.funcs[node.name]
                self.funcs[node.name] = ([(n, None if _nest(t) else t) for n, t in params],
                                         None if _nest(ret) else ret)
        for node in list(self.tree.body):
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef) and member.name != '__init__':
                        self.function(member, node.name)
            elif isinstance(node, ast.FunctionDef):
                self.function(node, None)
        if self.rows:
            classes = []
            for name, element in sorted(self.rows.items()):
                cls = ast.parse('class %s:\n    def __init__(self, v: list[%s]):\n        self.v = v\n'
                                % (name, _element_text(element))).body[0]
                for n in ast.walk(cls):
                    n.lineno = n.end_lineno = 1
                    n.col_offset = n.end_col_offset = 0
                classes.append(cls)
            self.tree.body[0:0] = classes
        ast.fix_missing_locations(self.tree)
        return bool(self.rows)

    def signature_legacy(self, fn):
        """A function whose signature a host sees (library exports, the entry point), or one
        returning a grid built the older way, is compiled exactly as before."""
        if self.library or fn.name == self.entry:
            return any(self.nested_annotation(a.annotation) for a in fn.args.args) or self.nested_annotation(fn.returns)
        return fn.name in self.legacy

    def nested_annotation(self, node):
        try:
            return self.nested_element(node) is not None
        except Exception:
            return True

    def decide_legacy(self):
        """Functions returning `list[list[int]]` built the older way keep the pool-handle grids."""
        candidates = {}
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and self.nested_element(node.returns) == 'int' \
                    and isinstance(node.returns, ast.Subscript) and node.returns.value.id == 'list':
                candidates[node.name] = node
        legacy = set(candidates)
        for name in legacy:
            self.funcs[name] = (self.funcs[name][0], None)
        changed = True
        while changed:
            changed = False
            for name in sorted(legacy - {self.entry}):
                fn = candidates[name]
                env = self.environment(fn, None)
                if any(isinstance(n, ast.Return) and n.value is not None and _nest(self.ty(n.value, env))
                       for n in ast.walk(fn)):
                    legacy.discard(name)
                    self.funcs[name] = (self.funcs[name][0], ('nest', 'int'))
                    changed = True
        self.legacy = legacy

    def function(self, fn, owner):
        if self.signature_legacy(fn):
            return
        env = self.environment(fn, owner)
        self.ret = self.ann(fn.returns)
        for arg in fn.args.args:
            arg.annotation = self.convert_ann(arg.annotation)
        if fn.returns is not None and self.nested_element(fn.returns) is not None:
            fn.returns = self.convert_ann(fn.returns, checked=True)
        if not any(_nest(t) or _row(t) for t in env.values()) and not self.mentions_nesting(fn):
            return
        self.env = env
        self.cond = 0
        self.build_into = self.built_into = None
        fn.body = self.block(fn.body)

    def mentions_nesting(self, fn):
        for n in ast.walk(fn):
            if isinstance(n, ast.ListComp) and isinstance(n.elt, (ast.List, ast.ListComp)):
                return True
            if isinstance(n, ast.List) and n.elts and all(isinstance(x, (ast.List, ast.ListComp)) for x in n.elts):
                return True
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and (
                    isinstance(n.left, ast.List) and len(n.left.elts) == 1 and isinstance(n.left.elts[0], (ast.List, ast.ListComp))
                    or isinstance(n.right, ast.List) and len(n.right.elts) == 1 and isinstance(n.right.elts[0], (ast.List, ast.ListComp))):
                return True
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and (
                    n.func.id in self.funcs and any(_nest(t) for _, t in self.funcs[n.func.id][0])
                    or n.func.id in self.structs and any(_nest(t) for t in self.structs[n.func.id]['fields'].values())):
                return True
            if isinstance(n, ast.Attribute) and any(_nest(info['fields'].get(n.attr))
                                                    for info in self.structs.values()):
                return True
        return False

    def block(self, body):
        out = []
        for s in body:
            try:
                out.extend(self.stmt(s))
            except self.Unsupported as error:
                if getattr(error, 'source_line', None) is None:
                    error.source_line = getattr(s, 'lineno', None)
                raise
        return out

    def stmt(self, s):
        pre = []
        env = self.env
        if isinstance(s, ast.Assign):
            if len(s.targets) == 1 and isinstance(s.targets[0], ast.Tuple) and isinstance(s.value, ast.Tuple) \
                    and len(s.targets[0].elts) == len(s.value.elts):
                wants = [self.target_want(t) for t in s.targets[0].elts]
                s.value.elts = [self.expr(v, w, pre) for v, w in zip(s.value.elts, wants)]
                s.targets[0].elts = [self.target(t, pre) for t in s.targets[0].elts]
            else:
                want = self.target_want(s.targets[0]) if len(s.targets) == 1 else None
                self.direct(s, s.targets[0] if len(s.targets) == 1 else None)
                s.value = self.expr(s.value, want, pre)
                s.targets = [self.target(t, pre) for t in s.targets]
        elif isinstance(s, ast.AnnAssign):
            want = self.ann(s.annotation)
            s.annotation = self.convert_ann(s.annotation)
            if s.value is not None:
                self.direct(s, s.target)
                s.value = self.expr(s.value, want if _nest(want) else None, pre)
        elif isinstance(s, ast.AugAssign):
            self.settle_target(s.target, pre)
            t = self.ty(s.target, env)
            s.value = self.expr(s.value, ('nest', t[1]) if _nest(t) else None, pre)
            s.target = self.target(s.target, pre, aug=True)
        elif isinstance(s, ast.Return):
            if s.value is not None:
                s.value = self.expr(s.value, self.ret if _nest(self.ret) else None, pre)
        elif isinstance(s, ast.Expr):
            s.value = self.expr(s.value, None, pre)
        elif isinstance(s, ast.For):
            s.iter = self.expr(s.iter, None, pre)
            s.body = self.block(s.body)
            s.orelse = self.block(s.orelse)
        elif isinstance(s, ast.While):
            test_pre = []
            s.test = self.expr(s.test, None, test_pre)
            if test_pre:
                raise self.Unsupported('a nested-list comprehension in a while condition: build it with a let before the loop')
            s.body = self.block(s.body)
            s.orelse = self.block(s.orelse)
        elif isinstance(s, ast.If):
            s.test = self.expr(s.test, None, pre)
            s.body = self.block(s.body)
            s.orelse = self.block(s.orelse)
        elif isinstance(s, ast.Try):
            s.body = self.block(s.body)
            for handler in s.handlers:
                handler.body = self.block(handler.body)
            s.orelse = self.block(s.orelse)
            s.finalbody = self.block(s.finalbody)
        elif isinstance(s, ast.Raise):
            if s.exc is not None:
                s.exc = self.expr(s.exc, None, pre)
        elif isinstance(s, ast.Assert):
            s.test = self.expr(s.test, None, pre)
            if s.msg is not None:
                s.msg = self.expr(s.msg, None, pre)
        elif isinstance(s, ast.Delete):
            s.targets = [self.target(t, pre) for t in s.targets]
        for p in pre:
            ast.copy_location(p, s)
        if self.built_into is not None:
            # `let rows = [...]` hoisted: the loop appended straight into `rows`.
            self.built_into = None
            return pre
        return pre + [s]

    def direct(self, s, target):
        """`let xs = [...]` whose comprehension becomes a loop: the loop may build `xs` itself
        (no temporary and no copy) when the comprehension does not read `xs`."""
        self.build_into = self.built_into = None
        if (isinstance(target, ast.Name) and isinstance(s.value, ast.ListComp)
                and not any(isinstance(n, ast.Name) and n.id == target.id for n in ast.walk(s.value))):
            self.build_into = (s.value, target.id)

    def settle_target(self, target, pre):
        """`g[i][f()] += v` reads and writes one element: Python evaluates the row and the index
        once, so a row or index that runs code is bound to a temporary first."""
        if not (isinstance(target, ast.Subscript) and not isinstance(target.slice, ast.Slice)):
            return
        base = self.ty(target.value, self.env)
        if not (_row(base) or _nest(base)):
            return
        if (_row(base) and isinstance(target.value, ast.Subscript)
                and not (_runs_no_code(target.value) and _runs_no_code(target.slice))):
            temp = self.fresh('row')
            self.env[temp] = base
            pre.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())],
                                  value=self.expr(target.value, base, pre), lineno=target.lineno))
            target.value = ast.copy_location(ast.Name(id=temp, ctx=ast.Load()), target.value)
        if not _runs_no_code(target.slice):
            temp = self.fresh('index')
            self.env[temp] = 'int'
            pre.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())],
                                  value=self.expr(target.slice, None, pre), lineno=target.lineno))
            target.slice = ast.copy_location(ast.Name(id=temp, ctx=ast.Load()), target.slice)

    def target_want(self, target):
        env = self.env
        if isinstance(target, ast.Name):
            t = env.get(target.id)
            return t if _nest(t) or _row(t) else None
        if isinstance(target, ast.Subscript) and not isinstance(target.slice, ast.Slice):
            base = self.ty(target.value, env)
            if _nest(base):
                return ('row', base[1])
            return None
        if isinstance(target, ast.Subscript):
            base = self.ty(target.value, env)
            return base if _nest(base) else None
        if isinstance(target, ast.Attribute):
            t = self.ty(target, env)
            return t if _nest(t) else None
        return None

    def target(self, target, pre, aug=False):
        """Rewrite an assignment target: a row used as a list becomes `row.v`."""
        env = self.env
        if isinstance(target, ast.Subscript):
            base_type = self.ty(target.value, env)
            own = self.ty(target, env)
            target.value = self.base(target.value, pre)
            if _row(base_type):
                target.value = ast.copy_location(ast.Attribute(value=target.value, attr='v', ctx=ast.Load()), target)
            target.slice = self.expr(target.slice, None, pre)
            if aug and _row(own):
                return ast.copy_location(ast.Attribute(value=self.as_load(target), attr='v', ctx=ast.Store()), target)
            return target
        if isinstance(target, ast.Attribute):
            target.value = self.base(target.value, pre)
            return target
        if isinstance(target, ast.Name) and aug and _row(env.get(target.id)):
            return ast.copy_location(ast.Attribute(value=ast.Name(id=target.id, ctx=ast.Load()), attr='v',
                                                   ctx=ast.Store()), target)
        if isinstance(target, ast.Tuple):
            target.elts = [self.target(t, pre) for t in target.elts]
        return target

    def as_load(self, node):
        node = copy.copy(node)
        node.ctx = ast.Load()
        return node

    def base(self, e, pre):
        """An expression whose value is used as a struct or receiver: never unwrapped here."""
        return self.expr(e, 'keep', pre)

    def row_call(self, element, value, near):
        self.rows.setdefault(row_class(element), element)
        return ast.copy_location(ast.Call(func=ast.Name(id=row_class(element), ctx=ast.Load()),
                                          args=[value], keywords=[]), near)

    def refuse_repeat(self, e):
        for side, count in ((e.left, e.right), (e.right, e.left)):
            if isinstance(side, ast.List) and len(side.elts) == 1:
                inner = side.elts[0]
                t = self.ty(inner, self.env)
                if _listlike(t) or _nest(t) or isinstance(inner, (ast.List, ast.ListComp)):
                    row = ast.unparse(inner) if isinstance(inner, (ast.List, ast.ListComp, ast.BinOp)) \
                        else '%s.copy()' % ast.unparse(inner)
                    raise self.Unsupported(
                        '`%s` makes every row the same list (in Python too: changing one row changes '
                        'them all); build independent rows with a comprehension: '
                        '`[%s for _ in range(%s)]`' % (ast.unparse(e), row, ast.unparse(count)))

    def expr(self, e, want, pre):
        env = self.env
        t = self.ty(e, env)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
            self.refuse_repeat(e)
        if isinstance(e, ast.ListComp) and (_nest(want) or _nest(t)):
            element = (want[1] if _nest(want) and want[1] is not None else t[1] if _nest(t) and t[1] else 'int')
            if self.cond:
                raise self.Unsupported('a nested-list comprehension that is only evaluated sometimes (in a '
                                       'condition, a conditional expression, a lambda or another '
                                       'comprehension): build it first with a let')
            return self.hoist(e, element, pre)
        if isinstance(e, ast.List) and (_nest(want) or _nest(t)):
            element = (want[1] if _nest(want) and want[1] is not None else t[1] if _nest(t) and t[1] else 'int')
            e.elts = [self.expr(x, ('row', element), pre) for x in e.elts]
            return e
        if (isinstance(e, ast.ListComp) and not self.cond and _plain_list(t)
                and (t[1] == 'str' or _struct(t[1]) or len(e.generators) > 1 and t[1] in SCALARS)
                and self.walks_rows(e)):
            # `[",".join(b) for b in buckets]`, `[x for row in g for x in row]`: a list of structs
            # is walked by comprehension only into numbers, one level deep, so these are loops.
            return self.hoist(e, t[1], pre, rows=False)
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)):
            saved = self.env
            self.env = env = dict(env)
            for index, gen in enumerate(e.generators):
                if index:
                    self.cond += 1
                gen.iter = self.expr(gen.iter, None, pre)
                if index:
                    self.cond -= 1
                self.bind_target(gen.target, _elem(self.ty(gen.iter, env)) if not self.is_enumerate(gen.iter)
                                 else ('enum', self.ty(gen.iter.args[0], env)), env, force=True)
                self.cond += 1
                gen.ifs = [self.expr(c, None, pre) for c in gen.ifs]
                self.cond -= 1
            self.cond += 1
            if isinstance(e, ast.DictComp):
                e.key = self.expr(e.key, None, pre)
                e.value = self.expr(e.value, None, pre)
            else:
                e.elt = self.expr(e.elt, None, pre)
            self.cond -= 1
            self.env = saved
            return self.finish(e, t, want)
        if isinstance(e, ast.BoolOp):
            e.values = [self.expr(e.values[0], None, pre)] + [self.conditional(v, None, pre) for v in e.values[1:]]
            return e
        if isinstance(e, ast.Subscript):
            base_type = self.ty(e.value, env)
            e.value = self.base(e.value, pre)
            if _row(base_type):
                e.value = ast.copy_location(ast.Attribute(value=e.value, attr='v', ctx=ast.Load()), e)
            e.slice = self.expr(e.slice, None, pre)
            return self.finish(e, t, want)
        if isinstance(e, ast.Attribute):
            e.value = self.base(e.value, pre)
            return self.finish(e, t, want)
        if isinstance(e, ast.Call):
            self.call(e, pre)
            return self.finish(e, t, want)
        if isinstance(e, ast.IfExp):
            e.test = self.expr(e.test, None, pre)
            e.body = self.conditional(e.body, want, pre)
            e.orelse = self.conditional(e.orelse, want, pre)
            return e
        if isinstance(e, ast.Lambda):
            e.body = self.conditional(e.body, None, pre)
            return e
        for field, value in ast.iter_fields(e):
            if isinstance(value, ast.expr):
                setattr(e, field, self.expr(value, None, pre))
            elif isinstance(value, list):
                setattr(e, field, [self.expr(v, None, pre) if isinstance(v, ast.expr) else self.misc(v, pre)
                                   for v in value])
            elif isinstance(value, ast.AST) and not isinstance(value, (ast.expr_context, ast.operator,
                                                                      ast.unaryop, ast.cmpop, ast.boolop)):
                setattr(e, field, self.misc(value, pre))
        return self.finish(e, t, want)

    def conditional(self, e, want, pre):
        """An operand Python evaluates only sometimes: nothing in it may be hoisted."""
        self.cond += 1
        try:
            return self.expr(e, want, pre)
        finally:
            self.cond -= 1

    def walks_rows(self, comp):
        """A comprehension walking a nested list, or a row of structs."""
        env = dict(self.env)
        for gen in comp.generators:
            source = gen.iter.args[0] if self.is_enumerate(gen.iter) else gen.iter
            t = self.ty(source, env)
            if _nest(t) or _row(t) and _struct(t[1]):
                return True
            self.bind_target(gen.target, _elem(self.ty(gen.iter, env)) if not self.is_enumerate(gen.iter)
                             else ('enum', t), env, force=True)
        return False

    def misc(self, node, pre):
        if isinstance(node, ast.keyword):
            node.value = self.expr(node.value, None, pre)
        elif isinstance(node, ast.comprehension):
            node.iter = self.expr(node.iter, None, pre)
            node.ifs = [self.expr(c, None, pre) for c in node.ifs]
        elif isinstance(node, ast.FormattedValue):
            node.value = self.expr(node.value, None, pre)
        return node

    def finish(self, e, t, want):
        if want == 'keep':
            return e
        ctx = getattr(e, 'ctx', None)
        if isinstance(ctx, (ast.Store, ast.Del)):
            return e
        if _row(t):
            if _row(want):
                return e
            return ast.copy_location(ast.Attribute(value=e, attr='v', ctx=ast.Load()), e)
        if _row(want) and not _nest(t):
            return self.row_call(want[1], e, e)
        return e

    def param_types(self, call):
        f = call.func
        if isinstance(f, ast.Name):
            if f.id in self.funcs:
                return self.funcs[f.id][0]
            if f.id in self.structs:
                return list(self.structs[f.id]['fields'].items())
        if isinstance(f, ast.Attribute):
            base = self.ty(f.value, self.env)
            if _struct(base) and base[1] in self.structs:
                method = self.structs[base[1]]['methods'].get(f.attr)
                if method:
                    return method[0]
        return None

    def call(self, e, pre):
        env = self.env
        f = e.func
        params = self.param_types(e)
        if isinstance(f, ast.Attribute):
            base_type = self.ty(f.value, env)
            f.value = self.base(f.value, pre)
            if _row(base_type):
                f.value = ast.copy_location(ast.Attribute(value=f.value, attr='v', ctx=ast.Load()), f)
            if _nest(base_type):
                element = base_type[1]
                if f.attr == 'append' and len(e.args) == 1:
                    e.args = [self.expr(e.args[0], ('row', element), pre)]
                elif f.attr == 'insert' and len(e.args) == 2:
                    e.args = [self.expr(e.args[0], None, pre), self.expr(e.args[1], ('row', element), pre)]
                elif f.attr == 'extend' and len(e.args) == 1:
                    e.args = [self.expr(e.args[0], base_type, pre)]
                elif f.attr in ('sort',):
                    pass
                else:
                    e.args = [self.expr(a, None, pre) for a in e.args]
                for kw in e.keywords:
                    kw.value = self.lambda_arg(kw.value, ('row', element), pre)
                return
        if params is not None:
            by_name = dict(params)
            e.args = [self.expr(a, params[i][1] if i < len(params) and _nest(params[i][1]) else None, pre)
                      for i, a in enumerate(e.args)]
            for kw in e.keywords:
                t = by_name.get(kw.arg)
                kw.value = self.expr(kw.value, t if _nest(t) else None, pre)
            return
        if isinstance(f, ast.Name) and f.id in ('sorted', 'min', 'max', 'heappush', 'heappop', 'heapify') and e.args:
            element = _elem(self.ty(e.args[0], env))
            e.args = [self.expr(a, None, pre) for a in e.args]
            for kw in e.keywords:
                kw.value = self.lambda_arg(kw.value, element, pre)
            return
        if not isinstance(f, ast.Attribute):
            e.func = self.expr(f, 'keep', pre)
        e.args = [self.expr(a, None, pre) for a in e.args]
        for kw in e.keywords:
            kw.value = self.lambda_arg(kw.value, None, pre) if isinstance(kw.value, ast.Lambda) \
                else self.expr(kw.value, None, pre)

    def lambda_arg(self, value, element, pre):
        if not isinstance(value, ast.Lambda):
            return self.expr(value, None, pre)
        saved = self.env
        self.env = dict(saved)
        if element is not None and value.args.args:
            self.env[value.args.args[0].arg] = element
        value.body = self.conditional(value.body, None, pre)
        self.env = saved
        return value

    def hoist(self, comp, element, pre, rows=True):
        """`[row_expr for ...]` building a nested list (or, `rows=False`, a list of str or structs
        from one): a loop appending to a temporary, run where the comprehension stood."""
        if self.build_into is not None and self.build_into[0] is comp:
            temp = self.built_into = self.build_into[1]
            self.build_into = None
        else:
            temp = self.fresh('rows' if rows else 'items')
        self.env[temp] = ('nest', element) if rows else ('list', element)
        annotation = self.row_ann(element) if rows else ast.Subscript(
            value=ast.Name(id='list', ctx=ast.Load()), slice=ast.Name(id=_element_text(element), ctx=ast.Load()),
            ctx=ast.Load())
        pre.append(ast.copy_location(ast.AnnAssign(target=ast.Name(id=temp, ctx=ast.Store()),
                                                   annotation=annotation,
                                                   value=ast.List(elts=[], ctx=ast.Load()), simple=1), comp))
        renames = {}

        # Comprehension variables are renamed: they are not the function's locals.
        def rename(node):
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and n.id in renames:
                    n.id = renames[n.id]
            return node
        loops = []
        for gen in comp.generators:
            gen_pre = []
            iterator = self.expr(rename(gen.iter), None, gen_pre)
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name):
                    renames[n.id] = self.fresh('c_' + n.id.strip('_'))
            target = rename(gen.target)
            if self.is_enumerate(iterator):
                self.bind_target(target, ('enum', self.ty(iterator.args[0], self.env)), self.env, force=True)
            else:
                self.bind_target(target, _elem(self.ty(iterator, self.env)), self.env, force=True)
            loop = ast.For(target=target, iter=iterator, body=[], orelse=[])
            conditions = [self.expr(rename(c), None, gen_pre) for c in gen.ifs]
            loops.append((gen_pre, loop, conditions))
        pre_inner = []
        elt = self.expr(rename(comp.elt), ('row', element) if rows else None, pre_inner)
        append = ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id=temp, ctx=ast.Load()),
                                                            attr='append', ctx=ast.Load()),
                                         args=[elt], keywords=[]))
        body = pre_inner + [append]
        for gen_pre, loop, conditions in reversed(loops):
            for c in reversed(conditions):
                body = [ast.If(test=c, body=body, orelse=[])]
            loop.body = body
            body = gen_pre + [loop]
        for s in body:
            for n in ast.walk(s):
                if isinstance(n, (ast.stmt, ast.expr)) and not hasattr(n, 'lineno'):
                    ast.copy_location(n, comp)
        pre.extend(body)
        return ast.copy_location(ast.Name(id=temp, ctx=ast.Load()), comp)


ACTIVE = False   # the last rewrite lowered something (refusals then name rows, not `.v`)


def rewrite(tree, unsupported, library=False, entry=None):
    """Lower every `list[list[T]]` in `tree` to rows; True when anything was lowered. The entry
    point (`entry`, else the last top-level function) keeps its signature: a host calling it
    marshals the older pool-handle grids, not rows."""
    global ACTIVE
    ACTIVE = False
    if entry is None:
        entry = next((node.name for node in reversed(tree.body) if isinstance(node, ast.FunctionDef)), None)
    ACTIVE = NestedLists(tree, unsupported, library, entry).run()
    return ACTIVE


def explain(message):
    """A refusal in source terms: the hidden row struct is `list[T]`, `g[i].v` is `g[i]`."""
    import re
    message = re.sub(r"\('olist', '_AilRow_(\w+)'\)", r'list[list[\1]]', message)
    message = re.sub(r"\(\s*'obj', '_AilRow_(\w+)'\)", r'list[\1]', message)
    message = re.sub(r'\b_AilRow_(\w+)\b', r'list[\1]', message)
    return re.sub(r'(?<=[\w\]\)])\.v\b(?!\()', '', message)
