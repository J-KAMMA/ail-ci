"""`statistics` over lists of int, lowered onto the functions of strt.py (library batch 4).

mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev: the same
numbers CPython gives (strt.py is compared with the statistics module by the test suite on generated data),
StatisticsError is spelt ValueError (it is a subclass of it).

Typing: the language has no int-or-float value. mean, median, variance and pvariance of ints are an int when
the answer is whole and a float when it is not, so a call is built only where the difference cannot be seen:

* print(call), str(call), a plain f-string field, "%s": the text CPython would print;
* a field with a numeric float spec ({call:.2f}), float(call), a comparison: the float;
* a variable assigned from such a call (or from round(call, n)), when every use of the variable is one of
  the float uses above -- the value is held as a float.
Anywhere else the call is refused by name, with fmean() (always a float) and sum(xs) / len(xs) as the
spellings to use. stdev / pstdev are always floats, mode is an element, median_low / median_high are
elements, multimode is a list, fmean is a float: those are built anywhere.
Lists of floats: fmean (the exactly rounded sum over n) is built; the others need CPython's exact fractions
over floats and are refused.
"""
import ast
import copy

import stdlib4
from iterlower import _name, _call

FUNCTIONS = ('mean', 'fmean', 'median', 'median_low', 'median_high', 'mode', 'multimode', 'pvariance', 'variance',
             'pstdev', 'stdev')
MIXED = ('mean', 'median', 'pvariance', 'variance')
ELEMENT = ('median_low', 'median_high', 'mode')
FLOAT_SPEC = set('feEgG%')
HELPERS = None


def refuse(node, text):
    stdlib4.refuse(node, text)


def helpers():
    """name -> (node, names it uses) of strt.py."""
    global HELPERS
    if HELPERS is None:
        from pathlib import Path
        tree = ast.parse((Path(__file__).parent / 'strt.py').read_text(encoding='utf-8'))
        top = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        uses = {}
        for name, node in top.items():
            uses[name] = {each.id for each in ast.walk(node) if isinstance(each, ast.Name) and each.id in top
                          and each.id != name}
        HELPERS = (top, uses)
    return HELPERS


def new_name(name):
    return '_ail_st_' + name


