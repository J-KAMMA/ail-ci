"""Library batch 3: `random`, `itertools`, `functools` and `json`, lowered onto what the compiler builds.

Run once on the parsed module (pyfunc `_to_c_once`) before iterlower.py. A program that imports none
of the four modules is not touched, so its C does not change. Every use is either lowered to code
that produces what CPython produces, or refused here by name (`module.name: why`); a use that is
left over after the rewrite is never passed on to the generic import refusal.

* random: MT19937 in the C runtime (cruntime RANDOM), bit for bit CPython 3.12 after
  `random.seed(<int>)`: random, randint, randrange, uniform, gauss are C calls; choice is an
  index expression, shuffle and sample are loops over the same `_randbelow`. Without a
  `random.seed(<int>)` in the program it is refused (an unseeded run is not reproducible).
* itertools / functools: see itlib.py.
* json: see jsonlib.py.

The pass subclasses iterlower._Lower, so the hoisting of a call out of the first-evaluated position of
a statement, the sequence analysis and the fresh-name scheme are the ones map / filter / zip use.
"""
import ast
import copy
import textwrap

import iterlower
from iterlower import _name, _mark, _call, _locate, _Rename, _Subst

MODULES = ('random', 'itertools', 'functools', 'json')
_Unsupported = None


def refuse(node, text):
    error = _Unsupported(text)
    error.source_line = getattr(node, 'lineno', None)
    raise error


def num(value):
    return ast.Constant(value=value)


def template(code, names=None, exprs=None, stmts=None, fresh=None):
    """Parse a statement template. `names` maps template variable names to fresh names, `exprs` maps a
    placeholder name to an expression (copied at each use), `stmts` maps a placeholder statement
    `NAME` (an expression statement of one name) to a list of statements."""
    module = ast.parse(textwrap.dedent(code))
    mapping = {}
    for each in ast.walk(module):
        if isinstance(each, ast.Name) and each.id.startswith('t_') and each.id not in (exprs or {}):
            if each.id not in mapping:
                mapping[each.id] = fresh(each.id[2:]) if fresh else each.id
    renamer = _Rename(mapping)

    class Fill(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Name) and stmts and node.value.id in stmts:
                return [copy.deepcopy(s) for s in stmts[node.value.id]]
            return self.generic_visit(node)

        def visit_Name(self, node):
            if exprs and node.id in exprs:
                return copy.deepcopy(exprs[node.id])
            return node

        def visit_arg(self, node):
            return node

    body = Fill().visit(renamer.visit(module)).body
    for stmt in body:
        _mark(stmt)
    return body


def pure(node):
    """An expression that can be evaluated twice: names, constants, attribute chains and arithmetic on them."""
    for each in ast.walk(node):
        if isinstance(each, (ast.Call, ast.NamedExpr, ast.Lambda, ast.ListComp, ast.GeneratorExp, ast.SetComp,
                             ast.DictComp, ast.Await, ast.Yield)):
            return False
    return True


class Imports:
    """The names a program binds to the four modules, found at the top level."""
    def __init__(self, tree):
        self.aliases = {}          # local name -> module
        self.names = {}            # local name -> (module, attribute)
        self.nodes = []
        body = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name in MODULES:
                        self.aliases[alias.asname or alias.name] = alias.name
                    else:
                        rest.append(alias)
                if len(rest) != len(node.names):
                    self.nodes.append(node)
                    if rest:
                        node.names = rest
                        body.append(node)
                    continue
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in MODULES:
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from %s import *: name what you use' % node.module)
                    self.names[alias.asname or alias.name] = (node.module, alias.name)
                self.nodes.append(node)
                continue
            body.append(node)
        tree.body = body

    def __bool__(self):
        return bool(self.aliases or self.names)

    def modules(self):
        return set(self.aliases.values()) | {m for m, _ in self.names.values()}

    def resolve(self, func):
        """(module, attribute) for `module.attr`, `alias.attr` or a from-imported name; attribute may be
        dotted (`chain.from_iterable`)."""
        if isinstance(func, ast.Attribute):
            inner = func.value
            if isinstance(inner, ast.Name) and inner.id in self.aliases:
                return self.aliases[inner.id], func.attr
            found = self.resolve(inner)
            if found is not None:
                return found[0], found[1] + '.' + func.attr
            return None
        if isinstance(func, ast.Name) and func.id in self.names:
            return self.names[func.id]
        return None


