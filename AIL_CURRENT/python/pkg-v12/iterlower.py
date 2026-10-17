"""Iterator spellings lowered to the loops and comprehensions the compiler already builds.

Run once on the parsed module (pyfunc `_to_c_once`), before any other pass looks at it, so every later
pass sees ordinary code. Each rewrite keeps CPython's order of evaluation:

* `for T in map(F, X):`      -> `for _m in X: T = F(_m); ...`   (F runs at each step, as map's does)
* `for T in filter(P, X):`   -> `for _f in X: if P(_f): T = _f; ...`
* `for a, b in zip(X, Y):`   -> an index loop that re-reads len() at every step (a list the body
  grows is walked on, as zip's list iterators do), when every argument is KNOWN to be a sequence
  (a list / str / bytes bound only to such values in this function, a slice, a range(n) /
  range(a, b)); anything else is left exactly as written.
* `list(map(F, X))`, `sum(map(...))`, `"".join(map(str, X))`, `sorted(filter(...))`, ... -> the
  comprehension or generator of the same elements. The consumer reads every element before it
  returns, so nothing observable moves.
* `max(X, key=K)` / `min` in the first-evaluated position of a statement (`v = ...`, `return ...`,
  `print(...)`) over a known sequence or a range -> one pass keeping the first best element (K once
  per element, in order, the `>` / `<` CPython compares with), ValueError on an empty sequence,
  ahead of the statement.
* `with open(path, "w"|"wb"|"a"|"ab") as f:` with only `f.write(x)` statements in the body -> the file
  is created or emptied, the writes collect in a buffer, and a `finally` appends it (write_text /
  append_bytes, which the language already has).
* `d = {K: V for T in X if C}` -> `d = {}` and the loops, the comprehension variables renamed so
  nothing leaks into the function (Python scopes them to the comprehension).
"""
import ast
import copy

_SEQ_CONSUMERS_LIST = ('list', 'sorted', 'set')
_SEQ_CONSUMERS_GEN = ('sum', 'min', 'max', 'any', 'all')
_SEQ_ANN = ('list', 'List', 'str', 'bytes')
_SEQ_METHODS = ('split', 'rsplit', 'splitlines', 'encode', 'decode', 'strip', 'lstrip', 'rstrip',
                'upper', 'lower', 'replace', 'join', 'format', 'read', 'readline')
_SEQ_CALLS = ('list', 'sorted', 'str', 'bytes', 'input')
_TYPE_METHODS = ('strip', 'lstrip', 'rstrip', 'upper', 'lower', 'title', 'capitalize', 'swapcase',
                 'isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower')

def _mark(node):
    """Flag every name of a node written here `_ail_synth`: the statements built here share their
    source line, so source order cannot say which mention of a name is last, and the compiler keeps
    a flagged name (and the storage behind it) until the function returns (pyfunc
    `_last_use_free_points`)."""
    for each in ast.walk(node):
        if isinstance(each, ast.Name):
            each._ail_synth = True
    return node


def _name(id_, store=False):
    return _mark(ast.Name(id=id_, ctx=ast.Store() if store else ast.Load()))


def _call(func, *args):
    return ast.Call(func=func, args=list(args), keywords=[])


class _Subst(ast.NodeTransformer):
    """Replace Load uses of one name by a copy of an expression."""
    def __init__(self, name, replacement):
        self.name, self.replacement = name, replacement

    def visit_Name(self, node):
        if node.id == self.name and isinstance(node.ctx, ast.Load):
            return copy.deepcopy(self.replacement)
        return node


