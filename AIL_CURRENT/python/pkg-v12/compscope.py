"""Comprehension scopes: a comprehension's variable is local to the comprehension.

CPython 3 gives every list/set/dict comprehension and generator expression its own scope, so
`total = 5; xs = [total for total in range(3)]; print(total)` prints 5, and
`[[x for x in row] for row in rows]` or `[[i for i in range(i)] for i in ...]` read each `i` in the
scope where Python resolves it. The compiler's passes keep one flat name table per function, so the
comprehension variable would leak into (or collide with) the function's own variable of that name.

`rename` gives a comprehension variable a fresh identifier (`total__c1`) BEFORE any pass sees the
source, but only where a clash is possible: the same name is also used in the enclosing scope
outside the comprehension, or a comprehension nested inside it binds the same name. Every other
program is returned unchanged (the same string), so the generated C of existing programs does not
move. The source is edited token by token on its own line, so line numbers stay where they were.
`shadowing.restore_text` spells the fresh identifiers as the user wrote them in refusals.
"""
import ast
import re

_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _bound(comp):
    names = set()
    for generator in comp.generators:
        for node in ast.walk(generator.target):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


class _Scope(ast.NodeVisitor):
    """One function (or the module) body. `uses[id(name node)]` is the comprehension that binds the
    name there (None: the enclosing function scope); nested defs/lambdas/classes are separate scopes."""

    def __init__(self):
        self.stack = []             # enclosing comprehensions, innermost last
        self.resolved = []          # (Name node, binding comprehension or None)
        self.nested_clash = set()   # id(comp) that has a nested comprehension binding one of its names
        self.bound = {}             # id(comp) -> names it binds
        self.comps = {}             # id(comp) -> comp
        self.scope_names = set()    # names used in the enclosing scope proper
        self.class_bodies = []      # class definitions whose body is analysed separately

    def visit_Name(self, node):
        owner = None
        for comp in reversed(self.stack):
            if node.id in self.bound[id(comp)]:
                owner = comp
                break
        self.resolved.append((node, owner))
        if owner is None:
            self.scope_names.add(node.id)

    def visit_arg(self, node):
        self.scope_names.add(node.arg)

    def _visit_comp(self, comp):
        self.bound[id(comp)] = _bound(comp)
        self.comps[id(comp)] = comp
        # the first iterable is evaluated in the enclosing scope
        self.visit(comp.generators[0].iter)
        for outer in self.stack:
            if self.bound[id(outer)] & self.bound[id(comp)]:
                self.nested_clash.add(id(outer))
                self.nested_clash.add(id(comp))
        self.stack.append(comp)
        for index, generator in enumerate(comp.generators):
            self.visit(generator.target)
            if index:
                self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(comp, ast.DictComp):
            self.visit(comp.key)
            self.visit(comp.value)
        else:
            self.visit(comp.elt)
        self.stack.pop()

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _visit_comp

    def visit_FunctionDef(self, node):
        # decorators, defaults and annotations belong to this scope; the body is its own scope
        for expr in node.decorator_list:
            self.visit(expr)
        for expr in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            self.visit(expr)
        self.scope_names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        for expr in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            self.visit(expr)

    def visit_ClassDef(self, node):
        self.scope_names.add(node.name)
        self.class_bodies.append(node)


