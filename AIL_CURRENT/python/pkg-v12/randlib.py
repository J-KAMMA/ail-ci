"""random.Random(seed) as a class (library batch 5, called from stdlib5).

`rng = random.Random(seed)` makes an object with its own Mersenne Twister state (prelude_random.py: CPython 3.12's
MT19937 and the methods built on it, bit for bit): `random randint randrange choice shuffle sample uniform gauss
getrandbits choices expovariate triangular seed`. Any number of generators, kept in variables, fields, lists or
passed to functions.

The typed path gets prelude_random_typed.py, the same class without method defaults (the typed class lowering
refuses them) and with randrange's one- and three-argument forms renamed by `_rewrite_randrange` to `randrange1` /
`randrange3`; the boxed class carries those names too. The typed class keeps random, getrandbits, randrange, randint,
choice, uniform, gauss and expovariate; shuffle, sample, choices and triangular stay on the general path.

A program that also calls the module-level functions (`random.seed(1)`, `random.randint(1, 6)`) keeps their state
apart from every `Random` object, as CPython does: they become calls of one hidden generator, `_ail_rng`, which the
program seeds with `random.seed(<int>)` (without a seed it starts from 0, where CPython starts from the OS).
When `random.seed` is the only module-level function used, the hidden generator is never read, so its creation
and the seed call are dropped (a module-level name bound to a constructor is not a typed module constant).
A program that only uses the module-level functions is not touched here (stdlib3 builds those on the typed path).

Not built, refused by name: `random.Random()` without a seed (not reproducible), a seed that is a str / bytes /
float / None (CPython hashes those), `random.SystemRandom`, `getstate` / `setstate`, `randbytes`, the other
distributions. getrandbits(k) beyond 63 bits is a RuntimeError (integers are 64-bit).
"""
import ast

import stdlib5
from stdlib4 import refuse

MODULE_FUNCS = {'seed', 'random', 'randint', 'randrange', 'uniform', 'gauss', 'choice', 'shuffle', 'sample',
                'getrandbits', 'choices', 'expovariate', 'triangular'}


def _scope_nodes(root):
    """Nodes of one scope: a module's top-level statements or one function's body, without
    descending into nested defs or classes (each has its own scope)."""
    stack = list(ast.iter_child_nodes(root))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _target_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for item in target.elts for name in _target_names(item)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return []


def _random_annotation(annotation):
    return isinstance(annotation, ast.Name) and annotation.id == 'Random'


def _random_value(value, known):
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'Random':
        return True
    return isinstance(value, ast.Name) and value.id in known


def _import_names(node):
    names = []
    for alias in node.names:
        if alias.asname:
            names.append(alias.asname)
        elif isinstance(node, ast.Import):
            names.append(alias.name.split('.')[0])
        else:
            names.append(alias.name)
    return names


