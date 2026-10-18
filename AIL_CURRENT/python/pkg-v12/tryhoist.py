"""A `try` that sits last in a loop body and whose handlers all leave, moved outside the loop.

    while C:                      try:
        pre                           while C:
        try:             ->               pre
            body                          body
        except E:                         post
            ...; return/raise     except E:
        post                          ...; return/raise

Each `try` entered inside a loop costs a setjmp (and a handler-stack push and pop) per iteration;
hoisted, the loop pays it once. The two programs are the same when every one of these holds, and the
rewrite is made only then:

* the `try` has no `else` and no `finally`, and every handler ends in `return` or `raise` and holds no
  `break`/`continue`, so after a caught exception control never goes back round the loop;
* `C` (a `for` loop's `range(...)` arguments), `pre` and `post` cannot raise anything the handlers catch:
  they are made of names, constants, field reads, `len`, comparisons and arithmetic only, and each
  kind is charged the exceptions it can raise (an index read: IndexError, KeyError and RuntimeError; a field
  read: RuntimeError, the field of None; `+ - *` and unary minus: OverflowError; `// %` by a non-zero
  constant: OverflowError; anything else is refused),
  so a statement that was outside the `try` still cannot be caught by it;
* a name the loop assigns and a handler reads is one that is certainly assigned when the `try` runs (before
  the loop, the `for` variable, or a plain assignment ahead of the `try` in the body), so the handler sees
  the value of the moment of the raise, exactly as before, and the new nesting adds no maybe-unassigned read.

Nothing else is observable: the handlers run after the same unwinding, with the same variables, in the
same function; the loop is left for good either way. Loops are visited inside out, so a `try` that
becomes the last statement of an outer loop body is hoisted again. Run on the parsed module before
the other passes (pyfunc `_to_c_once`).
"""
import ast

# builtin exception names the handler types may use (pyfunc EXC_NAMES); anything else is left alone
_KNOWN = {'ValueError', 'ZeroDivisionError', 'IndexError', 'KeyError', 'EOFError', 'OSError',
          'FileNotFoundError', 'RuntimeError', 'UnicodeDecodeError', 'AssertionError', 'OverflowError'}
_SIMPLE_BINOPS = (ast.Add, ast.Sub, ast.Mult)
_BIT_BINOPS = (ast.BitAnd, ast.BitOr, ast.BitXor)
_COMPARES = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ALL = None                      # "may raise anything": the expression is refused


def _union(*sets):
    if any(item is _ALL for item in sets):
        return _ALL
    out = set()
    for item in sets:
        out |= item
    return out


def _expr(node, shadowed):
    """The exception names evaluating `node` can raise, or _ALL when that is not known."""
    if isinstance(node, (ast.Name, ast.Constant)):
        return set()
    if isinstance(node, ast.Attribute):
        return _union(_expr(node.value, shadowed), {'RuntimeError'})      # a field of None
    if isinstance(node, ast.Subscript):
        if isinstance(node.slice, (ast.Slice, ast.Tuple)):
            return _ALL
        return _union(_expr(node.value, shadowed), _expr(node.slice, shadowed),
                      {'IndexError', 'KeyError', 'RuntimeError'})
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return _expr(node.operand, shadowed)
        if isinstance(node.op, ast.USub):
            return _union(_expr(node.operand, shadowed), {'OverflowError'})
        return _ALL
    if isinstance(node, ast.BoolOp):
        return _union(*[_expr(value, shadowed) for value in node.values])
    if isinstance(node, ast.Compare):
        if not all(isinstance(op, _COMPARES) for op in node.ops):
            return _ALL
        return _union(_expr(node.left, shadowed), *[_expr(value, shadowed) for value in node.comparators])
    if isinstance(node, ast.IfExp):
        return _union(_expr(node.test, shadowed), _expr(node.body, shadowed), _expr(node.orelse, shadowed))
    if isinstance(node, ast.BinOp):
        both = _union(_expr(node.left, shadowed), _expr(node.right, shadowed))
        if isinstance(node.op, _SIMPLE_BINOPS):
            return _union(both, {'OverflowError'})
        if isinstance(node.op, _BIT_BINOPS):
            return both
        if (isinstance(node.op, (ast.FloorDiv, ast.Mod)) and isinstance(node.right, ast.Constant)
                and type(node.right.value) is int and node.right.value > 0):
            return _union(both, {'OverflowError'})
        return _ALL
    if isinstance(node, ast.Call):
        if (isinstance(node.func, ast.Name) and node.func.id == 'len' and 'len' not in shadowed
                and len(node.args) == 1 and not node.keywords):
            return _expr(node.args[0], shadowed)
        return _ALL
    return _ALL


def _block(body, shadowed, in_loop=False):
    """The exception names a statement list can raise, or _ALL. `break`/`continue` count only inside
    a loop that belongs to the list (one that would leave or repeat the hoisted loop is refused)."""
    out = set()
    for statement in body:
        found = _statement(statement, shadowed, in_loop)
        if found is _ALL:
            return _ALL
        out |= found
    return out


def _statement(node, shadowed, in_loop):
    if isinstance(node, ast.Pass):
        return set()
    if isinstance(node, (ast.Break, ast.Continue)):
        return set() if in_loop else _ALL
    if isinstance(node, ast.Assign):
        if not all(isinstance(target, ast.Name) for target in node.targets):
            return _ALL
        return _expr(node.value, shadowed)
    if isinstance(node, ast.AnnAssign):
        if not isinstance(node.target, ast.Name) or node.value is None:
            return _ALL
        return _expr(node.value, shadowed)
    if isinstance(node, ast.AugAssign):
        if not isinstance(node.target, ast.Name):
            return _ALL
        return _expr(ast.BinOp(left=node.target, op=node.op, right=node.value), shadowed)
    if isinstance(node, ast.If):
        return _union(_expr(node.test, shadowed), _block(node.body, shadowed, in_loop),
                      _block(node.orelse, shadowed, in_loop))
    if isinstance(node, ast.While):
        if node.orelse:
            return _ALL
        return _union(_expr(node.test, shadowed), _block(node.body, shadowed, True))
    return _ALL


