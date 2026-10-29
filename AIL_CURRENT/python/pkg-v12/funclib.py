"""functools.lru_cache / cache and cmp_to_key (called from stdlib3.py before the statements are lowered).

lru_cache / cache: a top-level function with int / str / bool parameters and an int / float / str / bool
result that touches nothing but its arguments (no print, input, file, sys, random, time, no `global`; every
function it calls is pure too) is memoised in a dict. There are no module-level mutable names here, so the
dict travels as a parameter: every function that can reach a cached function gets one extra trailing
parameter per cached function it can reach (`_m_<name>`, an object holding the dict), the calls pass it on,
and the functions nobody else calls (main...) create it. The program therefore shares one cache per cached
function exactly as CPython's single module-level cache does. The key is the int / str argument itself,
or a string built from the arguments (`str(a) + "," + str(b)`, a str argument as `len:text`) -- never an
approximation that could join two different calls. The size bound of lru_cache(maxsize=N) is ignored: the
result of a pure function does not depend on what was evicted. cache_info() is built for the unbounded forms
(cache, lru_cache(maxsize=None)) where there is no eviction to reproduce: hits / misses are counted and
currsize is len(cache). cache_clear() / cache_parameters() and a cached function used as a value (passed,
stored) are refused by name.

cmp_to_key: `sorted(xs, key=cmp_to_key(f))` / `xs.sort(key=cmp_to_key(f))` (reverse= too) as a statement-
level stable merge sort over indices, calling f(a, b) < 0 as the only comparison, as list.sort does with the
K objects functools builds; the same order as CPython for any comparator that is a consistent ordering.
"""
import ast
import copy
import textwrap

from iterlower import _name, _mark, _call, _locate, _Rename

KEY_TYPES = ('int', 'str', 'bool')
VALUE_TYPES = ('int', 'float', 'str', 'bool')
IMPURE_NAMES = ('print', 'input', 'open', 'write_text', 'write_bytes', 'append_bytes', 'read_stdin_bytes',
                'exit', 'flush_stdout', 'write_stdout_bytes', 'read_text', 'read_bytes', 'monotonic')
IMPURE_ROOTS = ('sys', 'random', 'time', 'os')


def S():
    import stdlib3
    return stdlib3


def refuse(node, text):
    S().refuse(node, text)


def ann_name(node):
    if not isinstance(node, ast.Name):
        return None
    name = node.id
    if name.startswith("__ail_checked_") and name.endswith("__"):
        name = name[len("__ail_checked_"):-2]       # the overflow-checked return type the Python surface writes
    return name