class _Rename(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        if node.id in self.mapping:
            return ast.copy_location(ast.Name(id=self.mapping[node.id], ctx=node.ctx), node)
        return node


def _rebinds(node, name):
    """Whether `name` is bound again inside `node` (a lambda parameter, a comprehension variable...)."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name and not isinstance(child.ctx, ast.Load):
            return True
        if isinstance(child, ast.arg) and child.arg == name:
            return True
    return False


def _locate(statements, origin):
    """Give every new node of `statements` that has no source location the location of `origin`."""
    for each in statements:
        for child in ast.walk(each):
            if 'lineno' in getattr(child, '_attributes', ()) and not hasattr(child, 'lineno'):
                ast.copy_location(child, origin)


class _Lower:
    def __init__(self):
        self.count = 0
        self.helpers = set()

    def fresh(self, stem):
        self.count += 1
        return '_il%d_%s' % (self.count, stem)

    # -- what is known to be a sequence ----------------------------------------------------------
    def seq_expr(self, node):
        if isinstance(node, (ast.List, ast.ListComp)):
            return True
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, bytes))
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id in _SEQ_CALLS
            if isinstance(node.func, ast.Attribute):
                return node.func.attr in _SEQ_METHODS
            return False
        if isinstance(node, ast.Subscript):
            return isinstance(node.slice, ast.Slice)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
            return self.seq_expr(node.left) or self.seq_expr(node.right) and isinstance(node.op, ast.Mult)
        return False

    def known_sequences(self, fn):
        """Names of `fn` whose every binding is a sequence-producing expression."""
        good, bad = set(), set()
        for arg in (*fn.args.args, *fn.args.kwonlyargs):
            ann = arg.annotation
            head = ann.value if isinstance(ann, ast.Subscript) else ann
            if isinstance(head, ast.Name) and head.id in _SEQ_ANN:
                good.add(arg.arg)
            else:
                bad.add(arg.arg)
        if fn.args.vararg:
            bad.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            bad.add(fn.args.kwarg.arg)
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        (good if self.seq_expr(node.value) else bad).add(target.id)
                    else:
                        bad.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                head = node.annotation.value if isinstance(node.annotation, ast.Subscript) else node.annotation
                ok = isinstance(head, ast.Name) and head.id in _SEQ_ANN
                (good if ok else bad).add(node.target.id)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                if not isinstance(node.op, ast.Add):
                    bad.add(node.target.id)
            elif isinstance(node, (ast.For, ast.comprehension)):
                bad.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
            elif isinstance(node, ast.NamedExpr):
                bad.add(node.target.id)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        bad.update(n.id for n in ast.walk(item.optional_vars) if isinstance(n, ast.Name))
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bad.add(node.name)
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                bad.update(node.names)
            elif isinstance(node, ast.Delete):
                bad.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node is not fn:
                bad.add(node.name)
        return good - bad

    # -- function reference applied to an element ---------------------------------------------------
    def apply(self, func, arg):
        """`func(arg)` for a lambda (inlined), a builtin type method spelled `str.strip`, or any callable
        expression; None when the shape is not one of those."""
        if isinstance(func, ast.Lambda):
            a = func.args
            if (len(a.args) != 1 or a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.posonlyargs):
                return None
            param = a.args[0].arg
            body = copy.deepcopy(func.body)
            if _rebinds(body, param):
                return None
            return _mark(_Subst(param, arg).visit(body))
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'str'
                and func.attr in _TYPE_METHODS):
            return _call(ast.Attribute(value=arg, attr=func.attr, ctx=ast.Load()))
        if isinstance(func, (ast.Name, ast.Attribute)):
            return _mark(_call(copy.deepcopy(func), arg))
        return None

    def truth(self, pred, arg):
        if isinstance(pred, ast.Constant) and pred.value is None:
            return _mark(copy.deepcopy(arg))
        return self.apply(pred, arg)

    # -- expressions ------------------------------------------------------------------------------
    def as_comprehension(self, node, generator):
        """`map(F, X)` / `filter(P, X)` as a ListComp or GeneratorExp over X, or None."""
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('map', 'filter')
                and not node.keywords and not any(isinstance(a, ast.Starred) for a in node.args)):
            return None
        if len(node.args) != 2:
            return None
        function, source = node.args
        var = self.fresh('e')
        arg = _name(var)
        build = ast.GeneratorExp if generator else ast.ListComp
        if node.func.id == 'map':
            element = self.apply(function, arg)
            ifs = []
            if element is None:
                return None
            target_value = element
        else:
            test = self.truth(function, arg)
            if test is None:
                return None
            target_value, ifs = _mark(copy.deepcopy(arg)), [test]
        comp = ast.comprehension(target=_name(var, True), iter=self.expr(source), ifs=ifs, is_async=0)
        return ast.copy_location(build(elt=target_value, generators=[comp]), node)

    def expr(self, node):
        """Rewrite the lowerable calls inside an expression (bottom-up)."""
        lower = self

        class Visitor(ast.NodeTransformer):
            def visit_Call(self, call):
                self.generic_visit(call)
                func = call.func
                if (isinstance(func, ast.Name) and func.id == 'int' and len(call.args) == 1
                        and len(call.keywords) == 1 and call.keywords[0].arg == 'base'):
                    call.args = [call.args[0], call.keywords[0].value]       # int(s, base=16) is int(s, 16)
                    call.keywords = []
                    return call
                if isinstance(func, ast.Name) and len(call.args) == 1:
                    arg = call.args[0]
                    if func.id in _SEQ_CONSUMERS_LIST and not (func.id != 'sorted' and call.keywords):
                        comp = lower.as_comprehension(arg, False)
                        if comp is not None:
                            if func.id == 'list':
                                return comp
                            call.args = [comp]
                            return call
                    if func.id in ('any', 'all') and not call.keywords:
                        # these stop early, so they keep a generator (and its lazy evaluation)
                        comp = lower.as_comprehension(arg, True)
                        if comp is not None:
                            call.args = [comp]
                            return call
                if (isinstance(func, ast.Attribute) and func.attr == 'join' and len(call.args) == 1
                        and not call.keywords):
                    comp = lower.as_comprehension(call.args[0], False)
                    if comp is not None:
                        call.args = [comp]
                        return call
                return call

        return Visitor().visit(node)

    def hoist(self, e):
        """(expression, statements): the first-evaluated `sum|min|max(map|filter(...))` inside `e` becomes
        a call over a list built by a statement ahead of the one that holds `e`. Only the first-evaluated
        position is touched (left operand, receiver, first argument, first `and`/`or` operand, past
        constants and names only), so no other part of the statement is reordered or made conditional."""
        if (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('sum', 'min', 'max')
                and len(e.args) == 1 and not e.keywords):
            comp = self.as_comprehension(e.args[0], False)
            if comp is not None:
                temp = self.fresh('l')
                assign = ast.Assign(targets=[_name(temp, True)], value=comp)
                e.args = [_name(temp)]
                return e, [assign]
        if (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('max', 'min')
                and len(e.args) == 1 and len(e.keywords) == 1 and e.keywords[0].arg == 'key'):
            lowered = self.keyed(e)
            if lowered is not None:
                return lowered[1], lowered[0]
        def first(operands):
            """hoist the first operand that can be: only constants and names (no code runs, nothing
            changes) may sit to its left, so the evaluation order of the statement is untouched"""
            for index, operand in enumerate(operands):
                new, pre = self.hoist(operand)
                operands[index] = new
                if pre or not isinstance(operand, (ast.Constant, ast.Name)):
                    return pre
            return []

        if isinstance(e, ast.BinOp):
            pair = [e.left, e.right]
            pre = first(pair)
            e.left, e.right = pair
        elif isinstance(e, ast.Compare):
            pair = [e.left, *e.comparators]
            pre = first(pair)
            e.left, e.comparators = pair[0], pair[1:]
        elif isinstance(e, ast.UnaryOp):
            e.operand, pre = self.hoist(e.operand)
        elif isinstance(e, (ast.Attribute, ast.Subscript)):
            e.value, pre = self.hoist(e.value)
        elif isinstance(e, ast.BoolOp):
            e.values[0], pre = self.hoist(e.values[0])
        elif isinstance(e, ast.Call):
            if isinstance(e.func, ast.Attribute):
                e.func.value, pre = self.hoist(e.func.value)
                if not pre and isinstance(e.func.value, (ast.Constant, ast.Name)):
                    pre = first(e.args)
            else:
                pre = first(e.args)
        elif isinstance(e, ast.Tuple):
            pre = first(e.elts)
        elif isinstance(e, ast.IfExp):
            e.test, pre = self.hoist(e.test)
        else:
            pre = []
        return e, pre

    def keyed(self, call):
        """`max(X, key=K)` / `min(...)` as (statements, element expression): one pass that keeps the first
        best element, K applied once per element in order, ValueError when X is empty -- CPython's own
        algorithm, hoisted ahead of the statement that needs the value."""
        source, key = call.args[0], call.keywords[0].value
        is_max = call.func.id == 'max'
        index, best_index, best_key, count = (self.fresh(n) for n in ('i', 'bi', 'bk', 'n'))
        pre = []
        if isinstance(source, ast.Name) and source.id in self.sequences:
            def element(position):
                return ast.Subscript(value=_name(source.id), slice=position, ctx=ast.Load())
            pre.append(ast.Assign(targets=[_name(count, True)], value=_call(_name('len'), _name(source.id))))
        elif (isinstance(source, ast.Call) and isinstance(source.func, ast.Name) and source.func.id == 'range'
              and not source.keywords and 1 <= len(source.args) <= 2):
            if len(source.args) == 1:
                pre.append(ast.Assign(targets=[_name(count, True)], value=self.expr(source.args[0])))
                def element(position):
                    return position
            else:
                start = self.fresh('a')
                pre.append(ast.Assign(targets=[_name(start, True)], value=self.expr(source.args[0])))
                pre.append(ast.Assign(targets=[_name(count, True)], value=ast.BinOp(
                    left=self.expr(source.args[1]), op=ast.Sub(), right=_name(start))))
                def element(position):
                    return ast.BinOp(left=_name(start), op=ast.Add(), right=position)
        else:
            return None
        first = self.apply(key, element(ast.Constant(value=0)))
        each = self.apply(key, element(_name(index)))
        if first is None or each is None:
            return None
        word = 'max' if is_max else 'min'
        pre.append(ast.If(test=ast.Compare(left=_name(count), ops=[ast.LtE()], comparators=[ast.Constant(value=0)]),
                          body=[ast.Raise(exc=_call(_name('ValueError'), ast.Constant(
                              value='%s() iterable argument is empty' % word)), cause=None)], orelse=[]))
        step = fresh_key = self.fresh('k')
        pre.append(ast.Assign(targets=[_name(best_index, True)], value=ast.Constant(value=0)))
        pre.append(ast.Assign(targets=[_name(best_key, True)], value=self.expr(first)))
        pre.append(ast.Assign(targets=[_name(index, True)], value=ast.Constant(value=1)))
        better = ast.Compare(left=_name(fresh_key), ops=[ast.Gt() if is_max else ast.Lt()],
                             comparators=[_name(best_key)])
        pre.append(ast.While(
            test=ast.Compare(left=_name(index), ops=[ast.Lt()], comparators=[_name(count)]),
            body=[ast.Assign(targets=[_name(fresh_key, True)], value=self.expr(each)),
                  ast.If(test=better, body=[ast.Assign(targets=[_name(best_key, True)], value=_name(fresh_key)),
                                            ast.Assign(targets=[_name(best_index, True)], value=_name(index))],
                         orelse=[]),
                  ast.AugAssign(target=_name(index, True), op=ast.Add(), value=ast.Constant(value=1))],
            orelse=[]))
        return pre, element(_name(best_index))

    # -- statements -------------------------------------------------------------------------------
    def block(self, stmts):
        out = []
        for stmt in stmts:
            out.extend(self.stmt(stmt))
        return out

    def stmt(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            saved = getattr(self, 'sequences', set())
            self.sequences = self.known_sequences(node)
            node.body = self.block(node.body)
            self.sequences = saved
            return [node]
        if isinstance(node, ast.ClassDef):
            node.body = self.block(node.body)
            return [node]
        if isinstance(node, ast.For):
            lowered = self.for_loop(node)
            if lowered is not None:
                return lowered
            node.iter = self.expr(node.iter)
            node.body = self.block(node.body)
            node.orelse = self.block(node.orelse)
            return [node]
        if isinstance(node, ast.If):
            node.test, pre = self.hoist(node.test)      # an `if` tests once, so it may be hoisted ahead of it
            if pre:
                _locate(pre, node)
                return self.block(pre) + self.stmt(node)
        if isinstance(node, (ast.While, ast.If)):
            node.test = self.expr(node.test)
            node.body = self.block(node.body)
            node.orelse = self.block(node.orelse)
            return [node]
        if isinstance(node, ast.Try):
            node.body = self.block(node.body)
            for handler in node.handlers:
                handler.body = self.block(handler.body)
            node.orelse = self.block(node.orelse)
            node.finalbody = self.block(node.finalbody)
            return [node]
        if isinstance(node, ast.With):
            lowered = self.with_open_write(node)
            if lowered is not None:
                return self.block(lowered)
            node.body = self.block(node.body)
            return [node]
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return, ast.AugAssign, ast.Expr)) \
                and getattr(node, 'value', None) is not None:
            node.value, pre = self.hoist(node.value)
            if pre:
                _locate(pre, node)
                return self.block(pre) + self.stmt(node)
        value = getattr(node, 'value', None)
        if (isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)) and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name) and value.func.id in ('max', 'min') and len(value.args) == 1
                and len(value.keywords) == 1 and value.keywords[0].arg == 'key'):
            lowered = self.keyed(value)
            if lowered is not None:
                pre, result = lowered
                node.value = result
                statements = [*pre, node]
                _locate(statements, node)
                return self.block(statements)
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.DictComp):
            lowered = self.dict_comp_assign(node)
            if lowered is not None:
                return lowered
        if isinstance(node, ast.Return) and isinstance(node.value, ast.DictComp):
            holder = self.fresh('d')
            assign = ast.copy_location(ast.Assign(targets=[_name(holder, True)], value=node.value), node)
            lowered = self.dict_comp_assign(assign)
            if lowered is not None:
                node.value = _name(holder)
                return lowered + [node]
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.expr(value))
            elif isinstance(value, list) and value and all(isinstance(v, ast.expr) for v in value):
                setattr(node, field, [self.expr(v) for v in value])
        return [node]

    def with_open_write(self, node):
        """`with open(path, "w"|"wb"|"a"|"ab") as f:` whose body only calls `f.write(x)` as statements ->
        the file is created (or emptied) first, the writes collect in a str / bytes buffer, and a
        `finally` appends the buffer with append_bytes, so the file holds what was written even when
        the body raises (as the closing `with` guarantees)."""
        if len(node.items) != 1:
            return None
        item = node.items[0]
        call = item.context_expr
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'open'
                and isinstance(item.optional_vars, ast.Name) and 1 <= len(call.args) <= 2
                and not any(isinstance(a, ast.Starred) for a in call.args)):
            return None
        mode = call.args[1] if len(call.args) == 2 else None
        for keyword in call.keywords:
            if keyword.arg == 'mode' and mode is None:
                mode = keyword.value
            elif not (keyword.arg == 'encoding' and isinstance(keyword.value, ast.Constant)
                      and str(keyword.value.value).lower().replace('-', '').replace('_', '') == 'utf8'):
                return None
        if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
            return None
        letters = ''.join(sorted(mode.value))
        binary = 'b' in letters
        if letters.replace('b', '').replace('t', '') == 'w':
            truncate = True
        elif letters.replace('b', '').replace('t', '') == 'a':
            truncate = False
        else:
            return None
        if binary and 't' in letters:
            return None
        var = item.optional_vars.id
        writes = set()
        for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == 'write'
                    and isinstance(stmt.value.func.value, ast.Name) and stmt.value.func.value.id == var
                    and len(stmt.value.args) == 1 and not stmt.value.keywords
                    and not isinstance(stmt.value.args[0], ast.Starred)):
                writes.add(id(stmt.value.func.value))
        for each in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if isinstance(each, ast.Name) and each.id == var and id(each) not in writes:
                return None
            if isinstance(each, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
                return None
        path_var, buffer = self.fresh('path'), self.fresh('buf')

        class Collect(ast.NodeTransformer):
            def visit_Expr(self, stmt):
                self.generic_visit(stmt)
                value = stmt.value
                if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == 'write'
                        and isinstance(value.func.value, ast.Name) and value.func.value.id == var):
                    return ast.copy_location(ast.Assign(
                        targets=[_name(buffer, True)],
                        value=ast.BinOp(left=_name(buffer), op=ast.Add(), right=value.args[0])), stmt)
                return stmt

        body = [Collect().visit(stmt) for stmt in node.body]
        empty = ast.Constant(value=b'' if binary else '')
        pre = [ast.Assign(targets=[_name(path_var, True)], value=call.args[0])]
        if truncate:
            pre.append(ast.Expr(value=_call(_name('write_bytes' if binary else 'write_text'),
                                            _name(path_var), copy.deepcopy(empty))))
        else:
            pre.append(ast.Expr(value=_call(_name('append_bytes'), _name(path_var),
                                            ast.Constant(value=b''))))
        pre.append(ast.Assign(targets=[_name(buffer, True)], value=copy.deepcopy(empty)))
        payload = _name(buffer) if binary else _call(ast.Attribute(value=_name(buffer), attr='encode', ctx=ast.Load()))
        flush = ast.Expr(value=_call(_name('append_bytes'), _name(path_var), payload))
        guarded = ast.Try(body=body, handlers=[], orelse=[], finalbody=[flush])
        statements = [*pre, guarded]
        _locate(statements, node)
        return statements

    def dict_comp_assign(self, node):
        comp = node.value
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                return None
        elif not isinstance(node.target, ast.Name):
            return None
        mapping, bound = {}, []
        for gen in comp.generators:
            if gen.is_async:
                return None
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name):
                    mapping[n.id] = self.fresh(n.id)
                elif not isinstance(n, (ast.Tuple, ast.List, ast.Store)):
                    return None
        parts = [comp.key, comp.value] + [c for g in comp.generators for c in g.ifs] + [g.iter for g in comp.generators[1:]]
        for part in parts:
            for inner in ast.walk(part):
                if isinstance(inner, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    return None
        renamer = _Rename(mapping)
        store = ast.Subscript(value=_name(node.targets[0].id if isinstance(node, ast.Assign) else node.target.id),
                              slice=_mark(renamer.visit(copy.deepcopy(comp.key))), ctx=ast.Store())
        inner = [ast.Assign(targets=[store], value=_mark(renamer.visit(copy.deepcopy(comp.value))))]
        for gen in reversed(comp.generators):
            for condition in reversed(gen.ifs):
                inner = [ast.If(test=_mark(renamer.visit(copy.deepcopy(condition))), body=inner, orelse=[])]
            iterable = copy.deepcopy(gen.iter)
            if gen is not comp.generators[0]:
                iterable = renamer.visit(iterable)
            _mark(iterable)
            inner = [ast.For(target=_mark(renamer.visit(copy.deepcopy(gen.target))), iter=iterable, body=inner,
                             orelse=[], type_comment=None)]
        empty = ast.Dict(keys=[], values=[])
        if isinstance(node, ast.Assign):
            head = ast.Assign(targets=node.targets, value=empty)
        else:
            head = ast.AnnAssign(target=node.target, annotation=node.annotation, value=empty, simple=node.simple)
        statements = [head] + inner
        _locate(statements, node)
        return self.block(statements)

    def for_loop(self, node):
        it = node.iter
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and not it.keywords
                and not any(isinstance(a, ast.Starred) for a in it.args)):
            return None
        if it.func.id == 'map' and len(it.args) == 2:
            var = self.fresh('m')
            element = self.apply(it.args[0], _name(var))
            if element is None:
                return None
            assign = ast.copy_location(ast.Assign(targets=[node.target], value=element), node)
            loop = ast.For(target=_name(var, True), iter=it.args[1], body=[assign] + node.body,
                           orelse=node.orelse, type_comment=None)
            return self.block([ast.copy_location(loop, node)])
        if it.func.id == 'filter' and len(it.args) == 2:
            var = self.fresh('f')
            test = self.truth(it.args[0], _name(var))
            if test is None:
                return None
            assign = ast.copy_location(ast.Assign(targets=[node.target], value=_name(var)), node)
            guard = ast.copy_location(ast.If(test=test, body=[assign] + node.body, orelse=[]), node)
            loop = ast.For(target=_name(var, True), iter=it.args[1], body=[guard], orelse=node.orelse,
                           type_comment=None)
            return self.block([ast.copy_location(loop, node)])
        if it.func.id == 'zip' and len(it.args) >= 2:
            return self.zip_loop(node)
        return None

    def zip_loop(self, node):
        args = node.iter.args
        target = node.target
        if not (isinstance(target, ast.Tuple) and len(target.elts) == len(args)
                and all(isinstance(e, ast.Name) for e in target.elts)):
            return None
        setup, conds, elements = [], [], []
        index = self.fresh('z')
        for arg in args:
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == 'range' \
                    and not arg.keywords and 1 <= len(arg.args) <= 2:
                if len(arg.args) == 1:
                    stop = self.fresh('n')
                    setup.append(ast.Assign(targets=[_name(stop, True)], value=self.expr(arg.args[0])))
                    conds.append(ast.Compare(left=_name(index), ops=[ast.Lt()], comparators=[_name(stop)]))
                    elements.append(_name(index))
                else:
                    start, stop = self.fresh('a'), self.fresh('b')
                    setup.append(ast.Assign(targets=[_name(start, True)], value=self.expr(arg.args[0])))
                    setup.append(ast.Assign(targets=[_name(stop, True)], value=self.expr(arg.args[1])))
                    position = ast.BinOp(left=_name(start), op=ast.Add(), right=_name(index))
                    conds.append(ast.Compare(left=copy.deepcopy(position), ops=[ast.Lt()], comparators=[_name(stop)]))
                    elements.append(position)
                continue
            if isinstance(arg, ast.Name) and arg.id in self.sequences:
                holder = arg.id
            elif self.seq_expr(arg):
                holder = self.fresh('s')
                setup.append(ast.Assign(targets=[_name(holder, True)], value=self.expr(arg)))
            else:
                return None
            conds.append(ast.Compare(left=_name(index), ops=[ast.Lt()],
                                     comparators=[_call(_name('len'), _name(holder))]))
            elements.append(ast.Subscript(value=_name(holder), slice=_name(index), ctx=ast.Load()))
        test = conds[0] if len(conds) == 1 else ast.BoolOp(op=ast.And(), values=conds)
        body = [ast.Assign(targets=[ast.Name(id=e.id, ctx=ast.Store())], value=el)
                for e, el in zip(target.elts, elements)]
        body.append(ast.AugAssign(target=_name(index, True), op=ast.Add(), value=ast.Constant(value=1)))
        loop = ast.While(test=test, body=body + node.body, orelse=node.orelse)
        statements = [*setup, ast.Assign(targets=[_name(index, True)], value=ast.Constant(value=0)), loop]
        _locate(statements, node)       # only nodes without a location borrow the loop's
        loop.body = body + self.block(node.body)
        loop.orelse = self.block(node.orelse)
        for each in setup:
            each.value = self.expr(each.value)
        return statements


def rewrite(tree):
    """Lower the iterator spellings in `tree` in place; returns whether anything changed."""
    source_text = ast.dump(tree)
    if not any(word in source_text for word in ("'map'", "'filter'", "'zip'", "'key'", "'base'", 'DictComp',
                                                                "'open'")):
        return False
    lower = _Lower()
    lower.sequences = set()
    tree.body = lower.block(tree.body)
    ast.fix_missing_locations(tree)
    return source_text != ast.dump(tree)
