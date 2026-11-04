"""`statistics` over lists of int, lowered onto the functions of strt.py (library batch 4).

mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev,
quantiles, covariance and correlation: the same numbers CPython gives (strt.py is compared with the statistics
module by the test suite on generated data), StatisticsError is spelt ValueError (it is a subclass of it).
fmean takes the weights= keyword (and the optional second positional argument) over lists of int or float.
quantiles takes n= and method= ("exclusive" and "inclusive"); covariance and correlation take two lists, and
correlation takes method="linear" (the "ranked" method is not built).

Typing: the language has no int-or-float value. mean, median, variance and pvariance of ints are an int when
the answer is whole and a float when it is not, so a call is built only where the difference cannot be seen:

* print(call), str(call), a plain f-string field, "%s": the text CPython would print;
* a field with a numeric float spec ({call:.2f}), float(call), a comparison: the float;
* a variable assigned from such a call (or from round(call, n)), when every use of the variable is one of
  the float uses above -- the value is held as a float.
Anywhere else the call is refused by name, with fmean() (always a float) and sum(xs) / len(xs) as the
spellings to use. stdev / pstdev are always floats, mode is an element, median_low / median_high are
elements, multimode is a list, fmean is a float: those are built anywhere.
Lists of floats: fmean (the exactly rounded sum over n), median, median_low, median_high, mode and multimode are
built (they need no exact sums); mean, variance, pvariance, stdev and pstdev need CPython's exact fractions over
floats (integers beyond 64 bits) and are refused.
"""
import ast
import copy

import stdlib4
from iterlower import _name, _call

FUNCTIONS = ('mean', 'fmean', 'median', 'median_low', 'median_high', 'mode', 'multimode', 'pvariance', 'variance',
             'pstdev', 'stdev', 'quantiles', 'covariance', 'correlation', 'geometric_mean', 'harmonic_mean',
             'linear_regression')