def _scope_bindings(scope):
    """(values, safe, unsafe, params, random_params) for one scope. `safe` names are bound only
    by a plain assignment / annotated assignment; `unsafe` names have at least one binding the
    analysis cannot follow (for, with, except, import, comprehension, def/class, augmented
    assignment, a walrus, del, a global/nonlocal declaration). A name in both is treated as
    unsafe."""
    values = {}
    safe = set()
    unsafe = set()
    params = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in scope.args.args + scope.args.kwonlyargs:
            params.add(arg.arg)
            if _random_annotation(arg.annotation):
                values.setdefault(arg.arg, [])
        if scope.args.vararg is not None:
            params.add(scope.args.vararg.arg)
        if scope.args.kwarg is not None:
            params.add(scope.args.kwarg.arg)
    for node in _scope_nodes(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _target_names(target):
                    safe.add(name)
                    values.setdefault(name, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            safe.add(node.target.id)
            if _random_annotation(node.annotation):
                values.setdefault(node.target.id, [])
            if node.value is not None:
                values.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            unsafe.update(_target_names(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    unsafe.update(_target_names(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                unsafe.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            unsafe.update(_import_names(node))
        elif isinstance(node, ast.AugAssign):
            unsafe.update(_target_names(node.target))
        elif isinstance(node, ast.NamedExpr):
            unsafe.update(_target_names(node.target))
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for generator in node.generators:
                unsafe.update(_target_names(generator.target))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            unsafe.add(node.name)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                unsafe.update(_target_names(target))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            unsafe.update(node.names)
    # an annotated parameter is a Random only while no other binding rebinds it
    random_params = {name for name in params if name in values and not values[name]}
    return values, safe, unsafe, params, random_params


def _scope_known(scope, module_known):
    """Names of one scope that hold a `Random` at every binding: parameters annotated
    `random.Random`, a local assigned only `Random(...)` values or aliases of one, and a module
    name visible here that the scope does not shadow. A name that is also bound by a `for`,
    `with`, `except`, import, comprehension or any other form has no value here and is not
    included, so a call is only rewritten when the receiver is provably a Random."""
    values, safe, unsafe, params, random_params = _scope_bindings(scope)
    bound = safe | unsafe | params
    known = set(module_known - bound) | (random_params - (safe | unsafe))
    changed = True
    while changed:
        changed = False
        for name in safe:
            if name in known or name in unsafe:
                continue
            current = values.get(name)
            if current and all(_random_value(value, known) for value in current):
                known.add(name)
                changed = True
    return known


def _rewrite_randrange(scope, known):
    """`r.randrange(x)` on a proven Random -> `randrange1`; three arguments -> `randrange3`.
    The typed prelude has no method defaults, so the one- and three-argument spellings get
    their own methods (the boxed class has the same three names)."""
    for node in _scope_nodes(scope):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'randrange' and isinstance(node.func.value, ast.Name)
                and node.func.value.id in known and not node.keywords):
            continue
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            continue                        # the arity is not known here; `randrange` takes two
        if len(node.args) == 1:
            node.func.attr = 'randrange1'
        elif len(node.args) == 3:
            node.func.attr = 'randrange3'


def _rewrite_random_calls(tree, extra=()):
    module_known = _scope_known(tree, set()) | set(extra)
    _rewrite_randrange(tree, module_known)

    def walk_scope(scope, outer_known):
        for node in _scope_nodes(scope):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                known = _scope_known(node, outer_known)
                _rewrite_randrange(node, known)
                walk_scope(node, known)
            elif isinstance(node, ast.ClassDef):
                # the class body sees its own names; a method sees the enclosing scope, not the
                # class attributes, so descend with the outer names
                _rewrite_randrange(node, _scope_known(node, outer_known))
                walk_scope(node, outer_known)

    walk_scope(tree, module_known)


class _SeedDrop(ast.NodeTransformer):
    """A `_ail_rng.seed(x)` call statement whose generator is never read is dead; drop it."""

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and \
                call.func.attr == 'seed' and isinstance(call.func.value, ast.Name) and \
                call.func.value.id == '_ail_rng':
            return None
        return self.generic_visit(node)


def _seed_calls_are_bare(tree):
    """Whether every use of the hidden generator left after the rewrite is a bare
    `_ail_rng.seed(x)` statement. A seed whose result is read (`x = random.seed(7)`, an `if`)
    is not a statement we may drop; the generator has to stay for it."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == '_ail_rng':
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.value is node and parent.attr == 'seed'):
                return False
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == '_ail_rng':
            if node.attr != 'seed':
                return False
            call = parents.get(node)
            if not (isinstance(call, ast.Call) and call.func is node):
                return False
            if not isinstance(parents.get(call), ast.Expr):
                return False
    return True


def _is_random_ctor(value):
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'Random'


def run(tree, text):
    peek = stdlib5.peek_imports(tree, 'random')
    if not peek:
        return
    if not any(peek.attr(n) == 'Random' for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))):
        return                                     # only the module-level functions: stdlib3's
    for each in ast.walk(tree):
        if isinstance(each, ast.ClassDef) and each.name in ('Random', '_ail_rng') or (
                isinstance(each, ast.Name) and each.id in ('Random', '_ail_rng') and isinstance(each.ctx, ast.Store)):
            refuse(tree.body[0] if tree.body else tree, 'the program binds the name Random itself; rename it')
    rb = stdlib5.take_imports(tree, 'random', set(), whole=False)
    module_used = {'yes': False}
    module_draw = {'yes': False}

    def fix(node):
        if isinstance(node, ast.Call) and peek.attr(node.func) == 'Random':
            if len(node.args) != 1 or node.keywords:
                refuse(node, 'random.Random() without exactly one seed is not built: an unseeded generator is not '
                       'reproducible; write random.Random(<int>)')
            seed = node.args[0]
            if isinstance(seed, ast.Constant) and not isinstance(seed.value, int):
                refuse(node, 'random.Random(seed): a seed that is a str, bytes, float or None is not built (CPython '
                       'hashes it); use an int')
            return ast.Call(func=stdlib5.name('Random'), args=[stdlib5.Replace(fix).visit(seed)], keywords=[])
        found = peek.attr(node)
        if found == 'Random':
            return stdlib5.name('Random')
        if found in MODULE_FUNCS:
            module_used['yes'] = True
            if found != 'seed':
                module_draw['yes'] = True
            return ast.Attribute(value=stdlib5.name('_ail_rng'), attr=found, ctx=ast.Load())
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    dropped = False
    if not module_draw['yes'] and _seed_calls_are_bare(tree):
        # Only bare `random.seed(x)` statements used the hidden generator: its state is never
        # read, so the module-level `_ail_rng = Random(0)` and those calls can go (the typed
        # path refuses a module-level name bound to a call, and there is nothing to keep).
        kept = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                values = [node.value] if node.value is not None else []
                if values and all(isinstance(t, ast.Name) and t.id == '_ail_rng' for t in targets) and \
                        all(_is_random_ctor(v) for v in values):
                    continue
            kept.append(node)
        tree.body = kept
        tree.body = [_SeedDrop().visit(node) for node in tree.body]
        dropped = True
    keep_hidden = module_draw['yes'] or (module_used['yes'] and not dropped)
    _rewrite_random_calls(tree, {'_ail_rng'} if keep_hidden else ())
    # what is left of the module's names is not a call we can send to the hidden generator
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute) and isinstance(each.value, ast.Name) and each.value.id in peek.aliases:
            refuse(each, 'random.%s is not built next to random.Random (use a Random object for it)' % each.attr)
        if isinstance(each, ast.Name) and each.id in peek.aliases and isinstance(each.ctx, ast.Load):
            refuse(each, 'random used as a value is not built')
    # drop the imports of the module (the class replaces them), keeping other names of a from-import
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            node.names = [a for a in node.names if a.name != 'random']
            if not node.names:
                continue
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'random':
            continue
        body.append(node)
    tree.body = body
    if not any(isinstance(n, ast.Import) and any(a.name == 'math' and not a.asname for a in n.names) for n in tree.body):
        index = 0
        while index < len(tree.body) and isinstance(tree.body[index], ast.Expr) and isinstance(
                tree.body[index].value, ast.Constant):
            index += 1
        tree.body.insert(index, ast.Import(names=[ast.alias(name='math', asname=None)]))
    chunk = stdlib5.prelude('random_typed')
    if keep_hidden:
        chunk += '\n_ail_rng = Random(0)\n'
    text.append(chunk)