def binds(tree, name):
    """Whether the program binds `name` itself (a variable, parameter, function or class). A method is not a
    binding of its name in the module's scope (`def random(self)` in a class does not hide `import random`)."""
    methods = {id(n) for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for n in c.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for each in ast.walk(tree):
        if id(each) in methods:
            continue
        if isinstance(each, ast.Name) and each.id == name and not isinstance(each.ctx, ast.Load):
            return True
        if isinstance(each, ast.arg) and each.arg == name:
            return True
        if isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name == name:
            return True
    return False


RANDOM_NOTE = ('random is built for seed(<int>), random, randint, randrange, uniform, gauss, choice (a list), '
               'shuffle (a list) and sample (a list): CPython 3.12\'s MT19937, bit for bit')


class Lib3(iterlower._Lower):
    def __init__(self, imports, tree):
        super().__init__()
        self.imports = imports
        self.tree = tree
        self.seeded = False
        self.random_used = False
        self.extra_helpers = []        # top-level definitions appended to the program
        self.sequences = set()
        self.lists = set()
        import itlib
        import funclib
        self.it = itlib.Streams(self)
        self.cmp = funclib.CmpSort(self)

    # -- helpers -----------------------------------------------------------------------------------
    def call_of(self, node):
        """(module, attribute) when `node` is a call of one of the four modules' names."""
        if isinstance(node, ast.Call):
            return self.imports.resolve(node.func)
        return None

    def args_of(self, call, names, defaults=None, what=''):
        """Positional + keyword arguments of `call` as a dict by parameter name (refuses *args/**kw and unknowns)."""
        out = {}
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            refuse(call, '%s: * and ** arguments are not built' % what)
        if len(call.args) > len(names):
            refuse(call, '%s: too many arguments' % what)
        for name, value in zip(names, call.args):
            out[name] = value
        for keyword in call.keywords:
            if keyword.arg not in names:
                refuse(call, '%s: the keyword %s= is not built' % (what, keyword.arg))
            if keyword.arg in out:
                refuse(call, '%s: %s given twice' % (what, keyword.arg))
            out[keyword.arg] = keyword.value
        return out

    def at(self, node, new):
        return ast.copy_location(new, node)

    def list_names(self, fn):
        """Names of `fn` bound only to list-valued expressions (a list annotation, a list display, a
        comprehension, list() / sorted() / split(), a slice or concatenation of such names)."""
        good, bad = set(), set()

        def listy(node):
            if isinstance(node, (ast.List, ast.ListComp)):
                return True
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    return node.func.id in ('list', 'sorted')
                if isinstance(node.func, ast.Attribute):
                    return node.func.attr in ('split', 'rsplit', 'splitlines')
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                return isinstance(node.value, ast.Name) and node.value.id in good
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                return listy(node.left) and listy(node.right)
            if isinstance(node, ast.Name):
                return node.id in good
            return False

        def ann_list(ann):
            head = ann.value if isinstance(ann, ast.Subscript) else ann
            return isinstance(head, ast.Name) and head.id in ('list', 'List')
        for arg in (*fn.args.args, *fn.args.kwonlyargs):
            (good if arg.annotation is not None and ann_list(arg.annotation) else bad).add(arg.arg)
        for _ in range(2):
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if listy(node.value):
                                good.add(target.id)
                            else:
                                bad.add(target.id)
                        else:
                            bad.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    (good if ann_list(node.annotation) else bad).add(node.target.id)
                elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    if not isinstance(node.op, ast.Add):
                        bad.add(node.target.id)
                elif isinstance(node, (ast.For, ast.comprehension)):
                    bad.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
                elif isinstance(node, (ast.With,)):
                    for item in node.items:
                        if item.optional_vars is not None:
                            bad.update(n.id for n in ast.walk(item.optional_vars) if isinstance(n, ast.Name))
                elif isinstance(node, ast.ExceptHandler) and node.name:
                    bad.add(node.name)
                elif isinstance(node, (ast.Global, ast.Nonlocal)):
                    bad.update(node.names)
        return good - bad

    # -- random ------------------------------------------------------------------------------------
    def rand_arg_check(self, call, what):
        if sum(1 for a in call.args if not pure(a)) > 1:
            refuse(call, '%s: more than one argument runs a call; bind the arguments to variables first '
                   '(their order of evaluation is kept by naming them)' % what)

    def random_expr(self, call, attr):
        """The expression for `random.<attr>(...)`, or None when it needs statements (sample)."""
        what = 'random.' + attr
        self.random_used = True
        if attr == 'seed':
            refuse(call, 'random.seed(<int>) is built as a statement on its own line')
        if attr == 'random':
            if call.args or call.keywords:
                refuse(call, 'random.random() takes no arguments')
            return self.at(call, _call(_name('_ail_rand_random')))
        if attr in ('uniform', 'gauss'):
            if attr == 'uniform':
                got = self.args_of(call, ['a', 'b'], what=what)
                if set(got) != {'a', 'b'}:
                    refuse(call, 'random.uniform(a, b) takes two arguments')
                ordered = [got['a'], got['b']]
            else:
                got = self.args_of(call, ['mu', 'sigma'], what=what)
                if set(got) != {'mu', 'sigma'}:
                    refuse(call, 'random.gauss(mu, sigma) takes both arguments (the defaults are not built)')
                ordered = [got['mu'], got['sigma']]
            self.rand_arg_check(call, what)
            return self.at(call, _call(_name('_ail_rand_' + attr), *ordered))
        if attr in ('randint', 'randrange'):
            if attr == 'randint':
                got = self.args_of(call, ['a', 'b'], what=what)
                if set(got) != {'a', 'b'}:
                    refuse(call, 'random.randint(a, b) takes two arguments')
                args = [got['a'], got['b'], num(1), num(4)]
            else:
                got = self.args_of(call, ['start', 'stop', 'step'], what=what)
                if 'start' not in got:
                    refuse(call, 'random.randrange() needs an argument')
                if 'stop' not in got:
                    if 'step' in got:
                        refuse(call, 'random.randrange: a step needs a stop (CPython raises TypeError)')
                    args = [got['start'], num(0), num(1), num(1)]
                elif 'step' not in got:
                    args = [got['start'], got['stop'], num(1), num(2)]
                else:
                    args = [got['start'], got['stop'], got['step'], num(3)]
            self.rand_arg_check(call, what)
            return self.at(call, _call(_name('_ail_rand_range'), *args))
        if attr == 'choice':
            got = self.args_of(call, ['seq'], what=what)
            seq = got.get('seq')
            if seq is None or not pure(seq) or not isinstance(seq, (ast.Name, ast.Attribute)):
                refuse(call, 'random.choice(seq): seq has to be a list held in a variable (or a field); '
                       'bind the list to a name first')
            if isinstance(seq, ast.Name) and self.current_lists is not None and seq.id not in self.current_lists:
                refuse(call, 'random.choice(%s): %s is not known to be a list here (a list parameter, or a '
                       'variable bound only to lists)' % (seq.id, seq.id))
            index = _call(_name('_ail_rand_choice_index'), _call(_name('len'), copy.deepcopy(seq)))
            return self.at(call, ast.Subscript(value=copy.deepcopy(seq), slice=index, ctx=ast.Load()))
        if attr in ('shuffle', 'sample'):
            return None
        refuse(call, '%s is not built; %s' % (what, RANDOM_NOTE))

    def shuffle_statement(self, node):
        call = node.value
        got = self.args_of(call, ['x'], what='random.shuffle')
        x = got.get('x')
        if not isinstance(x, ast.Name):
            refuse(call, 'random.shuffle(x): x has to be a list held in a variable')
        if self.current_lists is not None and x.id not in self.current_lists:
            refuse(call, 'random.shuffle(%s): %s is not known to be a list here (a list parameter, or a '
                   'variable bound only to lists)' % (x.id, x.id))
        self.random_used = True
        # the swaps run on a list of indices, then the list is gathered through it: the same permutation as
        # swapping the elements (x[i], x[j] = x[j], x[i]), for every element type the compiler holds in a list
        body = template('''
            t_perm = list(range(len(X)))
            t_i = len(X) - 1
            while t_i >= 1:
                t_j = _ail_rand_below_i(t_i + 1)
                t_t = t_perm[t_i]
                t_perm[t_i] = t_perm[t_j]
                t_perm[t_j] = t_t
                t_i -= 1
            X = [X[t_g] for t_g in t_perm]
        ''', exprs={'X': x}, fresh=self.fresh)
        for each in body:
            if isinstance(each, ast.Assign) and isinstance(each.targets[0], ast.Name) and each.targets[0].id == x.id:
                each.targets[0].ctx = ast.Store()
        _locate(body, node)
        return body

    def sample_hoist(self, call):
        what = 'random.sample'
        got = self.args_of(call, ['population', 'k'], what=what)
        if set(got) != {'population', 'k'}:
            refuse(call, 'random.sample(population, k) takes both arguments (counts= is not built)')
        pop, k = got['population'], got['k']
        if not isinstance(pop, ast.Name) or (self.current_lists is not None and pop.id not in self.current_lists):
            refuse(call, 'random.sample(population, k): population has to be a list held in a variable '
                   '(a str, range or set is not built); bind it to a name first')
        self.random_used = True
        res = self.fresh('sample')
        kk = self.fresh('k')
        body = template('''
            t_k = K
            t_n = len(P)
            if t_k < 0 or t_k > t_n:
                raise ValueError("Sample larger than population or is negative")
            t_r: list[int] = []
            if t_n <= _ail_rand_setsize(t_k):
                t_pool = list(range(t_n))
                t_i = 0
                while t_i < t_k:
                    t_j = _ail_rand_below_i(t_n - t_i)
                    t_r.append(t_pool[t_j])
                    t_pool[t_j] = t_pool[t_n - t_i - 1]
                    t_i += 1
            else:
                t_sel: set[int] = set()
                t_i = 0
                while t_i < t_k:
                    t_j = _ail_rand_below_i(t_n)
                    while t_j in t_sel:
                        t_j = _ail_rand_below_i(t_n)
                    t_sel.add(t_j)
                    t_r.append(t_j)
                    t_i += 1
            RES = [P[t_g] for t_g in t_r]
        ''', exprs={'P': pop, 'K': k, 'RES': _name(res)}, fresh=self.fresh)
        for stmt in body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name) \
                    and stmt.targets[0].id == res:
                stmt.targets[0].ctx = ast.Store()
        _locate(body, call)
        return _name(res), body

    def seed_statement(self, node):
        call = node.value
        got = self.args_of(call, ['a', 'version'], what='random.seed')
        if 'a' not in got or 'version' in got:
            refuse(call, 'random.seed(): seeding from the clock is not reproducible and is not built; '
                   'call random.seed(<int>)')
        arg = got['a']
        if isinstance(arg, ast.Constant) and (isinstance(arg.value, (float, str, bytes)) or arg.value is None):
            refuse(call, 'random.seed(%r): only an int seed is built (str / float / bytes seeds go through a '
                   'hash in CPython)' % (arg.value,))
        self.seeded = True
        self.random_used = True
        return [self.at(node, ast.Assign(targets=[_name('_ail_rand_seeded', True)],
                                         value=_call(_name('_ail_rand_seed'), arg)))]

    # -- walking ------------------------------------------------------------------------------------
    current_lists = None

    def lib_expr(self, node):
        """Rewrite the module calls inside an expression that need no statements."""
        lower = self

        class Visitor(ast.NodeTransformer):
            def visit_Call(self, call):
                self.generic_visit(call)
                found = lower.call_of(call)
                if found is None:
                    return call
                module, attr = found
                if module == 'random':
                    result = lower.random_expr(call, attr)
                    return call if result is None else result
                return lower.it.call_expr(call, module, attr, call)
        return Visitor().visit(node)

    def expr(self, node):
        if self.imports:
            node = self.lib_expr(node)
        return super().expr(node)

    def hoist(self, e):
        found = self.call_of(e)
        if found == ('random', 'sample'):
            return self.sample_hoist(e)
        lowered = self.it.hoist(e)
        if lowered is not None:
            return lowered
        lowered = self.cmp.hoist(e)
        if lowered is not None:
            return lowered
        return super().hoist(e)

    cur_fn = None

    def stmt(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            saved, saved_fn = self.current_lists, self.cur_fn
            self.current_lists = self.list_names(node)
            self.cur_fn = node
            try:
                return super().stmt(node)
            finally:
                self.current_lists, self.cur_fn = saved, saved_fn
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            found = self.call_of(node.value)
            if found == ('random', 'shuffle'):
                return self.block(self.shuffle_statement(node))
            if found == ('random', 'seed'):
                return self.seed_statement(node)
            lowered = self.cmp.sort_statement(node)
            if lowered is not None:
                return self.block(lowered)
        if isinstance(node, ast.For):
            lowered = self.it.for_statement(node)
            if lowered is not None:
                return lowered
            node.iter, pre = self.hoist(node.iter)
            if pre:
                _locate(pre, node)
                return self.block(pre) + self.stmt(node)
        out = self.it.statement(node)
        if out is not None:
            return out
        return super().stmt(node)


def leftovers(tree, imports):
    """Name the first use of one of the modules' names that is still in the tree."""
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute):
            found = imports.resolve(each)
            if found is not None:
                refuse(each, '%s.%s used here is not built: %s' % (found[0], found[1], LEFT_NOTE.get(found[0], '')))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.names:
            module, attr = imports.names[each.id]
            refuse(each, '%s.%s used here is not built: %s' % (module, attr, LEFT_NOTE.get(module, '')))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.aliases:
            refuse(each, '%s used as a value is not built' % imports.aliases[each.id])