class Memo:
    def __init__(self, imports, tree):
        self.imports = imports
        self.tree = tree

    # -- finding the cached functions -------------------------------------------------------------
    def cache_kind(self, decorator):
        """'cache' / 'lru_cache' (with its maxsize) when `decorator` is one of those, else None."""
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        found = self.imports.resolve(target)
        if not found or found[0] != 'functools' or found[1] not in ('cache', 'lru_cache'):
            return None
        return found[1]

    def run(self):
        tree = self.tree
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        cached = {}
        unbounded = {}
        for name, fn in functions.items():
            kinds = [self.cache_kind(d) for d in fn.decorator_list]
            if not any(kinds):
                continue
            if len(fn.decorator_list) != 1:
                refuse(fn, 'functools.%s together with another decorator is not built' % kinds[0])
            decorator = fn.decorator_list[0]
            kind = next(k for k in kinds if k)
            unbounded[name] = kind == 'cache'
            maxsize_zero = False
            if isinstance(decorator, ast.Call):
                if any(isinstance(a, ast.Starred) for a in decorator.args) or any(k.arg is None for k in decorator.keywords):
                    refuse(decorator, 'functools.lru_cache: * arguments are not built')
                for keyword in decorator.keywords:
                    if keyword.arg not in ('maxsize', 'typed'):
                        refuse(decorator, 'functools.lru_cache: the argument %s= is not built' % keyword.arg)
                values = list(decorator.args) + [k.value for k in decorator.keywords if k.arg == 'maxsize']
                if values and isinstance(values[0], ast.Constant) and values[0].value == 0:
                    maxsize_zero = True
                elif values and not (isinstance(values[0], ast.Constant) and (values[0].value is None or type(values[0].value) is int)):
                    refuse(decorator, 'functools.lru_cache(maxsize=...) needs an int literal or None')
                if values and isinstance(values[0], ast.Constant) and values[0].value is None:
                    unbounded[name] = True
            fn.decorator_list = []
            if not maxsize_zero:
                cached[name] = fn
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
                for d in node.decorator_list:
                    if self.cache_kind(d):
                        refuse(node, 'functools.lru_cache / cache on a method or nested function is not built; '
                               'decorate a top-level function')
        if not cached:
            return
        for name, fn in cached.items():
            self.validate(fn, functions, cached)
        calls = {name: self.callees(fn, functions) for name, fn in functions.items()}
        need = {name: set(cached) & {name} for name in functions}
        changed = True
        while changed:
            changed = False
            for name in functions:
                for callee in calls[name]:
                    if not need[callee] <= need[name]:
                        need[name] |= need[callee]
                        changed = True
        own = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        if '_AilCacheInfo' not in own:
            self.cacheinfo_used = self.rewrite_cache_info(tree, cached, unbounded)
        else:
            self.cacheinfo_used = False
        self.check_uses(functions, need)
        callers = {name: set() for name in functions}
        for name, callees in calls.items():
            for callee in callees:
                if callee != name:
                    callers[callee].add(name)
        # new definitions
        classes, wrappers = [], []
        info = {}
        for name, fn in cached.items():
            info[name] = self.describe(fn)
            classes.append(self.memo_class(name, info[name]))
        if self.cacheinfo_used:
            classes.append(self.cache_info_class())
        for name in cached:
            fn = cached[name]
            wrappers.append(self.split(fn, info[name], need))
        for name, fn in functions.items():
            if not need[name] or name in cached:
                continue
            memos = sorted(need[name])
            self.thread(fn, need)
            if callers[name]:
                fn.args.args.extend(ast.arg(arg='_m_' + m, annotation=ast.Name(id='_AilMemo_' + m, ctx=ast.Load()))
                                    for m in memos)
            else:
                prologue = [ast.Assign(targets=[ast.Name(id='_m_' + m, ctx=ast.Store())],
                                       value=_call(ast.Name(id='_AilMemo_' + m, ctx=ast.Load()),
                                                   ast.Dict(keys=[], values=[]))) for m in memos]
                for stmt in prologue:
                    _mark(stmt)
                    ast.copy_location(stmt, fn)
                body = fn.body
                keep = 1 if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) else 0
                fn.body = body[:keep] + prologue + body[keep:]
        # module-level calls into threaded functions
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                continue
            for each in ast.walk(node):
                if isinstance(each, ast.Call) and isinstance(each.func, ast.Name) and each.func.id in need \
                        and need[each.func.id] and callers[each.func.id]:
                    refuse(each, '%s() uses a functools cache and is called from other functions too; calling it at '
                           'module level cannot hand it the cache: call it from main()' % each.func.id)
        # splice: classes first, the wrapper pairs replace the cached functions
        body = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in cached:
                body.extend(wrappers[list(cached).index(node.name)])
            else:
                body.append(node)
        index = 0
        while index < len(body) and (isinstance(body[index], (ast.Import, ast.ImportFrom))
                                     or (isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
            index += 1
        tree.body = body[:index] + classes + body[index:]

    # -- checks ---------------------------------------------------------------------------------------
    def describe(self, fn):
        keys = []
        for arg in fn.args.args:
            keys.append(ann_name(arg.annotation))
        result = ann_name(fn.returns)
        return keys, result

    def validate(self, fn, functions, cached):
        a = fn.args
        if a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.posonlyargs or not a.args:
            refuse(fn, 'functools cache on %s: the function needs positional parameters without defaults' % fn.name)
        for arg in a.args:
            if ann_name(arg.annotation) not in KEY_TYPES:
                refuse(fn, 'functools cache on %s: parameter %s has to be annotated int, str or bool (hashable '
                       'scalars; a float or list argument is not built)' % (fn.name, arg.arg))
        if ann_name(fn.returns) not in VALUE_TYPES:
            refuse(fn, 'functools cache on %s: the result has to be annotated int, float, str or bool' % fn.name)
        reason = self.impure(fn, functions, set())
        if reason:
            refuse(fn, 'functools cache on %s: it has to be a pure function, but %s' % (fn.name, reason))

    def impure(self, fn, functions, seen):
        if fn.name in seen:
            return None
        seen.add(fn.name)
        for node in ast.walk(fn):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                return 'it uses global / nonlocal'
            if isinstance(node, (ast.FunctionDef, ast.Lambda, ast.AsyncFunctionDef)) and node is not fn:
                return 'it defines a nested function'
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    if f.id in IMPURE_NAMES:
                        return 'it calls %s()' % f.id
                    if f.id in self.imports.names and self.imports.names[f.id][0] == 'random':
                        return 'it calls random.%s' % self.imports.names[f.id][1]
                    if f.id in functions and f.id != fn.name:
                        sub = self.impure(functions[f.id], functions, seen)
                        if sub:
                            return 'it calls %s, which is not pure (%s)' % (f.id, sub)
                else:
                    root = f
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if isinstance(root, ast.Name) and (root.id in IMPURE_ROOTS
                                                       or self.imports.aliases.get(root.id) == 'random'):
                        return 'it uses %s' % root.id
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in IMPURE_ROOTS:
                return 'it uses %s' % node.value.id
        return None

    def callees(self, fn, functions):
        out = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
                out.add(node.func.id)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'cache_info' and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in functions and not node.args and not node.keywords):
                out.add(node.func.value.id)
        return out

    def rewrite_cache_info(self, tree, cached, unbounded):
        """`f.cache_info()` of an unbounded cache, inside a function that gets the cache, is the CacheInfo
        object built from the memo: hits / misses / maxsize=None / currsize=len(d)."""
        used = [False]

        def field(memo, attr):
            return ast.Attribute(value=ast.Name(id=memo, ctx=ast.Load()), attr=attr, ctx=ast.Load())

        class Rewrite(ast.NodeTransformer):
            depth = 0

            def visit_FunctionDef(self, node):
                self.depth += 1
                self.generic_visit(node)
                self.depth -= 1
                return node

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                f = node.func
                if (self.depth and isinstance(f, ast.Attribute) and f.attr == 'cache_info'
                        and isinstance(f.value, ast.Name) and f.value.id in cached
                        and unbounded.get(f.value.id) and not node.args and not node.keywords):
                    memo = '_m_' + f.value.id
                    new = ast.Call(func=ast.Name(id='_AilCacheInfo', ctx=ast.Load()),
                                   args=[field(memo, 'hits'), field(memo, 'misses'), ast.Constant(value=None),
                                         ast.Call(func=ast.Name(id='len', ctx=ast.Load()),
                                                  args=[field(memo, 'd')], keywords=[])],
                                   keywords=[])
                    used[0] = True
                    return ast.copy_location(new, node)
                return self.generic_visit(node)

        Rewrite().visit(tree)
        return used[0]

    def check_uses(self, functions, need):
        """A threaded function may only be called by name (a call passes the caches on)."""
        for fn in functions.values():
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and node.attr in ('cache_info', 'cache_clear', 'cache_parameters',
                                                                      '__wrapped__'):
                    refuse(node, 'functools cache: .%s is not built' % node.attr)
        called = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(id(node.func))
        for tree_node in ast.walk(self.tree):
            if isinstance(tree_node, ast.Name) and tree_node.id in need and need[tree_node.id] \
                    and isinstance(tree_node.ctx, ast.Load) and id(tree_node) not in called:
                refuse(tree_node, 'functools cache: %s is used as a value; call it by name (the cache travels as an '
                       'extra argument of every call)' % tree_node.id)

    # -- building -------------------------------------------------------------------------------------
    def key_type(self, keys):
        if len(keys) == 1:
            return 'int' if keys[0] in ('int', 'bool') else 'str'
        return 'str'

    def value_type(self, result):
        return 'int' if result == 'bool' else result

    def memo_class(self, name, info):
        keys, result = info
        text = textwrap.dedent('''
            class _AilMemo_%s:
                def __init__(self, d: dict[%s, %s]):
                    self.d = d
                    self.hits: int = 0
                    self.misses: int = 0
        ''' % (name, self.key_type(keys), self.value_type(result)))
        node = ast.parse(text).body[0]
        _mark(node)
        return node

    def cache_info_class(self):
        text = textwrap.dedent('''
            class _AilCacheInfo:
                def __init__(self, hits: int, misses: int, maxsize: int | None, currsize: int):
                    self.hits = hits
                    self.misses = misses
                    self.maxsize = maxsize
                    self.currsize = currsize

                def __repr__(self) -> str:
                    return ("CacheInfo(hits=" + str(self.hits) + ", misses=" + str(self.misses)
                            + ", maxsize=" + str(self.maxsize) + ", currsize=" + str(self.currsize) + ")")

                def __str__(self) -> str:
                    return self.__repr__()
        ''')
        node = ast.parse(text).body[0]
        _mark(node)
        return node

    def key_expr(self, fn, keys):
        names = [a.arg for a in fn.args.args]
        parts = []
        for arg, kind in zip(names, keys):
            if kind == 'int':
                parts.append('str(%s)' % arg)
            elif kind == 'bool':
                parts.append('str(int(%s))' % arg)
            else:
                parts.append('str(len(%s)) + ":" + %s' % (arg, arg))
        if len(keys) == 1:
            if keys[0] == 'int':
                return ast.parse(names[0], mode='eval').body
            if keys[0] == 'bool':
                return ast.parse('int(%s)' % names[0], mode='eval').body
            return ast.parse(names[0], mode='eval').body
        return ast.parse(' + "," + '.join('(%s)' % p for p in parts), mode='eval').body

    def split(self, fn, info, need):
        """[wrapper, body]: the wrapper looks the call up; the body is the original function."""
        keys, result = info
        name = fn.name
        memos = sorted(need[name])
        params = [a.arg for a in fn.args.args]
        extra = [ast.arg(arg='_m_' + m, annotation=ast.Name(id='_AilMemo_' + m, ctx=ast.Load())) for m in memos]
        body_name = '_ail_body_' + name
        body_fn = copy.deepcopy(fn)
        body_fn.name = body_name
        body_fn.args.args = list(body_fn.args.args) + [copy.deepcopy(e) for e in extra]
        key = self.key_expr(fn, keys)
        forward = [ast.Name(id=p, ctx=ast.Load()) for p in params] + [ast.Name(id='_m_' + m, ctx=ast.Load()) for m in memos]
        self_memo = '_m_' + name
        read = ast.parse('%s.d[_ail_k]' % self_memo, mode='eval').body
        stored = _call(ast.Name(id='int', ctx=ast.Load()), ast.Name(id='_ail_r', ctx=ast.Load())) \
            if result == 'bool' else ast.Name(id='_ail_r', ctx=ast.Load())
        got = ast.Compare(left=read, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)]) if result == 'bool' else read
        def bump(field):
            return ast.Assign(
                targets=[ast.Attribute(value=ast.Name(id=self_memo, ctx=ast.Load()), attr=field, ctx=ast.Store())],
                value=ast.BinOp(left=ast.Attribute(value=ast.Name(id=self_memo, ctx=ast.Load()), attr=field,
                                                   ctx=ast.Load()), op=ast.Add(), right=ast.Constant(value=1)))
        wrapper = ast.FunctionDef(
            name=name,
            args=ast.arguments(posonlyargs=[], args=[copy.deepcopy(a) for a in fn.args.args] + extra, vararg=None,
                               kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=[
                ast.Assign(targets=[ast.Name(id='_ail_k', ctx=ast.Store())], value=key),
                ast.If(test=ast.Compare(left=ast.Name(id='_ail_k', ctx=ast.Load()), ops=[ast.In()],
                                        comparators=[ast.parse('%s.d' % self_memo, mode='eval').body]),
                       body=[bump('hits'), ast.Return(value=got)], orelse=[]),
                bump('misses'),
                ast.Assign(targets=[ast.Name(id='_ail_r', ctx=ast.Store())],
                           value=ast.Call(func=ast.Name(id=body_name, ctx=ast.Load()), args=forward, keywords=[])),
                ast.Assign(targets=[ast.Subscript(value=ast.parse('%s.d' % self_memo, mode='eval').body,
                                                  slice=ast.Name(id='_ail_k', ctx=ast.Load()), ctx=ast.Store())],
                           value=stored),
                ast.Return(value=ast.Name(id='_ail_r', ctx=ast.Load()))],
            decorator_list=[], returns=copy.deepcopy(fn.returns), type_comment=None)
        for node in (wrapper, body_fn):
            ast.copy_location(node, fn)
            for each in ast.walk(node):
                if 'lineno' in getattr(each, '_attributes', ()) and not hasattr(each, 'lineno'):
                    ast.copy_location(each, fn)
            _mark(node)
        # the body keeps calling the cached function by its own name, which is the wrapper: thread those calls
        self.thread(body_fn, need)
        return [wrapper, body_fn]

    def thread(self, fn, need):
        """Pass the caches on in every call to a function that needs them."""
        class Pass(ast.NodeTransformer):
            def visit_Call(self, call):
                self.generic_visit(call)
                if isinstance(call.func, ast.Name) and call.func.id in need and need[call.func.id] \
                        and not getattr(call, '_ail_threaded', False):
                    call.args = list(call.args) + [ast.Name(id='_m_' + m, ctx=ast.Load()) for m in sorted(need[call.func.id])]
                    call._ail_threaded = True
                return call
        Pass().visit(fn)


# ---- cmp_to_key ---------------------------------------------------------------------------------
SORT_TEMPLATE = '''
t_n = len(X)
t_idx = [t_g for t_g in range(t_n)]
t_buf = [t_g for t_g in range(t_n)]
t_w = 1
while t_w < t_n:
    t_lo = 0
    while t_lo < t_n:
        t_mid = t_lo + t_w
        if t_mid > t_n:
            t_mid = t_n
        t_hi = t_lo + 2 * t_w
        if t_hi > t_n:
            t_hi = t_n
        t_l = t_lo
        t_r = t_mid
        t_o = t_lo
        while t_l < t_mid and t_r < t_hi:
            if CMP < 0:
                t_buf[t_o] = t_idx[t_r]
                t_r += 1
            else:
                t_buf[t_o] = t_idx[t_l]
                t_l += 1
            t_o += 1
        while t_l < t_mid:
            t_buf[t_o] = t_idx[t_l]
            t_l += 1
            t_o += 1
        while t_r < t_hi:
            t_buf[t_o] = t_idx[t_r]
            t_r += 1
            t_o += 1
        t_lo = t_lo + 2 * t_w
    t_k = 0
    while t_k < t_n:
        t_idx[t_k] = t_buf[t_k]
        t_k += 1
    t_w = t_w * 2
'''


class CmpSort:
    """sorted(xs, key=cmp_to_key(f)) and xs.sort(key=cmp_to_key(f))."""
    def __init__(self, lib):
        self.lib = lib

    def cmp_function(self, keynode):
        """f when `keynode` is cmp_to_key(f) (f a module-level function name), else None."""
        if isinstance(keynode, ast.Call) and self.lib.imports.resolve(keynode.func) == ('functools', 'cmp_to_key'):
            if len(keynode.args) != 1 or keynode.keywords or not isinstance(keynode.args[0], ast.Name):
                refuse(keynode, 'functools.cmp_to_key(f): f has to be a function name')
            return keynode.args[0]
        return None

    def sort_statements(self, source, func, reverse_node, origin):
        lib = self.lib
        if not isinstance(source, ast.Name):
            refuse(origin, 'sorting with cmp_to_key: the list has to be held in a variable')
        if lib.current_lists is not None and source.id not in lib.current_lists:
            refuse(origin, 'sorting with cmp_to_key: %s is not known to be a list here' % source.id)
        if not self.pure_function(func.id):
            refuse(origin, 'cmp_to_key(%s): the comparison function has to be pure (the sort calls it a different '
                   'number of times than CPython does)' % func.id)
        template_text = SORT_TEMPLATE
        mapping = {}
        probe = ast.parse(textwrap.dedent(template_text))
        for each in ast.walk(probe):
            if isinstance(each, ast.Name) and each.id.startswith('t_') and each.id not in mapping:
                mapping[each.id] = lib.fresh(each.id[2:])
        compare = ast.parse('%s(X[A], X[B])' % func.id, mode='eval').body
        reverse = 'False'
        if reverse_node is not None:
            if not (isinstance(reverse_node, ast.Constant) and isinstance(reverse_node.value, bool)):
                refuse(origin, 'sorting with cmp_to_key: reverse= has to be True or False')
            reverse = str(reverse_node.value)
        # the comparison reads the two candidates through the index lists: left = idx[l], right = idx[r]
        text = template_text.replace('CMP', '_ph_cmp')
        module = ast.parse(textwrap.dedent(text))
        renamer = _Rename(mapping)

        class Fill(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == '_ph_cmp':
                    call = copy.deepcopy(compare)
                    call.args[0].value = copy.deepcopy(source)
                    call.args[1].value = copy.deepcopy(source)
                    call.args[0].slice = ast.Subscript(value=ast.Name(id=mapping['t_idx'], ctx=ast.Load()),
                                                       slice=ast.Name(id=mapping['t_r'], ctx=ast.Load()), ctx=ast.Load())
                    call.args[1].slice = ast.Subscript(value=ast.Name(id=mapping['t_idx'], ctx=ast.Load()),
                                                       slice=ast.Name(id=mapping['t_l'], ctx=ast.Load()), ctx=ast.Load())
                    return call
                if node.id == 'X':
                    return copy.deepcopy(source)
                return node
        body = Fill().visit(renamer.visit(module)).body
        if reverse == 'True':
            # reverse, sort stably, reverse: equal elements keep their original order
            order = ast.parse('%s = [%s - 1 - %s for %s in range(%s)]' % (
                mapping['t_idx'], 'len(%s)' % source.id, mapping['t_g'], mapping['t_g'], 'len(%s)' % source.id)).body[0]
            for pos, stmt in enumerate(body):
                if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == mapping['t_idx']:
                    body[pos] = order
                    break
            body.append(ast.parse('%s.reverse()' % mapping['t_idx']).body[0])
        for stmt in body:
            _mark(stmt)
        _locate(body, origin)
        return body, mapping['t_idx']

    def pure_function(self, name):
        for node in self.lib.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return Memo(self.lib.imports, self.lib.tree).impure(
                    node, {n.name: n for n in self.lib.tree.body if isinstance(n, ast.FunctionDef)}, set()) is None
        return False

    def hoist(self, e):
        """sorted(xs, key=cmp_to_key(f)[, reverse=b]) -> (list expression, statements)."""
        if not (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == 'sorted'):
            return None
        keys = [k for k in e.keywords if k.arg == 'key']
        if not keys:
            return None
        func = self.cmp_function(keys[0].value)
        if func is None:
            return None
        others = [k for k in e.keywords if k.arg not in ('key', 'reverse')]
        if len(e.args) != 1 or others:
            refuse(e, 'sorted(..., key=cmp_to_key(f)) takes the list and key= / reverse= only')
        reverse = next((k.value for k in e.keywords if k.arg == 'reverse'), None)
        source = e.args[0]
        body, idx = self.sort_statements(source, func, reverse, e)
        gather = self.lib.fresh('g')
        result = self.lib.fresh('sorted')
        make = ast.Assign(targets=[ast.Name(id=result, ctx=ast.Store())], value=ast.ListComp(
            elt=ast.Subscript(value=copy.deepcopy(source), slice=ast.Name(id=gather, ctx=ast.Load()), ctx=ast.Load()),
            generators=[ast.comprehension(target=ast.Name(id=gather, ctx=ast.Store()),
                                          iter=ast.Name(id=idx, ctx=ast.Load()), ifs=[], is_async=0)]))
        _mark(make)
        _locate([make], e)
        return _name(result), body + [make]

    def sort_statement(self, node):
        """xs.sort(key=cmp_to_key(f)) as a statement."""
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == 'sort'
                and isinstance(call.func.value, ast.Name) and not call.args):
            return None
        keys = [k for k in call.keywords if k.arg == 'key']
        if not keys:
            return None
        func = self.cmp_function(keys[0].value)
        if func is None:
            return None
        others = [k for k in call.keywords if k.arg not in ('key', 'reverse')]
        if others:
            refuse(call, 'list.sort(key=cmp_to_key(f)) takes key= / reverse= only')
        reverse = next((k.value for k in call.keywords if k.arg == 'reverse'), None)
        source = call.func.value
        body, idx = self.sort_statements(source, func, reverse, node)
        gather = self.lib.fresh('g')
        make = ast.Assign(targets=[ast.Name(id=source.id, ctx=ast.Store())], value=ast.ListComp(
            elt=ast.Subscript(value=copy.deepcopy(source), slice=ast.Name(id=gather, ctx=ast.Load()), ctx=ast.Load()),
            generators=[ast.comprehension(target=ast.Name(id=gather, ctx=ast.Store()),
                                          iter=ast.Name(id=idx, ctx=ast.Load()), ifs=[], is_async=0)]))
        _mark(make)
        body.append(make)
        _locate(body, node)
        return body
