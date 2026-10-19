"""Nested functions lifted to the module level before either path compiles the program (Python surface).

A `def` written directly in the body of a top-level function (or method) that the compilers cannot take in
place -- it rebinds a captured name with `nonlocal`, changes a captured container (`seen[u] = True`,
`order.append(u)`), calls a sibling nested function, is decorated with `functools.cache` /
`lru_cache`, or is handed to `sorted`/`min`/`max`/`.sort` as `key=`, to `map`/`filter`, or to
`functools.cmp_to_key` -- is lambda-lifted here, as a rewrite of the program text:

    def main():                              def main():
        seen = [False] * n                       seen = [False] * n
        def dfs(u: int) -> None:     ==>         _ail_env = _AilEnv_main(seen)
            seen[u] = True                       main__dfs(_ail_env, 0)
            ...                                  print(sum(_ail_env.seen))
        dfs(0)
        print(sum(seen))                     class _AilEnv_main:  # one field per shared name
                                                 def __init__(self, seen: list[bool]): self.seen = seen
                                             def main__dfs(_ail_env: _AilEnv_main, u: int) -> None:
                                                 _ail_env.seen[u] = True ...

The names the nested functions rebind or change live in one environment object per activation of the
enclosing function, created just before the first statement that refers to a nested function; from there
on every read and write of those names, in the enclosing function and in the nested ones, goes through it.
This is CPython's cell semantics for a closure that does not outlive its enclosing call: a `nonlocal` write
is seen by the enclosing function, and a nested function sees the current value of a name, not the value
it had when the `def` ran (late binding). The names a nested function only reads are passed as leading
arguments at each call, which gives the current value too. A cached nested function gets its own memo
dict in the environment, so every activation of the enclosing function has a fresh cache, as CPython's
`lru_cache` applied to a fresh function object does.

The field annotations of the environment come from the program's own annotations and initializers
(`[False] * n`, `[]` with its appends, `0`); a field whose type cannot be told is left unannotated and the
typed path refuses it by name (the general path does not need the annotation). A nested function that
escapes (returned, stored, assigned to another name, passed elsewhere), one inside a loop or an `if`, one
inside another nested function, and the other shapes listed in `_liftable` are left as written for the
compilers' own handling. Generated definitions are appended at the end of the text, so every original
line keeps its number.
"""
import ast
import os
import sys
import io
import re
import tokenize

MUTATORS = frozenset(('append', 'extend', 'insert', 'pop', 'remove', 'clear', 'sort', 'reverse', 'add',
                      'discard', 'update', 'setdefault', 'popitem', 'difference_update',
                      'intersection_update', 'symmetric_difference_update', 'appendleft', 'popleft',
                      'extendleft', 'rotate'))
MUTATING_FUNCS = frozenset(('heappush', 'heappop', 'heapify', 'heapreplace', 'heappushpop', 'insort',
                            'insort_left', 'insort_right', 'shuffle'))
CALLBACK_KEYS = frozenset(('sorted', 'min', 'max', 'sort', 'nlargest', 'nsmallest'))
ENV = '_ail_env'
_INNER_DEF = re.compile(r'^[ \t]+def\s', re.M)


class _Skip(Exception):
    """This enclosing function is left as written."""


def rewrite(source, notes=None):
    """The program with its nested functions lifted where that is needed; the text as written otherwise."""
    if not _INNER_DEF.search(source):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    try:
        return _Program(source, tree).run()
    except (_Skip, AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError):
        return source


def _first_hop(node):
    """'attr' when the access chain `node` starts at its name with an attribute (`x.f[...]`)."""
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        if isinstance(node.value, ast.Name):
            return 'attr' if isinstance(node, ast.Attribute) else 'item'
        node = node.value
    return None


def _base_name(node):
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _stores(node):
    """Names bound anywhere in `node` (not entering nested functions, lambdas or comprehensions)."""
    out = set()

    def walk(n):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split('.')[0])
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
            return
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return
        for c in ast.iter_child_nodes(n):
            walk(c)
    for s in (node if isinstance(node, list) else [node]):
        walk(s)
    return out


def _free_names(fn):
    """Names `fn` reads or writes that are not its own locals, with the names it declares nonlocal."""
    params = {a.arg for a in fn.args.args + fn.args.posonlyargs + fn.args.kwonlyargs}
    if fn.args.vararg:
        params.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        params.add(fn.args.kwarg.arg)
    nonlocal_names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Nonlocal):
            nonlocal_names.update(n.names)
    own = (params | _stores(fn.body)) - nonlocal_names
    free = []
    for n in _scoped_names(fn.body, set()):
        if n.id not in own and n.id not in free:
            free.append(n.id)
    return free, own, nonlocal_names


def _scoped_names(stmts, bound):
    """Every Name node in `stmts` that refers to the enclosing scope: names bound by a comprehension,
    a lambda's parameters or a nested def are not yielded inside that construct."""
    out = []

    def walk(n, hidden):
        if isinstance(n, ast.Name):
            if n.id not in hidden:
                out.append(n)
            return
        if isinstance(n, ast.Lambda):
            inner = hidden | {a.arg for a in n.args.args + n.args.kwonlyargs + n.args.posonlyargs}
            for d in n.args.defaults + n.args.kw_defaults:
                if d is not None:
                    walk(d, hidden)
            walk(n.body, inner)
            return
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = set(hidden)
            for g in n.generators:
                walk(g.iter, inner if g is not n.generators[0] else hidden)
                inner |= {t.id for t in ast.walk(g.target) if isinstance(t, ast.Name)}
                for c in g.ifs:
                    walk(c, inner)
            if isinstance(n, ast.DictComp):
                walk(n.key, inner)
                walk(n.value, inner)
            else:
                walk(n.elt, inner)
            return
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        for c in ast.iter_child_nodes(n):
            walk(c, hidden)
    for s in stmts:
        walk(s, bound)
    return out