def _free_body(fn):
    """Names a lambda's body reads from outside the lambda. Argument defaults are excluded: they
    are evaluated in the enclosing scope, which this analysis rewrites, so they follow a rename."""
    args = fn.args
    own = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    if args.vararg:
        own.add(args.vararg.arg)
    if args.kwarg:
        own.add(args.kwarg.arg)
    found = set()

    def walk(n, hidden):
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load) and n.id not in hidden:
                found.add(n.id)
            return
        if isinstance(n, ast.NamedExpr):
            walk(n.value, hidden)
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    own.add(t.id)
            return
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                walk(d, hidden)
            found.update(_free_body(n))
            return
        if isinstance(n, _COMPS):
            inner = set(hidden)
            for k, g in enumerate(n.generators):
                walk(g.iter, inner if k else hidden)
                inner |= {t.id for t in ast.walk(g.target) if isinstance(t, ast.Name)}
                for c in g.ifs:
                    walk(c, inner)
            if isinstance(n, ast.DictComp):
                walk(n.key, inner)
                walk(n.value, inner)
            else:
                walk(n.elt, inner)
            return
        if isinstance(n, ast.ClassDef):
            return
        for c in ast.iter_child_nodes(n):
            walk(c, hidden)

    walk(fn.body, set())
    return found - own


def _lambda_loads(node):
    """Names read in the body of a lambda nested in `node` (not one nested in another lambda,
    whose body the enclosing lambda's scan already covers).  Its defaults are evaluated in the
    enclosing scope and rewritten there, so they do not decide this."""
    names = set()

    def walk(n):
        if isinstance(n, ast.Lambda):
            names.update(_free_body(n))
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                walk(d)
            return
        for c in ast.iter_child_nodes(n):
            walk(c)

    walk(node)
    return names


def _scopes(tree):
    """Every scope body to analyse: the module and each (possibly nested) function."""
    yield tree.body
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.body


def rename(source):
    """(source, {fresh: old}); `source` unchanged when no comprehension variable can clash."""
    if not re.search(r'\bfor\b', source):
        return source, {}
    stripped = source.strip()
    try:
        tree = ast.parse(stripped)
    except SyntaxError:
        return source, {}
    plans = []                  # (name node, new identifier)
    used = None
    counter = 0

    def analyse(body, outer_names, is_class=False):
        nonlocal used, counter
        scope = _Scope()
        scope.scope_names.update(outer_names)
        for statement in body:
            scope.visit(statement)
        keep = {}               # class-body comps whose target a nested lambda reads
        if is_class:
            for key, comp in scope.comps.items():
                keep[key] = _lambda_loads(comp) & scope.bound[key]
        if scope.comps:
            renames = {}        # (id(comp), name) -> fresh identifier
            for key, comp in scope.comps.items():
                for name in sorted(scope.bound[key]):
                    if name in keep.get(key, ()):     # leave the shared name for the closure pass
                        continue
                    if name in scope.scope_names or key in scope.nested_clash:
                        if used is None:
                            used = set(re.findall(r'\w+', source))
                        counter += 1
                        fresh = '%s__c%d' % (name, counter)
                        while fresh in used:
                            counter += 1
                            fresh = '%s__c%d' % (name, counter)
                        used.add(fresh)
                        renames[(key, name)] = fresh
            for node, owner in scope.resolved:
                if owner is not None and (id(owner), node.id) in renames:
                    plans.append((node, renames[(id(owner), node.id)]))
        for node in scope.class_bodies:
            analyse(node.body, scope.scope_names, is_class=True)

    for body in _scopes(tree):
        analyse(body, ())
    if not plans:
        return source, {}
    lines = stripped.split('\n')
    encoded = [line.encode('utf8') for line in lines]
    edits = {}
    for node, fresh in plans:
        old = node.id.encode('utf8')
        if encoded[node.lineno - 1][node.col_offset:node.col_offset + len(old)] != old:
            return source, {}   # cannot locate the token: leave the program as written
        edits.setdefault(node.lineno - 1, []).append((node.col_offset, old, fresh.encode('utf8')))
    for index, changes in edits.items():
        line = encoded[index]
        for column, old, new in sorted(set(changes), reverse=True):
            line = line[:column] + new + line[column + len(old):]
        lines[index] = line.decode('utf8')
    start = source.find(stripped)
    renamed = source[:start] + '\n'.join(lines) + source[start + len(stripped):]
    mapping = {}
    for node, fresh in plans:
        mapping[fresh] = node.id
    return renamed, mapping