class Stat:
    def __init__(self, imports, tree):
        self.imports = imports
        self.tree = tree
        self.used = set()
        self.count = 0

    def resolve(self, node):
        found = self.imports.resolve(node) if isinstance(node, (ast.Name, ast.Attribute)) else None
        if found is not None and found[0] == 'statistics':
            return found[1]
        return None

    def call(self, name, *args):
        self.used.add(name)
        return _call(_name(new_name(name)), *args)

    # -- element types ---------------------------------------------------------------------------------------------------
    def ann_elem(self, ann):
        """'int' / 'float' / 'str' for a list[T] / List[T] annotation, ('dict', 'int'...) for dict[str, list[T]]."""
        if isinstance(ann, ast.Subscript):
            head = ann.value.id if isinstance(ann.value, ast.Name) else (ann.value.attr if isinstance(ann.value, ast.Attribute) else '')
            if head in ('list', 'List', 'Sequence', 'Iterable') and isinstance(ann.slice, ast.Name):
                return ann.slice.id if ann.slice.id in ('int', 'float', 'str') else None
            if head in ('dict', 'Dict') and isinstance(ann.slice, ast.Tuple) and len(ann.slice.elts) == 2:
                inner = self.ann_elem(ann.slice.elts[1])
                return ('dict', inner) if inner is not None else None
        return None

    def scalar_kind(self, node, env):
        """'int' / 'float' / 'str' for an element expression."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return None
            if isinstance(node.value, int):
                return 'int'
            if isinstance(node.value, float):
                return 'float'
            if isinstance(node.value, str):
                return 'str'
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('int', 'len', 'ord', 'abs') and (node.func.id != 'abs' or node.args and
                                                                 self.scalar_kind(node.args[0], env) == 'int'):
                return 'int'
            if node.func.id in ('float',):
                return 'float'
            if node.func.id in ('str',):
                return 'str'
        if isinstance(node, ast.Name):
            return env.get(node.id) if env.get(node.id) in ('int', 'float', 'str') else None
        if isinstance(node, ast.BinOp):
            left, right = self.scalar_kind(node.left, env), self.scalar_kind(node.right, env)
            if isinstance(node.op, ast.Div):
                return 'float'
            if left == 'float' or right == 'float':
                return 'float'
            if left == 'int' and right == 'int':
                return 'int'
        if isinstance(node, ast.Subscript):
            base = self.list_elem(node.value, env)
            if base in ('int', 'float', 'str') and not isinstance(node.slice, ast.Slice):
                return base
        return None

    def list_elem(self, node, env):
        """The element kind of a list expression."""
        if isinstance(node, ast.Name):
            t = env.get(node.id)
            return t[1] if isinstance(t, tuple) and t[0] == 'list' else None
        if isinstance(node, ast.ListComp):
            inner = dict(env)
            for gen in node.generators:
                it = self.list_elem(gen.iter, inner)
                if isinstance(gen.target, ast.Name):
                    inner[gen.target.id] = it
            return self.scalar_kind(node.elt, inner)
        if isinstance(node, ast.List):
            kinds = {self.scalar_kind(e, env) for e in node.elts}
            return kinds.pop() if len(kinds) == 1 else None
        if isinstance(node, ast.Subscript):
            base = node.value
            if isinstance(base, ast.Name):
                t = env.get(base.id)
                if isinstance(t, tuple) and t[0] == 'dict' and not isinstance(node.slice, ast.Slice):
                    return t[1]
                if isinstance(t, tuple) and t[0] == 'list' and isinstance(node.slice, ast.Slice):
                    return t[1]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args:
            if node.func.id in ('sorted', 'list', 'reversed'):
                return self.list_elem(node.args[0], env)
            if node.func.id == 'map' and len(node.args) == 2 and isinstance(node.args[0], ast.Name):
                return node.args[0].id if node.args[0].id in ('int', 'float', 'str') else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('split', 'splitlines'):
            return 'str'
        return None

    def environment(self, fn):
        env = {}
        for arg in (*fn.args.args, *fn.args.kwonlyargs):
            t = self.ann_elem(arg.annotation) if arg.annotation is not None else None
            if isinstance(t, str):
                env[arg.arg] = ('list', t)
            elif t is not None:
                env[arg.arg] = t
            elif isinstance(arg.annotation, ast.Name) and arg.annotation.id in ('int', 'float', 'str'):
                env[arg.arg] = arg.annotation.id
        for _ in range(2):
            for node in ast.walk(fn):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    t = self.ann_elem(node.annotation)
                    if isinstance(t, str):
                        env[node.target.id] = ('list', t)
                    elif t is not None:
                        env[node.target.id] = t
                    elif isinstance(node.annotation, ast.Name) and node.annotation.id in ('int', 'float', 'str'):
                        env[node.target.id] = node.annotation.id
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    e = self.list_elem(node.value, env)
                    if e is not None and isinstance(node.value, (ast.ListComp, ast.List, ast.Call, ast.Subscript, ast.Name)):
                        env.setdefault(name, ('list', e))
                    else:
                        k = self.scalar_kind(node.value, env)
                        if k is not None:
                            env.setdefault(name, k)
                elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                    e = self.list_elem(node.iter, env)
                    if e is not None:
                        env.setdefault(node.target.id, e)
        return env

    # -- walking -----------------------------------------------------------------------------------------------------------
    def run(self):
        top = self.tree
        # contexts are found with parent links
        for node in ast.walk(top):
            for child in ast.iter_child_nodes(node):
                child._st_parent = node
        scopes = [(top, {})]
        for node in ast.walk(top):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((node, self.environment(node)))
        # the module level and each function, innermost scope first
        owner = {}
        for scope, env in scopes:
            for node in ast.walk(scope):
                if isinstance(node, ast.Call) and self.resolve(node.func) in FUNCTIONS:
                    if id(node) not in owner or isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        owner[id(node)] = (scope, env)
        calls = [node for node in ast.walk(top) if isinstance(node, ast.Call) and self.resolve(node.func) in FUNCTIONS]
        replacements = {}
        for call in calls:
            scope, env = owner[id(call)]
            replacements[id(call)] = self.lower(call, env, scope)
        self.apply(replacements)
        for node in ast.walk(top):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                types = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
                for index, each in enumerate(types):
                    if self.resolve(each) == 'StatisticsError':
                        types[index] = _name('ValueError')
                if not isinstance(node.type, ast.Tuple):
                    node.type = types[0]
        self.attach()

    def apply(self, replacements):
        class Swap(ast.NodeTransformer):
            def visit_Call(self, node):
                if id(node) in replacements:
                    return replacements[id(node)]
                self.generic_visit(node)
                return node
        Swap().visit(self.tree)

    def lower(self, call, env, scope):
        name = self.resolve(call.func)
        if call.keywords:
            refuse(call, 'statistics.%s with keyword arguments (mu=, xbar=, weights=...) is not built' % name)
        if len(call.args) != 1:
            refuse(call, 'statistics.%s takes the data as its one argument here' % name)
        data = call.args[0]
        elem = self.list_elem(data, env)
        if elem is None:
            refuse(call, 'statistics.%s: the element type of the data is not known here; annotate the list '
                   '(xs: list[int] = ...) or build it with a comprehension of int(...) / float(...)' % name)
        if elem == 'float':
            if name == 'fmean':
                return self.call('fsum_floats_mean', data)
            refuse(call, 'statistics.%s of floats needs CPython\'s exact fractions over floats, which is not '
                   'built; fmean() (the exactly rounded sum over n) is, and so is sum(xs) / len(xs)' % name)
        if elem == 'str':
            if name == 'mode':
                return self.call('mode_str', data)
            if name == 'multimode':
                return self.call('multimode_str', data)
            refuse(call, 'statistics.%s of strings is not defined (mode and multimode are built)' % name)
        if name == 'fmean':
            return self.call('fmean', data)
        if name in ('pstdev', 'stdev'):
            return self.call('stdev_float', data, ast.Constant(value=name == 'stdev'))
        if name == 'mode':
            return self.call('mode_int', data)
        if name == 'multimode':
            return self.call('multimode_int', data)
        if name in ('median_low', 'median_high'):
            return self.call(name, data)
        # mean, median, variance, pvariance of ints: an int or a float, by the data
        return self.mixed(call, name, data, env, scope)

    def mixed(self, call, name, data, env, scope):
        kind = self.context(call)
        sample = ast.Constant(value=name == 'variance')
        extra = [sample] if name in ('variance', 'pvariance') else []
        base = {'mean': 'mean', 'median': 'median', 'variance': 'variance', 'pvariance': 'variance'}[name]
        if kind == 'text':
            return self.call(base + '_text', data, *extra)
        if kind == 'float':
            return self.call(base + '_float', data, *extra)
        if kind == 'variable':
            return self.call(base + '_float', data, *extra)
        refuse(call, 'statistics.%s of ints is an int when the answer is whole and a float otherwise, and this '
               'use needs one type: print it, format it with a float spec ({m:.2f}), or use statistics.fmean() '
               '(always a float) / sum(xs) / len(xs)' % name)

    # -- the use of a mixed result -----------------------------------------------------------------------------------------
    def context(self, node):
        """'text' (printed), 'float' (a float use), 'variable' (assigned to a name that is only used as a float) or None."""
        parent = getattr(node, '_st_parent', None)
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'print' \
                and node in parent.args:
            return 'text'
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'str' \
                and parent.args and parent.args[0] is node:
            return 'text'
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'float' \
                and parent.args and parent.args[0] is node:
            return 'float'
        if isinstance(parent, ast.FormattedValue) and parent.value is node:
            spec = parent.format_spec
            if spec is None and parent.conversion in (-1, 115):
                return 'text'
            if isinstance(spec, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in spec.values):
                text = ''.join(v.value for v in spec.values)
                if text and text[-1] in FLOAT_SPEC:
                    return 'float'
            return None
        if isinstance(parent, ast.Compare):
            return 'float'
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'round' \
                and parent.args and parent.args[0] is node and len(parent.args) == 2:
            outer = self.context_of_value(parent)
            return 'float' if outer in ('float', 'variable') else None
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) \
                and parent.value is node:
            return 'variable' if self.only_float_uses(parent.targets[0].id, parent) else None
        return None

    def context_of_value(self, node):
        """The context of an expression that is built from the call (round(call, n))."""
        parent = getattr(node, '_st_parent', None)
        if isinstance(parent, ast.FormattedValue) and parent.value is node:
            spec = parent.format_spec
            if isinstance(spec, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in spec.values):
                text = ''.join(v.value for v in spec.values)
                if text and text[-1] in FLOAT_SPEC:
                    return 'float'
            return None
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) \
                and parent.value is node:
            return 'variable' if self.only_float_uses(parent.targets[0].id, parent) else None
        if isinstance(parent, ast.Compare):
            return 'float'
        return None

    def only_float_uses(self, name, assign):
        """Whether the name, assigned once in its function, is only used as a float."""
        fn = assign
        while fn is not None and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            fn = getattr(fn, '_st_parent', None)
        stores = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load)]
        if len(stores) != 1:
            return False
        for use in ast.walk(fn):
            if isinstance(use, ast.Name) and use.id == name and isinstance(use.ctx, ast.Load):
                parent = getattr(use, '_st_parent', None)
                ok = False
                if isinstance(parent, ast.FormattedValue) and parent.value is use:
                    spec = parent.format_spec
                    if isinstance(spec, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in spec.values):
                        text = ''.join(v.value for v in spec.values)
                        ok = bool(text) and text[-1] in FLOAT_SPEC
                elif isinstance(parent, ast.Compare):
                    ok = True
                elif isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'float':
                    ok = True
                if not ok:
                    return False
        return True

    # -- helper source -----------------------------------------------------------------------------------------------------
    def attach(self):
        if not self.used:
            return
        top, uses = helpers()
        need, stack = set(), list(self.used)
        while stack:
            name = stack.pop()
            if name in need:
                continue
            need.add(name)
            stack.extend(uses.get(name, ()))
        mapping = {name: new_name(name) for name in top}

        class Rename(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in mapping:
                    return ast.copy_location(ast.Name(id=mapping[node.id], ctx=node.ctx), node)
                return node

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                node.name = mapping.get(node.name, node.name)
                return node
        nodes = [Rename().visit(copy.deepcopy(node)) for name, node in top.items() if name in need]
        self.out = '\n\n\n'.join(ast.unparse(n) for n in nodes)


def rewrite(tree, inject):
    """Lower the statistics uses in `tree` (AST, in place); returns whether anything changed."""
    imports = stdlib4.Imports(tree, ('statistics',))
    if not imports:
        return False
    stat = Stat(imports, tree)
    stat.run()
    # a name of the module that is still in the tree was not built
    for each in ast.walk(tree):
        found = imports.resolve(each) if isinstance(each, (ast.Name, ast.Attribute)) else None
        if found is not None and found[0] == 'statistics' and not (
                isinstance(each, ast.Name) and not isinstance(each.ctx, ast.Load)):
            refuse(each, 'statistics.%s used here is not built (mean, fmean, median, median_low, median_high, '
                   'mode, multimode, pvariance, variance, pstdev, stdev are, over a list of int)' % found[1])
    if stat.used:
        inject(tree, stat.out)
    return True