class _Program:
    def __init__(self, source, tree):
        self.source = source
        self.tree = tree
        self.lines = source.split('\n')
        self.edits = []          # (line index, byte start, byte end, text)
        self.appended = []
        self.taken = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name):
                self.taken.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                self.taken.add(n.name)
            elif isinstance(n, ast.arg):
                self.taken.add(n.arg)
        self.functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        self.multiline_strings = self._multiline_string_lines()

    def fresh(self, base):
        name, k = base, 1
        while name in self.taken:
            k += 1
            name = '%s_%d' % (base, k)
        self.taken.add(name)
        return name

    def _multiline_string_lines(self):
        lines = set()
        try:
            for tok in tokenize.generate_tokens(io.StringIO(self.source).readline):
                if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
                    lines.update(range(tok.start[0], tok.end[0] + 1))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            raise _Skip()
        return lines

    def run(self):
        outers = []
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                outers.append((node, None))
            elif isinstance(node, ast.ClassDef):
                outers.extend((m, node) for m in node.body if isinstance(m, ast.FunctionDef))
        changed = False
        for outer, owner in outers:
            if not any(isinstance(s, ast.FunctionDef) for s in outer.body):
                continue
            saved = (len(self.edits), len(self.appended), set(self.taken))
            try:
                if _Outer(self, outer, owner).lift():
                    changed = True
            except _Skip:
                if os.environ.get('AIL_NESTFN_DEBUG'):
                    import traceback
                    print('nestfn: %s left as written:\n%s' % (outer.name, traceback.format_exc(limit=-1)), file=sys.stderr)
                del self.edits[saved[0]:]
                del self.appended[saved[1]:]
                self.taken = saved[2]
        if not changed:
            return self.source
        return self.render()

    def edit(self, lineno, col, end_col, text):
        self.edits.append((lineno - 1, col, end_col, text))

    def node_edit(self, node, text):
        if node.lineno != node.end_lineno:
            raise _Skip()
        self.edit(node.lineno, node.col_offset, node.end_col_offset, text)

    def render(self):
        lines = [l.encode('utf-8') for l in self.lines]
        by_line = {}
        for i, a, b, t in self.edits:
            by_line.setdefault(i, []).append((a, b, t))
        for i, edits in by_line.items():
            edits.sort(key=lambda e: (e[0], e[1]))
            for (a1, b1, _), (a2, b2, _) in zip(edits, edits[1:]):
                if a2 < b1:
                    raise _Skip()
            line = lines[i]
            for a, b, t in sorted(edits, key=lambda e: (-e[0], -e[1])):
                line = line[:a] + t.encode('utf-8') + line[b:]
            lines[i] = line
        text = '\n'.join(l.decode('utf-8') for l in lines).rstrip('\n') + '\n'
        return text + ''.join('\n\n' + block.rstrip('\n') + '\n' for block in self.appended)