CENTRE = {'variance': 'xbar', 'stdev': 'xbar', 'pvariance': 'mu', 'pstdev': 'mu'}
INT64_MAX = 9223372036854775807
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
        top = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
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
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            kind = self.scalar_kind(node.operand, env)
            return kind if kind in ('int', 'float') else None
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

    # -- literal lists (the new forms need values known at build time) -----------------------------------------------------
    def scope_nodes(self, scope):
        """The nodes of one scope, not descending into a nested function or class."""
        out = []
        body = scope.body if isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)) else []
        stack = list(body)
        while stack:
            node = stack.pop()
            out.append(node)
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    stack.append(child)
        return out

    def int_list(self, node):
        """The ints of a list / tuple literal of int constants, or None."""
        if not isinstance(node, (ast.List, ast.Tuple)):
            return None
        out = []
        for each in node.elts:
            value = self.int_value(each)
            if value is None:
                return None
            out.append(value)
        return out

    def int_value(self, node):
        """The value of an int constant (a negative literal is a unary minus), or None."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = self.int_value(node.operand)
            return -inner if inner is not None else None
        return None

    def const_lists(self, scope):
        """name -> values of a list[int] assigned once from a literal list that nothing can mutate afterwards.

        The loads of such a name must be the data argument of a statistics call or `len(name)`; anything else
        (printing it, passing it on, an item or a slice) could hand it out, so its values are not known."""
        nodes = self.scope_nodes(scope)
        stores = {}
        for node in nodes:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                stores.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        stores.setdefault(target.id, []).append(node.value)
                    else:
                        for sub in ast.walk(target):
                            if isinstance(sub, ast.Name):
                                stores.setdefault(sub.id, []).append(None)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                stores.setdefault(node.target.id, []).append(None)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name):
                        stores.setdefault(sub.id, []).append(None)
        found = {}
        for name, values in stores.items():
            if len(values) != 1:
                continue
            values = self.int_list(values[0])
            if values is not None:
                found[name] = values
        for name in list(found):
            for node in nodes:
                if not isinstance(node, ast.Name) or node.id != name or not isinstance(node.ctx, ast.Load):
                    continue
                parent = getattr(node, '_st_parent', None)
                allowed = isinstance(parent, ast.Call) and node in parent.args and (
                    isinstance(parent.func, ast.Name) and parent.func.id == 'len'
                    or self.resolve(parent.func) in FUNCTIONS)
                if not allowed:
                    del found[name]
                    break
        return found

    def values_of(self, node, scope):
        """The values of an int list expression: a literal, or a name whose literal list cannot change."""
        values = self.const_lists_values(node, scope)
        if values is not None:
            return values
        literal = self.int_list(node)
        return literal

    def const_lists_values(self, node, scope):
        if not isinstance(node, ast.Name):
            return None
        values = self.consts.get(id(scope), {}).get(node.id)
        return values

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
        self.consts = {id(scope): self.const_lists(scope) for scope, env in scopes}
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
        self.finish_linear()
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

    def enclosing(self, node):
        while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            node = getattr(node, '_st_parent', None)
        return node

    def subscript(self, name, index):
        return ast.Subscript(value=ast.Name(id=name, ctx=ast.Load()), slice=ast.Constant(value=index),
                             ctx=ast.Load())

    def finish_linear(self):
        """The typed path refuses a __repr__ on an injected class (dunders runs before the helper is added), so
        linear_regression returns [slope, intercept]; lower the two field reads and the text forms here."""
        linear = (new_name('linear_regression_int'), new_name('linear_regression_prop'))
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child._st_parent = node
        replacements = {}
        assigned = {}
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in linear):
                continue
            parent = getattr(node, '_st_parent', None)
            if isinstance(parent, ast.Attribute) and parent.value is node and parent.attr in ('slope', 'intercept'):
                index = 0 if parent.attr == 'slope' else 1
                replacements[id(parent)] = ast.copy_location(
                    ast.Subscript(value=node, slice=ast.Constant(value=index), ctx=ast.Load()), parent)
            elif isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) \
                    and parent.func.id in ('print', 'str') and node in parent.args:
                replacements[id(node)] = ast.copy_location(self.call('linear_repr', node), node)
            elif isinstance(parent, ast.FormattedValue) and parent.value is node \
                    and parent.format_spec is None and parent.conversion in (-1, 115):
                replacements[id(node)] = ast.copy_location(self.call('linear_repr', node), node)
            elif isinstance(parent, (ast.Assign, ast.AnnAssign)):
                target = parent.targets[0] if isinstance(parent, ast.Assign) else parent.target
                if not isinstance(target, ast.Name):
                    refuse(parent, 'statistics.linear_regression: assign the result to one name (fit = ...) here')
                scope = self.enclosing(parent)
                assigned.setdefault(id(scope), (scope, {}))[1].setdefault(target.id, []).append(parent)
            elif isinstance(parent, ast.Expr):
                continue
            else:
                refuse(node, 'statistics.linear_regression: the result is used here in a way that is not built '
                       '(print it, format it, or read .slope / .intercept)')
        for scope, names in assigned.values():
            nodes = self.scope_nodes(scope)
            for name, assigns in names.items():
                stores = [n for n in nodes if isinstance(n, ast.Name) and n.id == name
                          and not isinstance(n.ctx, ast.Load)]
                if len(assigns) != 1 or len(stores) != 1:
                    refuse(assigns[0], 'statistics.linear_regression: the result name is assigned more than once '
                           'here; keep one assignment (fit = statistics.linear_regression(x, y))')
                for use in nodes:
                    if not isinstance(use, ast.Name) or use.id != name or not isinstance(use.ctx, ast.Load):
                        continue
                    parent = getattr(use, '_st_parent', None)
                    if isinstance(parent, ast.Attribute) and parent.value is use and parent.attr in ('slope', 'intercept'):
                        index = 0 if parent.attr == 'slope' else 1
                        replacements[id(parent)] = ast.copy_location(self.subscript(name, index), parent)
                    elif isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) \
                            and parent.func.id in ('print', 'str') and use in parent.args:
                        replacements[id(use)] = ast.copy_location(
                            self.call('linear_repr', ast.Name(id=name, ctx=ast.Load())), use)
                    elif isinstance(parent, ast.FormattedValue) and parent.value is use \
                            and parent.format_spec is None and parent.conversion in (-1, 115):
                        replacements[id(use)] = ast.copy_location(
                            self.call('linear_repr', ast.Name(id=name, ctx=ast.Load())), use)
                    else:
                        refuse(assigns[0], 'statistics.linear_regression: the result is used here in a way that '
                               'is not built (print it, format it, or read .slope / .intercept)')
        if replacements:
            class Swap(ast.NodeTransformer):
                def visit(self, node):
                    if id(node) in replacements:
                        return replacements[id(node)]
                    return self.generic_visit(node)
            Swap().visit(self.tree)

    def lower(self, call, env, scope):
        name = self.resolve(call.func)
        if name == 'quantiles':
            return self.lower_quantiles(call, env)
        if name in ('covariance', 'correlation'):
            return self.lower_pair(call, name, env)
        if name == 'linear_regression':
            return self.lower_linear(call, env, scope)
        if name in CENTRE and (call.keywords or len(call.args) == 2):
            return self.lower_centre(call, name, env, scope)
        if name in ('geometric_mean', 'harmonic_mean'):
            return self.lower_mean(call, name, env, scope)
        if name == 'fmean' and (call.keywords or len(call.args) == 2):
            return self.lower_fmean(call, env)
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
            if name in ('median', 'median_low', 'median_high', 'mode', 'multimode'):
                return self.call(name + '_f', data)
            refuse(call, 'statistics.%s of floats needs CPython\'s exact fractions over floats, which is not '
                   'built; fmean() (the exactly rounded sum over n) is, and so is sum(xs) / len(xs); '
                   'median, median_low, median_high, mode and multimode of floats are built' % name)
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

    def keyword(self, call, allowed):
        """The keyword arguments of `call`, with every name not in `allowed` refused."""
        found = {}
        for kw in call.keywords:
            if kw.arg is None or kw.arg not in allowed:
                refuse(call, 'statistics.%s does not take the keyword argument %s here' % (
                    self.resolve(call.func), kw.arg if kw.arg is not None else '**'))
            found[kw.arg] = kw.value
        return found

    def lower_fmean(self, call, env):
        kwargs = self.keyword(call, ('weights',))
        if len(call.args) < 1 or len(call.args) > 2:
            refuse(call, 'statistics.fmean takes the data and an optional weights argument here')
        if len(call.args) == 2 and 'weights' in kwargs:
            refuse(call, 'statistics.fmean was given weights twice')
        data = call.args[0]
        weights = kwargs.get('weights')
        if weights is None and len(call.args) == 2:
            weights = call.args[1]
        if weights is None or (isinstance(weights, ast.Constant) and weights.value is None):
            return self.lower_fmean_plain(call, data, env)
        kinds = []
        for node in (data, weights):
            elem = self.list_elem(node, env)
            if elem is None:
                refuse(call, 'statistics.fmean with weights: the element type of the data is not known here; '
                       'annotate the lists (xs: list[int] = ...) or build them with a comprehension of '
                       'int(...) / float(...)')
            if elem not in ('int', 'float'):
                refuse(call, 'statistics.fmean with weights of strings is not defined')
            kinds.append(elem)
        if kinds == ['int', 'int']:
            return self.call('fmean_weights_int', data, weights)
        left = data if kinds[0] == 'float' else self.call('to_floats', data)
        right = weights if kinds[1] == 'float' else self.call('to_floats', weights)
        return self.call('fmean_weights', left, right)

    def lower_fmean_plain(self, call, data, env):
        elem = self.list_elem(data, env)
        if elem is None:
            refuse(call, 'statistics.fmean: the element type of the data is not known here; annotate the list '
                   '(xs: list[int] = ...) or build it with a comprehension of int(...) / float(...)')
        if elem == 'float':
            return self.call('fsum_floats_mean', data)
        if elem == 'int':
            return self.call('fmean', data)
        refuse(call, 'statistics.fmean of strings is not defined')

    def lower_quantiles(self, call, env):
        if len(call.args) != 1:
            refuse(call, 'statistics.quantiles takes the data as its one positional argument here (n= and method= are keywords)')
        kwargs = self.keyword(call, ('n', 'method'))
        data = call.args[0]
        elem = self.list_elem(data, env)
        if elem is None:
            refuse(call, 'statistics.quantiles: the element type of the data is not known here; annotate the list '
                   '(xs: list[int] = ...) or build it with a comprehension of int(...) / float(...)')
        n = kwargs.get('n', ast.Constant(value=4))
        method = kwargs.get('method', ast.Constant(value='exclusive'))
        if elem == 'int':
            return self.call('quantiles_int', data, n, method)
        if elem == 'float':
            return self.call('quantiles_f', data, n, method)
        refuse(call, 'statistics.quantiles of strings is not defined')

    def lower_pair(self, call, name, env):
        allowed = ('method',) if name == 'correlation' else ()
        kwargs = self.keyword(call, allowed)
        if len(call.args) != 2:
            refuse(call, 'statistics.%s takes two data lists here' % name)
        left, right = call.args
        kinds = []
        for data in (left, right):
            elem = self.list_elem(data, env)
            if elem is None:
                refuse(call, 'statistics.%s: the element type of the data is not known here; annotate the lists '
                       '(xs: list[int] = ...) or build them with a comprehension of int(...) / float(...)' % name)
            if elem not in ('int', 'float'):
                refuse(call, 'statistics.%s of strings is not defined' % name)
            kinds.append(elem)
        args = [left if kinds[0] == 'float' else self.call('to_floats', left),
                right if kinds[1] == 'float' else self.call('to_floats', right)]
        if name == 'covariance':
            return self.call('covariance_f', *args)
        method = kwargs.get('method', ast.Constant(value='linear'))
        if not (isinstance(method, ast.Constant) and isinstance(method.value, str)):
            refuse(call, "statistics.correlation(..., method=...) needs the literal 'linear' here; a computed method is not built (method='ranked' is not built either)")
        if method.value == 'ranked':
            refuse(call, "statistics.correlation(..., method='ranked') is not built; method='linear' is")
        return self.call('correlation_f', *args, method)

    def lower_centre(self, call, name, env, scope):
        """variance / pvariance / stdev / pstdev with the centre given (xbar= / mu=)."""
        allowed = CENTRE[name]
        kwargs = self.keyword(call, (allowed,))
        if len(call.args) != 1:
            refuse(call, 'statistics.%s takes the data as its one positional argument here (the centre is %s=)'
                   % (name, allowed))
        data = call.args[0]
        centre = kwargs.get(allowed)
        if centre is None or (isinstance(centre, ast.Constant) and centre.value is None):
            refuse(call, 'statistics.%s with %s=None is not built here (leave the argument out)' % (name, allowed))
        value = self.int_value(centre)
        if value is None:
            refuse(call, 'statistics.%s: %s= must be an int literal here; a computed centre is not built'
                   % (name, allowed))
        elem = self.list_elem(data, env)
        if elem is None:
            refuse(call, 'statistics.%s: the element type of the data is not known here; annotate the list '
                   '(xs: list[int] = ...) or build it with a comprehension of int(...) / float(...)' % name)
        if elem != 'int':
            refuse(call, 'statistics.%s with %s= is built over a list of int here; a %s centre over floats needs '
                   'CPython\'s exact fractions, which are not built' % (name, allowed, elem))
        values = self.values_of(data, scope)
        if values is None:
            refuse(call, 'statistics.%s with %s=: the data must be a literal list of ints (its values are needed '
                   'at build time to show the exact sum of squares fits 64 bits); use the two-pass form '
                   'sum((x - %s) ** 2 for x in xs) / (len(xs) - 1) instead' % (name, allowed, allowed))
        ss = 0
        for x in values:
            d = x - value
            ss += d * d
        if ss > INT64_MAX:
            refuse(call, 'statistics.%s with %s=: the exact sum of squares leaves 64 bits for this data, so the '
                   'value is not built on the typed path' % (name, allowed))
        if name in ('variance', 'pvariance'):
            kind = self.context(call)
            if kind == 'text':
                helper = 'variance_c_text'
            elif kind in ('float', 'variable'):
                helper = 'variance_c_float'
            else:
                refuse(call, 'statistics.%s of ints is an int when the answer is whole and a float otherwise, and '
                       'this use needs one type: print it, format it with a float spec ({m:.2f}), or use '
                       'statistics.fmean() (always a float) / sum(xs) / len(xs)' % name)
            return self.call(helper, data, ast.Constant(value=value),
                             ast.Constant(value=name == 'variance'))
        return self.call('stdev_c', data, ast.Constant(value=value), ast.Constant(value=name == 'stdev'))

    def harmonic_parts(self, values):
        """(num, den) with num / den the result of harmonic_mean(values), when every int64 intermediate fits."""
        count = len(values)
        ms = []
        es = []
        for x in values:
            t = 1.0 / x
            e = 0
            while t != float(int(t)):
                t = t * 2.0
                e = e + 1
            ms.append(int(t))
            es.append(e)
        big = 0
        for e in es:
            if e > big:
                big = e
        total = 0
        for i in range(count):
            shift = big - es[i]
            term = ms[i] << shift
            if term > INT64_MAX - total:
                return None
            total += term
        shift = 0
        reduced = total
        while reduced % 2 == 0:
            reduced = reduced // 2
            shift += 1
        if big >= shift:
            num = count << (big - shift)
            den = reduced
        else:
            num = count
            den = reduced << (shift - big)
        if num > INT64_MAX or den > INT64_MAX:
            return None
        from fractions import Fraction
        import statistics as module
        if float(Fraction(num, den)) != module.harmonic_mean(values):
            return None
        return num, den

    def lower_mean(self, call, name, env, scope):
        if call.keywords:
            refuse(call, 'statistics.%s with keyword arguments is not built here' % name)
        if len(call.args) != 1:
            refuse(call, 'statistics.%s takes the data as its one argument here' % name)
        data = call.args[0]
        elem = self.list_elem(data, env)
        if elem is None:
            refuse(call, 'statistics.%s: the element type of the data is not known here; annotate the list '
                   '(xs: list[int] = ...) or build it with a comprehension of int(...) / float(...)' % name)
        if elem != 'int':
            refuse(call, 'statistics.%s of %s is not built on the typed path (list[int] is)' % (name, elem))
        if name == 'geometric_mean':
            return self.call('geometric_mean_int', data)
        values = self.values_of(data, scope)
        if values is None:
            refuse(call, 'statistics.harmonic_mean of list[int] is built only for a literal list of positive ints '
                   'whose exact reciprocal sum fits 64 bits (its values are needed at build time); use '
                   'len(xs) / sum(1.0 / x for x in xs) instead')
        if len(values) == 0:
            refuse(call, 'statistics.harmonic_mean of an empty list raises StatisticsError; that form is not built '
                   'on the typed path')
        for x in values:
            if x <= 0:
                refuse(call, 'statistics.harmonic_mean of a non-positive value raises StatisticsError; that form is '
                       'not built on the typed path')
        if len(values) == 1:
            return ast.Constant(value=values[0])
        if self.harmonic_parts(values) is None:
            refuse(call, 'statistics.harmonic_mean: the exact reciprocal sum of this data leaves 64 bits, so it is '
                   'not built on the typed path; use len(xs) / sum(1.0 / x for x in xs) instead')
        return self.call('harmonic_mean_int', data)

    def lower_linear(self, call, env, scope):
        kwargs = self.keyword(call, ('proportional',))
        if len(call.args) != 2:
            refuse(call, 'statistics.linear_regression takes the two data lists here')
        left, right = call.args
        for data in (left, right):
            elem = self.list_elem(data, env)
            if elem is None:
                refuse(call, 'statistics.linear_regression: the element type of the data is not known here; '
                       'annotate the lists (xs: list[int] = ...) or build them with a comprehension of int(...)')
            if elem != 'int':
                refuse(call, 'statistics.linear_regression of %s lists is not built on the typed path (list[int] is)'
                       % elem)
        prop = kwargs.get('proportional', ast.Constant(value=False))
        if not (isinstance(prop, ast.Constant) and (prop.value is True or prop.value is False or prop.value is None)):
            refuse(call, 'statistics.linear_regression(proportional=...) needs the literal True or False here')
        if not prop.value:
            return self.call('linear_regression_int', left, right)
        vx = self.values_of(left, scope)
        vy = self.values_of(right, scope)
        if vx is None or vy is None:
            refuse(call, 'statistics.linear_regression(proportional=True): both lists must be literal ints (their '
                   'values are needed at build time to show the exact product sums fit 64 bits)')
        if len(vx) != len(vy):
            refuse(call, 'statistics.linear_regression: the lists have different lengths, which raises '
                   'StatisticsError; that form is not built on the typed path')
        if len(vx) < 2:
            refuse(call, 'statistics.linear_regression of fewer than two points raises StatisticsError; that form '
                   'is not built on the typed path')
        sxy = 0
        sxx = 0
        for i in range(len(vx)):
            product = vx[i] * vy[i]
            square = vx[i] * vx[i]
            if product > INT64_MAX or product < -INT64_MAX - 1 or square > INT64_MAX:
                refuse(call, 'statistics.linear_regression(proportional=True): an exact product of this data '
                       'leaves 64 bits, so it is not built on the typed path')
            sxy += product
            sxx += square
            if sxy > INT64_MAX or sxy < -INT64_MAX - 1 or sxx > INT64_MAX:
                refuse(call, 'statistics.linear_regression(proportional=True): an exact product sum of this data '
                       'leaves 64 bits, so it is not built on the typed path')
        return self.call('linear_regression_prop', left, right)

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

            def visit_ClassDef(self, node):
                self.generic_visit(node)
                node.name = mapping.get(node.name, node.name)
                return node
        nodes = [Rename().visit(copy.deepcopy(node)) for name, node in top.items() if name in need]
        text = '\n\n\n'.join(ast.unparse(n) for n in nodes)
        if 'math.' in text:
            text = 'import math\n\n\n' + text
        self.out = text


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
                   'mode, multimode, pvariance, variance, pstdev, stdev, quantiles, covariance, correlation, '
                   'geometric_mean, harmonic_mean, linear_regression are, over a list of int)' % found[1])
    if stat.used:
        inject(tree, stat.out)
    return True