def _stores(node):
    return {each.id for each in ast.walk(node) if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store)}


def _loads(node):
    return {each.id for each in ast.walk(node) if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load)}


def _caught(handlers):
    names = set()
    for handler in handlers:
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        for each in types:
            if not isinstance(each, ast.Name) or each.id not in _KNOWN:
                return None
            names.add(each.id)
    if 'ValueError' in names:
        names.add('UnicodeDecodeError')
    if 'OSError' in names:
        names.add('FileNotFoundError')
    return names


def _leaves(handler):
    """The handler ends in return/raise, and nothing in it can send control back round the loop."""
    if not handler.body or not isinstance(handler.body[-1], (ast.Return, ast.Raise)):
        return False
    return not any(isinstance(each, (ast.Break, ast.Continue)) for statement in handler.body
                   for each in ast.walk(statement))


def _hoistable(loop, bound, shadowed):
    if loop.orelse:
        return None
    header = set()
    if isinstance(loop, ast.For):
        call = loop.iter
        if not (isinstance(loop.target, ast.Name) and isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name) and call.func.id == 'range' and 'range' not in shadowed
                and 1 <= len(call.args) <= 3 and not call.keywords):
            return None
        header = _union(*[_expr(argument, shadowed) for argument in call.args])
    elif isinstance(loop, ast.While):
        header = _expr(loop.test, shadowed)
    else:
        return None
    tries = [index for index, statement in enumerate(loop.body) if isinstance(statement, ast.Try)]
    if len(tries) != 1:
        return None
    index = tries[0]
    node = loop.body[index]
    if node.finalbody or node.orelse or not node.handlers or not node.body:
        return None
    caught = _caught(node.handlers)
    if caught is None or not all(_leaves(handler) for handler in node.handlers):
        return None
    pre, post = loop.body[:index], loop.body[index + 1:]
    raised = _union(header, _block(pre, shadowed), _block(post, shadowed))
    if raised is _ALL or raised & caught:
        return None
    # names a handler may read although the loop assigns them: assigned before the loop, the loop's own
    # variable (the handler can only run from inside an iteration), or assigned by a plain statement
    # of the body ahead of the `try` (every iteration runs those first)
    known = set(bound)
    if isinstance(loop, ast.For):
        known.add(loop.target.id)
    for statement in pre:
        if isinstance(statement, ast.Assign):
            known.update(target.id for target in statement.targets)
        elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
            known.add(statement.target.id)
    assigned = _stores(loop)
    for handler in node.handlers:
        for statement in handler.body:
            for name in _loads(statement):
                if name in assigned and name not in known and name != handler.name:
                    return None
    return index


def _hoist(loop, bound, shadowed):
    index = _hoistable(loop, bound, shadowed)
    if index is None:
        return loop
    node = loop.body[index]
    inner = ast.copy_location(type(loop)(**{field: getattr(loop, field) for field in loop._fields}), loop)
    inner.body = loop.body[:index] + node.body + loop.body[index + 1:]
    outer = ast.Try(body=[inner], handlers=node.handlers, orelse=[], finalbody=[])
    return ast.copy_location(outer, loop)


def _suite(body, bound, shadowed):
    """Rewrite a statement list (inside out); `bound` holds the names directly assigned before it."""
    bound = set(bound)
    out = []
    changed = False
    for statement in body:
        for field in ('body', 'orelse', 'finalbody'):
            suite = getattr(statement, field, None)
            if isinstance(suite, list) and suite and not isinstance(
                    statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                fresh, did = _suite(suite, bound, shadowed)
                if did:
                    setattr(statement, field, fresh)
                    changed = True
        for handler in getattr(statement, 'handlers', ()):
            fresh, did = _suite(handler.body, bound, shadowed)
            if did:
                handler.body = fresh
                changed = True
        if isinstance(statement, (ast.While, ast.For)):
            replaced = _hoist(statement, bound, shadowed)
            if replaced is not statement:
                statement = replaced
                changed = True
                # the new try is the last statement of the suite it stands in: an enclosing loop
                # whose body is `pre; try; post` sees it as a try like any other
        if isinstance(statement, ast.Assign):
            bound.update(target.id for target in statement.targets if isinstance(target, ast.Name))
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None \
                and isinstance(statement.target, ast.Name):
            bound.add(statement.target.id)
        out.append(statement)
    return out, changed


def rewrite(tree):
    """Hoist in place; returns whether anything changed."""
    if not any(isinstance(each, ast.Try) for each in ast.walk(tree)):
        return False
    shadowed = {each.name for each in ast.walk(tree) if isinstance(each, ast.FunctionDef)}
    changed = False
    for function in [each for each in ast.walk(tree) if isinstance(each, ast.FunctionDef)]:
        if any(isinstance(each, (ast.Yield, ast.YieldFrom, ast.Await)) for each in ast.walk(function)):
            continue        # a suspended frame sits inside its `try`s: leave generators alone
        params = {argument.arg for argument in function.args.args + function.args.kwonlyargs}
        if function.args.vararg:
            params.add(function.args.vararg.arg)
        if function.args.kwarg:
            params.add(function.args.kwarg.arg)
        body, did = _suite(function.body, params, shadowed)
        if did:
            function.body = body
            changed = True
    if changed:
        ast.fix_missing_locations(tree)
    return changed