class _Outer:
    def __init__(self, prog, outer, owner):
        self.prog = prog
        self.outer = outer
        self.owner = owner
        self.fname = ('%s_%s' % (owner.name, outer.name)) if owner else outer.name

    # -- what may be lifted ---------------------------------------------------------------------------
    def lift(self):
        outer = self.outer
        inners = [s for s in outer.body if isinstance(s, ast.FunctionDef)]
        inner_ids = {id(s) for s in inners}
        names = {i.name for i in inners}
        if len(names) != len(inners):
            raise _Skip()
        for n in ast.walk(outer):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not outer and id(n) not in inner_ids:
                raise _Skip()        # a def in a loop, an if, or inside a nested def: not lifted here
            if isinstance(n, ast.ClassDef) or isinstance(n, ast.AsyncFunctionDef):
                raise _Skip()
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('locals', 'vars', 'exec', 'eval'):
                raise _Skip()
            if isinstance(n, ast.Global) and set(n.names) & names:
                raise _Skip()
        self.inners = inners
        self.names = names
        for inner in inners:
            self._check_inner(inner)
        # the enclosing function's own names (its body without the nested defs)
        rest = [s for s in outer.body if id(s) not in inner_ids]
        if not rest:
            raise _Skip()
        params = {a.arg for a in outer.args.args + outer.args.posonlyargs + outer.args.kwonlyargs}
        if outer.args.vararg:
            params.add(outer.args.vararg.arg)
        if outer.args.kwarg:
            params.add(outer.args.kwarg.arg)
        outer_bound = params | _stores(rest)
        if outer_bound & names:
            raise _Skip()            # the enclosing function rebinds a nested function's name
        self.outer_bound = outer_bound
        self.rest = rest
        info = {}
        for inner in inners:
            free, own, nonlocal_names = _free_names(inner)
            if own & names:
                raise _Skip()
            if nonlocal_names - outer_bound:
                raise _Skip()
            captured = [f for f in free if f in outer_bound]
            info[inner.name] = {'node': inner, 'captured': captured, 'own': own, 'nonlocal': nonlocal_names,
                                'calls': set(), 'mutates': set(), 'cache': self._cache(inner)}
        # uses of the nested functions' names: calls, callbacks, anything else escapes
        self.callbacks = []      # (Name node, arity)
        self.calls = []          # Call nodes
        for scope, stmts in [(None, rest)] + [(i.name, i.body) for i in inners]:
            for node, parent, grand in self._walk_parents(stmts):
                if not (isinstance(node, ast.Name) and node.id in names):
                    continue
                if scope is not None and node.id in info[scope]['own']:
                    continue
                if isinstance(parent, ast.Call) and parent.func is node:
                    if any(isinstance(a, ast.Starred) for a in parent.args) or any(k.arg is None for k in parent.keywords):
                        raise _Skip()
                    self.calls.append((scope, parent))
                    if scope is not None:
                        info[scope]['calls'].add(node.id)
                    continue
                arity = self._callback_arity(node, parent, grand)
                if arity is None:
                    raise _Skip()    # escapes as a value: left for the compilers
                self.callbacks.append((scope, node, arity))
                if scope is not None:
                    info[scope]['calls'].add(node.id)
        # what each nested function changes among the names it shares with the enclosing function
        self.info = info
        infer = _Infer(self)
        for name, row in info.items():
            through_field = set()
            for n in ast.walk(row['node']):
                base = None
                if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                    targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                    for t in targets:
                        for e in ast.walk(t):
                            if isinstance(e, (ast.Subscript, ast.Attribute)) and isinstance(e.ctx, (ast.Store, ast.Del)):
                                b = _base_name(e)
                                if b:
                                    row['mutates'].add(b)
                                    if _first_hop(e) == 'attr':
                                        through_field.add(b)
                elif isinstance(n, ast.Call):
                    f = n.func
                    if isinstance(f, ast.Attribute) and f.attr in MUTATORS:
                        base = _base_name(f.value)
                        if base and _first_hop(f) == 'attr' and not isinstance(f.value, ast.Name):
                            through_field.add(base)
                    elif isinstance(f, ast.Name) and f.id in MUTATING_FUNCS and n.args:
                        base = _base_name(n.args[0])
                    elif isinstance(f, ast.Attribute) and f.attr in MUTATING_FUNCS and n.args:
                        base = _base_name(n.args[0])
                    if base:
                        row['mutates'].add(base)
                    if isinstance(f, ast.Name) and (f.id in self.prog.functions or f.id in self.prog.classes):
                        for a in n.args:
                            b = _base_name(a)
                            if b:
                                row['mutates'].add(b)
            row['mutates'] = {m for m in row['mutates'] if m in row['captured'] and m not in row['own']}
            # an instance of a class of the program is a reference on both paths: a change of one of
            # its fields needs no shared environment
            for m in list(row['mutates']):
                if m in through_field and infer.name_type(m) in self.prog.classes:
                    row['mutates'].discard(m)
        needs = any(row['nonlocal'] or row['mutates'] or row['calls'] - {name} or row['cache']
                    for name, row in info.items()) or self.callbacks
        if not needs:
            # a captured str, container or instance is passed as an annotated argument here, which
            # the typed path's own lifting (scalars only, unannotated) does not do
            needs = any(infer.name_type(c) not in (None, 'int', 'float', 'bool')
                        for row in info.values() for c in row['captured'])
        if not needs:
            return False
        self._plan()
        self._emit()
        return True

    def _check_inner(self, inner):
        a = inner.args
        if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs:
            raise _Skip()
        if any(not isinstance(d, ast.Constant) for d in a.defaults):
            raise _Skip()
        for n in ast.walk(inner):
            if isinstance(n, ast.Global):
                raise _Skip()
            if isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)):
                raise _Skip()
        for line in range(inner.lineno, inner.end_lineno + 1):
            if line in self.prog.multiline_strings:
                doc = (inner.body and isinstance(inner.body[0], ast.Expr) and isinstance(inner.body[0].value, ast.Constant)
                       and isinstance(inner.body[0].value.value, str) and inner.body[0].lineno <= line <= inner.body[0].end_lineno)
                if not doc:
                    raise _Skip()
        if inner.decorator_list and not self._cache(inner):
            raise _Skip()

    def _cache(self, inner):
        """None, or (maxsize-is-None, decorator) for a functools cache decorator."""
        if not inner.decorator_list:
            return None
        if len(inner.decorator_list) != 1:
            raise _Skip()
        d = inner.decorator_list[0]
        target = d.func if isinstance(d, ast.Call) else d
        text = ast.unparse(target)
        if text not in ('cache', 'lru_cache', 'functools.cache', 'functools.lru_cache'):
            raise _Skip()
        unbounded = text.endswith('cache') and not text.endswith('lru_cache')
        if isinstance(d, ast.Call):
            if any(k.arg not in ('maxsize', 'typed') for k in d.keywords):
                raise _Skip()
            vals = list(d.args) + [k.value for k in d.keywords if k.arg == 'maxsize']
            if vals:
                v = vals[0]
                if not isinstance(v, ast.Constant) or not (v.value is None or type(v.value) is int):
                    raise _Skip()
                if v.value == 0:
                    raise _Skip()
                unbounded = v.value is None
        return (unbounded, d)

    @staticmethod
    def _walk_parents(stmts):
        out = []

        def walk(n, parent, grand):
            out.append((n, parent, grand))
            for c in ast.iter_child_nodes(n):
                walk(c, n, parent)
        for s in stmts:
            walk(s, None, None)
        return out

    def _callback_arity(self, node, parent, grand):
        """The number of arguments a nested function handed over as a callback is called with, or None
        when it is used any other way."""
        if isinstance(parent, ast.keyword) and parent.arg == 'key' and isinstance(grand, ast.Call):
            f = grand.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if fname in CALLBACK_KEYS:
                return 1
            return None
        if isinstance(parent, ast.Call) and node in parent.args:
            f = parent.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if fname in ('map', 'filter') and parent.args[0] is node:
                return len(parent.args) - 1 if fname == 'map' else 1
            if fname == 'cmp_to_key' and len(parent.args) == 1:
                return 2
        return None

    # -- planning ---------------------------------------------------------------------------------------
    def _plan(self):
        info = self.info
        # names that live in the environment: rebound with nonlocal, or changed, by some nested function
        ref = set()
        for row in info.values():
            ref |= row['nonlocal'] | row['mutates']
        # a nested function passes on what the nested functions it calls need
        changed = True
        while changed:
            changed = False
            for name, row in info.items():
                for callee in row['calls']:
                    if callee == name:
                        continue
                    for c in info[callee]['captured']:
                        if c not in row['captured']:
                            row['captured'].append(c)
                            changed = True
                    if info[callee]['cache'] and not row.get('needs_env'):
                        row['needs_env'] = True
                        changed = True
        for name, row in info.items():
            for c in row['captured']:
                if c in row['own'] and c not in row['nonlocal']:
                    ref.add(c)       # a callee needs the enclosing value of a name this function rebinds
        memo = {}
        for name, row in info.items():
            if row['cache']:
                memo[name] = self._memo_plan(row)
        self.memo = memo
        self.ref = sorted(ref, key=lambda n: self._first_line(n))
        self.has_env = bool(self.ref or memo)
        for name, row in info.items():
            row['vals'] = [c for c in row['captured'] if c not in ref]
            row['env'] = bool(memo.get(name)) or any(c in ref for c in row['captured'])
        # a nested function takes the environment when it, or one it calls, uses it
        changed = True
        while changed:
            changed = False
            for name, row in info.items():
                if not row['env'] and any(info[c]['env'] for c in row['calls'] if c != name):
                    row['env'] = changed = True
        # where the environment is created: before the first statement that refers to a nested function
        P = None
        for k, stmt in enumerate(self.rest):
            if any(isinstance(n, ast.Name) and n.id in self.names for n in ast.walk(stmt)):
                P = k
                break
        if P is None:
            P = len(self.rest)       # never called: no environment is created
        self.P = P
        before = set(a.arg for a in self.outer.args.args + self.outer.args.posonlyargs + self.outer.args.kwonlyargs)
        before |= _stores(self.rest[:P])
        # a shared name the enclosing function binds only after that statement starts as the empty
        # value of its type; the binding itself is a store into the environment
        self.late = [r for r in self.ref if r not in before]
        # forms the renaming does not cover
        for stmt in self.rest[P:]:
            for n in ast.walk(stmt):
                if isinstance(n, (ast.Global, ast.Nonlocal)) and set(n.names) & ref:
                    raise _Skip()
                if isinstance(n, (ast.For, ast.comprehension)) and any(
                        isinstance(t, ast.Name) and t.id in ref for t in ast.walk(n.target)):
                    raise _Skip()
                if isinstance(n, ast.withitem) and n.optional_vars is not None and any(
                        isinstance(t, ast.Name) and t.id in ref for t in ast.walk(n.optional_vars)):
                    raise _Skip()
                if isinstance(n, ast.ExceptHandler) and n.name in ref:
                    raise _Skip()
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id in ref:
                    raise _Skip()
                if isinstance(n, ast.NamedExpr) and n.target.id in ref:
                    raise _Skip()
                if isinstance(n, ast.Delete) and any(isinstance(t, ast.Name) and t.id in ref for t in n.targets):
                    raise _Skip()
        for name, row in info.items():
            for n in ast.walk(row['node']):
                if isinstance(n, (ast.For, ast.comprehension)) and any(
                        isinstance(t, ast.Name) and t.id in ref and (t.id in row['nonlocal'] or t.id not in row['own'])
                        for t in ast.walk(n.target)):
                    raise _Skip()
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id in row['nonlocal']:
                    raise _Skip()
                if isinstance(n, ast.NamedExpr) and n.target.id in row['nonlocal']:
                    raise _Skip()
        self.lifted = {name: self.prog.fresh('%s__%s' % (self.fname, name)) for name in info}
        self.env_class = self.prog.fresh('_AilEnv_' + self.fname) if self.has_env else None
        if self.has_env:
            self.prog.taken.add(ENV)

    def _first_line(self, name):
        for n in ast.walk(self.outer):
            if isinstance(n, ast.Name) and n.id == name:
                return (n.lineno, n.col_offset)
            if isinstance(n, ast.arg) and n.arg == name:
                return (n.lineno, n.col_offset)
        return (0, 0)

    def _memo_plan(self, row):
        inner = row['node']
        unbounded, _ = row['cache']
        keys = []
        for a in inner.args.args:
            t = ast.unparse(a.annotation) if a.annotation is not None else None
            if t not in ('int', 'str', 'bool'):
                raise _Skip()
            keys.append((a.arg, t))
        if not keys or inner.args.defaults:
            raise _Skip()
        ret = ast.unparse(inner.returns) if inner.returns is not None else None
        if ret not in ('int', 'float', 'str'):
            raise _Skip()
        if not unbounded:
            # the size bound changes nothing only when the result depends on the arguments alone
            if row['nonlocal'] or row['mutates'] or row['calls'] - {inner.name}:
                raise _Skip()
            late = _stores([s for s in self.outer.body if getattr(s, 'lineno', 0) > inner.end_lineno])
            if set(row['captured']) & late:
                raise _Skip()
            for c in row['captured']:
                for other in self.info.values():
                    if c in other['mutates'] or c in other['nonlocal']:
                        raise _Skip()
        for n in ast.walk(self.outer):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == inner.name:
                raise _Skip()        # cache_info() / cache_clear()
        if len(keys) == 1 and keys[0][1] in ('int', 'str'):
            ktype, kexpr = keys[0][1], keys[0][0]
        else:
            parts = []
            for nm, t in keys:
                parts.append('str(len(%s)) + ":" + %s' % (nm, nm) if t == 'str' else 'str(%s)' % nm)
            ktype, kexpr = 'str', ' + "," + '.join(parts)
        field = self.prog.fresh('_ail_memo_' + inner.name)
        return {'field': field, 'ktype': ktype, 'kexpr': kexpr, 'ret': ret}

    # -- the field types ----------------------------------------------------------------------------------
    def _field_types(self):
        inf = _Infer(self)
        out = {}
        for r in self.ref:
            out[r] = inf.name_type(r)
        return out

    def _val_param(self, name):
        """A leading parameter for a name passed by value, annotated when its type can be told."""
        if not hasattr(self, '_val_types'):
            self._val_types = {}
        if name not in self._val_types:
            self._val_types[name] = _Infer(self).name_type(name)
        t = self._val_types[name]
        return '%s: %s' % (name, t) if t else name

    # -- emitting -----------------------------------------------------------------------------------------
    def _call_prefix(self, callee, scope):
        args = []
        if self.has_env and self.info[callee]['env']:
            args.append(ENV)
        args.extend(self.info[callee]['vals'])
        return args

    def _emit(self):
        prog = self.prog
        info = self.info
        ref = set(self.ref)
        # 1. the calls and callbacks
        for scope, call in self.calls:
            callee = call.func.id
            prefix = self._call_prefix(callee, scope)
            prog.node_edit(call.func, self.lifted[callee])
            if prefix:
                text = ', '.join(prefix) + (', ' if call.args or call.keywords else '')
                self._insert_after_paren(call, text)
        for scope, node, arity in self.callbacks:
            callee = node.id
            row = info[callee]
            nparams = len(row['node'].args.args)
            if nparams - len(row['node'].args.defaults) > arity or arity > nparams:
                raise _Skip()
            prefix = self._call_prefix(callee, scope)
            params = ['_ail_a%d' % k for k in range(arity)]
            if prefix:
                text = '(lambda %s: %s(%s))' % (', '.join(params), self.lifted[callee], ', '.join(prefix + params))
            else:
                text = self.lifted[callee]
            prog.node_edit(node, text)
        # 2. the enclosing function: the environment and the shared names after it
        if self.has_env:
            types = self._field_types()
            fields = [(r, types.get(r)) for r in self.ref]
            # (no type: None, which only the general path takes; the typed path refuses the field by name)
            init_args = [(_empty_value(types.get(r)) or 'None') if r in self.late else r for r in self.ref]
            for name, m in self.memo.items():
                fields.append((m['field'], 'dict[%s, %s]' % (m['ktype'], m['ret'])))
                init_args.append('{}')
            params = ', '.join('%s: %s' % (f, t) if t else f for f, t in fields)
            this = 'self' if 'self' not in self.ref else '_ail_this'
            body = '\n'.join('        %s.%s = %s' % (this, f, f) for f, _ in fields)
            unknown = [f for f, t in fields if not t]
            doc = ''
            if unknown:
                inner_of = {}
                for name, row in info.items():
                    for u in unknown:
                        if u in row['mutates'] or u in row['nonlocal']:
                            inner_of.setdefault(u, name)
                doc = '    """nested: %s"""\n' % ', '.join('%s=%s' % (u, inner_of.get(u, '?')) for u in unknown)
            prog.appended.append('class %s:\n%s    def __init__(%s, %s):\n%s\n' % (self.env_class, doc, this, params, body))
            create = '%s = %s(%s)' % (ENV, self.env_class, ', '.join(init_args))
            env_line = self._insert_env(create) if self.P < len(self.rest) else None
        else:
            env_line = None
        if self.has_env:
            for stmt in self.rest[self.P:]:
                for n in _scoped_names([stmt], set()):
                    if n.id in ref:
                        prog.node_edit(n, '%s.%s' % (ENV, n.id))
        # 3. the nested definitions: blanked where they were, appended as module functions
        lines = prog.lines
        for name, row in info.items():
            inner = row['node']
            start = (inner.decorator_list[0].lineno if inner.decorator_list else inner.lineno)
            local_edits = []
            for n in _scoped_names(inner.body, set()):
                if n.id in ref and (n.id in row['nonlocal'] or n.id not in row['own']):
                    local_edits.append((n.lineno, n.col_offset, n.end_col_offset, '%s.%s' % (ENV, n.id)))
            for n in ast.walk(inner):
                if isinstance(n, ast.Nonlocal):
                    if n.lineno != n.end_lineno:
                        raise _Skip()
                    local_edits.append((n.lineno, n.col_offset, n.end_col_offset, 'pass'))
            # move the edits recorded so far inside this def into the lifted copy
            mine = [e for e in prog.edits if start - 1 <= e[0] <= inner.end_lineno - 1]
            prog.edits = [e for e in prog.edits if not (start - 1 <= e[0] <= inner.end_lineno - 1)]
            local_edits.extend((i + 1, a, b, t) for i, a, b, t in mine)
            # header: def name(  ->  def lifted(env: Env, vals...,
            head_line = inner.lineno
            raw = lines[head_line - 1].encode('utf-8')
            found = re.compile(rb'def\s+' + re.escape(name.encode()) + rb'\s*\(').search(raw, inner.col_offset)
            if not found:
                raise _Skip()
            lead = []
            if self.has_env and row['env']:
                lead.append('%s: %s' % (ENV, self.env_class))
            lead.extend(self._val_param(v) for v in row["vals"])
            text = 'def %s(' % self.lifted[name] + (', '.join(lead) + (', ' if inner.args.args else '') if lead else '')
            local_edits.append((head_line, found.start(), found.end(), text))
            if row['cache']:
                d = row['cache'][1]
                if d.lineno != d.end_lineno:
                    raise _Skip()
                local_edits.append((d.lineno, d.col_offset - 1, d.end_col_offset, ''))
            block = self._apply(start, inner.end_lineno, local_edits, inner.col_offset)
            if row['cache']:
                block = self._memo_wrap(name, row, block)
            prog.appended.append(block)
            for ln in range(start, inner.end_lineno + 1):
                text = env_line[1] if env_line and env_line[0] == ln else ''
                prog.edits.append((ln - 1, 0, len(lines[ln - 1].encode('utf-8')), text))

    def _insert_after_paren(self, call, text):
        """Insert `text` right after the opening parenthesis of `call`."""
        f = call.func
        line = self.prog.lines[f.end_lineno - 1].encode('utf-8')
        k = f.end_col_offset
        while k < len(line) and line[k:k + 1] in (b' ', b'\t'):
            k += 1
        if line[k:k + 1] != b'(':
            raise _Skip()
        self.prog.edit(f.end_lineno, k + 1, k + 1, text)

    def _insert_env(self, create):
        """Where the statement creating the environment goes: a line that holds no statement between
        the last statement before the first use and that use (a blank line, a comment, or a line of a
        nested def, which is blanked), so no line moves; else in front of the first use on its line;
        else on a new line. Returns (line, whole-line text) for a line of a nested def, else None."""
        prog = self.prog
        stmt = self.rest[self.P]
        indent = stmt.col_offset
        prev_end = None
        for s in self.outer.body:
            if s is stmt:
                break
            if s not in self.inners:
                prev_end = s.end_lineno
        if prev_end is None:
            prev_end = self.outer.body[0].lineno - 1
            first = self.outer.body[0]
            if first in self.inners and first.decorator_list:
                prev_end = first.decorator_list[0].lineno - 1
        inner_lines = set()
        for i in self.inners:
            start = i.decorator_list[0].lineno if i.decorator_list else i.lineno
            inner_lines.update(range(start, i.end_lineno + 1))
        for ln in range(prev_end + 1, stmt.lineno):
            if ln in prog.multiline_strings and ln not in inner_lines:
                continue
            text = prog.lines[ln - 1]
            if ln in inner_lines:
                return (ln, ' ' * indent + create)
            if not text.strip() or text.strip().startswith('#'):
                prog.edits.append((ln - 1, 0, len(text.encode('utf-8')), ' ' * indent + create))
                return None
        simple = (ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Return, ast.Pass, ast.Raise,
                  ast.Assert, ast.Delete, ast.Import, ast.ImportFrom)
        prev = None
        for s in self.outer.body:
            if s is stmt:
                break
            if s not in self.inners:
                prev = s
        if (prev is not None and isinstance(prev, simple) and prev.lineno == prev.end_lineno
                and prev.end_lineno < stmt.lineno):
            # after the last statement before the first use, on its line
            prog.edit(prev.end_lineno, prev.end_col_offset, prev.end_col_offset, '; ' + create)
            return None
        if isinstance(stmt, simple) and stmt.lineno == stmt.end_lineno:
            prog.edit(stmt.lineno, stmt.col_offset, stmt.col_offset, create + '; ')
            return None
        # no free line: a new one (the lines below shift by one)
        prog.edit(stmt.lineno, 0, 0, ' ' * indent + create + '\n')
        return None

    def _apply(self, start, end, edits, indent):
        lines = [self.prog.lines[ln - 1].encode('utf-8') for ln in range(start, end + 1)]
        by = {}
        for ln, a, b, t in edits:
            by.setdefault(ln, []).append((a, b, t))
        for ln, es in by.items():
            es.sort()
            for (a1, b1, _), (a2, b2, _) in zip(es, es[1:]):
                if a2 < b1:
                    raise _Skip()
            line = lines[ln - start]
            for a, b, t in sorted(es, key=lambda e: (-e[0], -e[1])):
                line = line[:a] + t.encode('utf-8') + line[b:]
            lines[ln - start] = line
        out = []
        pad = b' ' * indent
        for k, line in enumerate(lines):
            if line.startswith(pad):
                line = line[indent:]
            elif line.strip():
                if (start + k) in self.prog.multiline_strings:
                    line = line.lstrip(b' ')
                else:
                    raise _Skip()
            out.append(line.decode('utf-8'))
        return '\n'.join(out) + '\n'

    def _memo_wrap(self, name, row, block):
        m = self.memo[name]
        lifted = self.lifted[name]
        body_name = self.prog.fresh(lifted + '__body')
        block = re.sub(r'^def %s\(' % re.escape(lifted), 'def %s(' % body_name, block, count=1, flags=re.M)
        inner = row['node']
        lead = ['%s: %s' % (ENV, self.env_class)]
        lead.extend(self._val_param(v) for v in row["vals"])
        params = ['%s: %s' % (a.arg, ast.unparse(a.annotation)) for a in inner.args.args]
        call = ', '.join([ENV] + row['vals'] + [a.arg for a in inner.args.args])
        memo = '%s.%s' % (ENV, m['field'])
        wrapper = ('def %s(%s) -> %s:\n'
                   '    _ail_k = %s\n'
                   '    if _ail_k in %s:\n'
                   '        return %s[_ail_k]\n'
                   '    _ail_v = %s(%s)\n'
                   '    %s[_ail_k] = _ail_v\n'
                   '    return _ail_v\n') % (lifted, ', '.join(lead + params), m['ret'], m['kexpr'], memo, memo,
                                             body_name, call, memo)
        return wrapper + '\n\n' + block