LEFT_NOTE = {
    'random': RANDOM_NOTE + '; sample() and the others are built where they are the first thing a statement '
              'evaluates',
    'itertools': 'the itertools functions are built in a for statement, in a comprehension / generator '
                 'expression, and as the argument of list(), sum(), min(), max(), any(), all(), sorted(), '
                 'len(list()) or "".join() where that call starts a statement',
    'functools': 'reduce, lru_cache / cache and cmp_to_key are built (see the reference)',
    'json': 'json.loads(s) into a declared type and json.dumps(x) of a typed value are built (see the reference)',
}


def rewrite(tree, Unsupported):
    """Lower the four modules' uses in `tree` in place; returns whether anything changed."""
    global _Unsupported
    _Unsupported = Unsupported
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return False
    imports = Imports(tree)
    if not imports:
        return False
    for alias in list(imports.aliases) + list(imports.names):
        if binds(tree, alias):
            refuse(tree.body[0] if tree.body else tree, '%s is also bound by the program itself; rename it '
                   '(the name stands for an imported module here)' % alias)
    import jsonlib
    if 'json' in imports.modules():
        jsonlib.Json(imports, tree).run()
    import funclib
    if 'functools' in imports.modules():
        funclib.Memo(imports, tree).run()
    lower = Lib3(imports, tree)
    lower.sequences = set()
    lower.it.prepare(tree)
    tree.body = lower.block(tree.body)
    lower.it.finish(tree)
    if lower.random_used and not lower.seeded:
        refuse(tree.body[0] if tree.body else tree, 'random without random.seed(<int>): an unseeded generator is '
               'not reproducible and is not built; call random.seed(<int>) first')
    leftovers(tree, imports)
    ast.fix_missing_locations(tree)
    return True