class _Infer:
    """Annotation text for a name of the enclosing function, from annotations and initializers."""

    def __init__(self, lifted):
        self.l = lifted
        self.outer = lifted.outer
        self.busy = set()

    def name_type(self, name, scope=None):
        if scope is not None and name in scope:
            return scope[name]
        if name in self.busy:
            return None
        self.busy.add(name)
        try:
            t = self._name_type(name)
            return None if t is not None and '?' in t else t
        finally:
            self.busy.discard(name)

    def _name_type(self, name):
        outer = self.outer
        for k, a in enumerate(outer.args.args):
            if a.arg == name:
                if a.annotation is not None:
                    return ast.unparse(a.annotation)
                if k == 0 and self.l.owner is not None:
                    return self.l.owner.name
                return None
        anns = [n for n in ast.walk(outer) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                and n.target.id == name and self._in_outer(n)]
        if anns:
            texts = {ast.unparse(n.annotation) for n in anns}
            return texts.pop() if len(texts) == 1 else None
        values = []
        for n in ast.walk(outer):
            if isinstance(n, ast.Assign) and self._in_outer(n):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        values.append(n.value)
                    elif isinstance(t, (ast.Tuple, ast.List)) and any(isinstance(e, ast.Name) and e.id == name for e in t.elts):
                        k = next(i for i, e in enumerate(t.elts) if isinstance(e, ast.Name) and e.id == name)
                        if isinstance(n.value, (ast.Tuple, ast.List)) and len(n.value.elts) == len(t.elts) \
                                and not any(isinstance(e, ast.Starred) for e in t.elts):
                            values.append(n.value.elts[k])
                        else:
                            return None
            elif isinstance(n, (ast.For, ast.comprehension)) and self._in_outer(n) and any(
                    isinstance(e, ast.Name) and e.id == name for e in ast.walk(n.target)):
                return None
        if not values:
            return None
        types = [self.expr_type(v, {}) for v in values]
        hole = [t for t in types if t and '?' in t]
        full = [t for t in types if t and '?' not in t]
        if any(t is None for t in types):
            # a later binding whose type is not told (`acc = acc * 100`) agrees with the others or the
            # typed path refuses the store into the annotated field by name
            if not full or hole or 'bool' in full:
                return None
        if full:
            return full[0] if len(set(full)) == 1 else None
        shape = hole[0]
        if len(set(hole)) != 1:
            return None
        filled = self._fill(name, shape)
        return filled

    def _in_outer(self, node):
        for inner in self.l.inners:
            if inner.lineno <= getattr(node, 'lineno', 0) <= inner.end_lineno:
                return False
        return True

    def _fill(self, name, shape):
        """Resolve the `?` of `list[?]`, `set[?]`, `dict[?]`, `list[list[?]]` from the uses of `name`."""
        elems, keys, vals, rows = set(), set(), set(), set()
        for scope, stmts, rowinfo in self._scopes():
            env = self._scope_env(scope)
            for n in ast.walk(ast.Module(body=stmts, type_ignores=[])):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.args:
                    v = n.func.value
                    if isinstance(v, ast.Name) and v.id == name and self._refers(scope, name):
                        if n.func.attr in ('append', 'add', 'appendleft'):
                            elems.add(self.expr_type(n.args[0], env))
                        elif n.func.attr == 'insert' and len(n.args) == 2:
                            elems.add(self.expr_type(n.args[1], env))
                        elif n.func.attr == 'extend':
                            t = self.expr_type(n.args[0], env)
                            elems.add(_elem(t))
                    elif (isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id == name
                          and self._refers(scope, name) and n.func.attr in ('append', 'add')):
                        rows.add(self.expr_type(n.args[0], env))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('heappush', 'insort') \
                        and len(n.args) == 2 and isinstance(n.args[0], ast.Name) and n.args[0].id == name:
                    elems.add(self.expr_type(n.args[1], env))
                if isinstance(n, (ast.Assign, ast.AugAssign)):
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for t in targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == name \
                                and self._refers(scope, name) and not isinstance(t.slice, ast.Slice):
                            keys.add(self.expr_type(t.slice, env))
                            vals.add(self.expr_type(n.value, env))
        if shape == 'list[?]' or shape == 'set[?]':
            kind = shape[:shape.index('[')]
            if len(elems) == 1 and None not in elems:
                return '%s[%s]' % (kind, elems.pop())
            return None
        if shape == 'dict[?]':
            if len(keys) == 1 and len(vals) == 1 and None not in keys and None not in vals:
                return 'dict[%s, %s]' % (keys.pop(), vals.pop())
            return None
        if shape in ('list[list[?]]', 'list[set[?]]'):
            if len(rows) == 1 and None not in rows:
                return shape.replace('?', rows.pop())
            return None
        return None

    def _scopes(self):
        yield None, self.l.rest, None
        for inner in self.l.inners:
            yield inner, inner.body, None

    def _refers(self, scope, name):
        if scope is None:
            return True
        row = self.l.info[scope.name]
        return name in row['nonlocal'] or name not in row['own']

    def _scope_env(self, scope):
        env = {}
        if scope is None:
            return env
        for a in scope.args.args:
            if a.annotation is not None:
                env[a.arg] = ast.unparse(a.annotation)
        for n in ast.walk(scope):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                env[n.target.id] = ast.unparse(n.annotation)
        for n in ast.walk(scope):
            if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id not in env:
                t = _elem(self.expr_type(n.iter, env))
                if t:
                    env[n.target.id] = t
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                    and n.targets[0].id not in env:
                t = self.expr_type(n.value, env)
                if t and '?' not in t:
                    env[n.targets[0].id] = t
        return env

    def expr_type(self, e, env):
        if isinstance(e, ast.Constant):
            v = e.value
            if isinstance(v, bool):
                return 'bool'
            if isinstance(v, int):
                return 'int'
            if isinstance(v, float):
                return 'float'
            if isinstance(v, str):
                return 'str'
            return None
        if isinstance(e, ast.Name):
            if e.id in env:
                return env[e.id]
            if e.id in ('True', 'False'):
                return 'bool'
            return self.name_type(e.id)
        if isinstance(e, ast.BinOp):
            a, b = self.expr_type(e.left, env), self.expr_type(e.right, env)
            if isinstance(e.op, ast.Mult) and a and a.startswith('list[') and b in ('int', None):
                return a
            if isinstance(e.op, ast.Mult) and b and b.startswith('list[') and a in ('int', None):
                return b
            if isinstance(e.op, ast.Add) and a == b and a and (a.startswith('list[') or a == 'str'):
                return a
            if a in ('int', 'bool') and b in ('int', 'bool'):
                return 'float' if isinstance(e.op, ast.Div) else 'int'
            if a in ('int', 'float', 'bool') and b in ('int', 'float', 'bool'):
                return 'float'
            if a == 'str' and isinstance(e.op, ast.Mod):
                return 'str'
            if a == 'str' and isinstance(e.op, ast.Mult) and b == 'int':
                return 'str'
            return None
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return 'bool'
            t = self.expr_type(e.operand, env)
            if isinstance(e.op, ast.Invert):
                return 'int' if t in ('int', 'bool') else None
            return 'int' if t == 'bool' else t if t in ('int', 'float') else None
        if isinstance(e, ast.Compare):
            return 'bool'
        if isinstance(e, ast.BoolOp):
            ts = {self.expr_type(v, env) for v in e.values}
            return ts.pop() if len(ts) == 1 else None
        if isinstance(e, ast.IfExp):
            a, b = self.expr_type(e.body, env), self.expr_type(e.orelse, env)
            return a if a == b else None
        if isinstance(e, ast.Tuple):
            ts = [self.expr_type(x, env) for x in e.elts]
            if any(t is None for t in ts) or not ts:
                return None
            return 'tuple[%s]' % ', '.join(ts)
        if isinstance(e, ast.List):
            if not e.elts:
                return 'list[?]'
            ts = {self.expr_type(x, env) for x in e.elts}
            if len(ts) == 1:
                t = ts.pop()
                if t is None:
                    return None
                if t == 'list[?]':
                    return 'list[list[?]]'
                return None if '?' in t else 'list[%s]' % t
            return None
        if isinstance(e, ast.Dict):
            if not e.keys:
                return 'dict[?]'
            ks = {self.expr_type(k, env) for k in e.keys if k is not None}
            vs = {self.expr_type(v, env) for v in e.values}
            if len(ks) == 1 and len(vs) == 1 and None not in ks and None not in vs:
                return 'dict[%s, %s]' % (ks.pop(), vs.pop())
            return None
        if isinstance(e, ast.ListComp) and len(e.generators) == 1:
            g = e.generators[0]
            inner = dict(env)
            if isinstance(g.target, ast.Name):
                t = _elem(self.expr_type(g.iter, env))
                if t:
                    inner[g.target.id] = t
            t = self.expr_type(e.elt, inner)
            if t == 'list[?]':
                return 'list[list[?]]'
            if t == 'set[?]':
                return 'list[set[?]]'
            if t is None or '?' in t:
                return None
            return 'list[%s]' % t
        if isinstance(e, ast.Subscript):
            t = self.expr_type(e.value, env)
            if isinstance(e.slice, ast.Slice):
                return t if t and (t.startswith('list[') or t == 'str') else None
            if t == 'str':
                return 'str'
            if t and t.startswith('dict['):
                return _dict_value(t)
            if t and t.startswith('tuple[') and isinstance(e.slice, ast.Constant) and isinstance(e.slice.value, int):
                parts = _split_args(t[len('tuple['):-1])
                return parts[e.slice.value] if 0 <= e.slice.value < len(parts) else None
            return _elem(t)
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Name):
                n = f.id
                if n in ('int', 'len', 'ord', 'round') and n not in env:
                    return 'int'
                if n == 'float':
                    return 'float'
                if n in ('str', 'chr', 'repr'):
                    return 'str'
                if n == 'bool':
                    return 'bool'
                if n in ('abs',) and e.args:
                    return self.expr_type(e.args[0], env)
                if n in ('max', 'min') and e.args and not e.keywords:
                    if len(e.args) == 1:
                        return _elem(self.expr_type(e.args[0], env))
                    ts = {self.expr_type(a, env) for a in e.args}
                    if ts <= {'int', 'bool'}:
                        return 'int'
                    if ts <= {'int', 'float', 'bool'} and None not in ts:
                        return 'float'
                    return None
                if n == 'sum' and e.args:
                    t = _elem(self.expr_type(e.args[0], env))
                    return 'int' if t in ('int', 'bool') else t if t == 'float' else None
                if n == 'set' and not e.args:
                    return 'set[?]'
                if n == "dict" and not e.args and not e.keywords:
                    return 'dict[?]'
                if n == 'list' and not e.args:
                    return 'list[?]'
                if n in ('list', 'sorted') and e.args:
                    t = self.expr_type(e.args[0], env)
                    el = _elem(t)
                    return 'list[%s]' % el if el else None
                if n == 'set' and e.args:
                    el = _elem(self.expr_type(e.args[0], env))
                    return 'set[%s]' % el if el else None
                if n == 'range':
                    return 'range'
                if n in self.l.prog.functions:
                    r = self.l.prog.functions[n].returns
                    return ast.unparse(r) if r is not None and ast.unparse(r) != 'None' else None
                if n in self.l.prog.classes:
                    return n
                return None
            if isinstance(f, ast.Attribute):
                t = self.expr_type(f.value, env)
                if t == 'str':
                    if f.attr in ('strip', 'lstrip', 'rstrip', 'lower', 'upper', 'replace', 'join', 'format',
                                  'title', 'capitalize', 'zfill', 'ljust', 'rjust', 'center'):
                        return 'str'
                    if f.attr in ('split', 'splitlines', 'rsplit'):
                        return 'list[str]'
                    if f.attr in ('find', 'rfind', 'count', 'index'):
                        return 'int'
                    return None
                if f.attr == 'copy' and t:
                    return t
                if t and t.startswith('list[') and f.attr == 'pop':
                    return _elem(t)
                if isinstance(f.value, ast.Constant) and isinstance(f.value.value, str) and f.attr == 'join':
                    return 'str'
            return None
        return None


def _empty_value(t):
    """The value a shared name of type `t` holds before the enclosing function first binds it."""
    if t is None:
        return None
    simple = {'int': '0', 'float': '0.0', 'str': '""', 'bool': 'False'}
    if t in simple:
        return simple[t]
    if t.startswith('list['):
        return '[]'
    if t.startswith('set['):
        return 'set()'
    if t.startswith('dict['):
        return '{}'
    return None


def _split_args(text):
    parts, depth, cur = [], 0, ''
    for ch in text:
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _elem(t):
    if not t:
        return None
    if t == 'range':
        return 'int'
    if t == 'str':
        return 'str'
    for kind in ('list[', 'set['):
        if t.startswith(kind) and t.endswith(']'):
            inner = t[len(kind):-1]
            return None if '?' in inner else inner
    if t.startswith('dict[') and t.endswith(']'):
        parts = _split_args(t[len('dict['):-1])
        return parts[0] if len(parts) == 2 else None
    return None


def _dict_value(t):
    parts = _split_args(t[len('dict['):-1])
    return parts[1] if len(parts) == 2 else None
