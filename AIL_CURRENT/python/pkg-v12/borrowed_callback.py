"""Conservative certificates for immediate-consumption borrowed STR callbacks."""

import ast


def _operand(node, parameter, kind):
    if isinstance(node, ast.Name):
        return node.id == parameter and isinstance(node.ctx, ast.Load)
    if isinstance(node, ast.Constant):
        return (type(node.value) is str if kind == 'str'
                else type(node.value) in (int, float))
    return (kind != 'str' and isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) in (int, float))


def _condition(node, parameter, kind):
    if isinstance(node, ast.BoolOp):
        return (isinstance(node.op, (ast.And, ast.Or)) and len(node.values) >= 2
                and all(_condition(value, parameter, kind) for value in node.values))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _condition(node.operand, parameter, kind)
    if isinstance(node, ast.Compare):
        return (bool(node.ops) and len(node.ops) == len(node.comparators)
                and all(isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
                                        ast.Gt, ast.GtE)) for op in node.ops)
                and all(_operand(value, parameter, kind)
                        for value in [node.left, *node.comparators]))
    return False


def _block(statements, parameter, kind):
    """Return (safe, guaranteed return), checking even unreachable statements."""
    returns = False
    for statement in statements:
        if isinstance(statement, ast.Return):
            value = statement.value
            safe = ((isinstance(value, ast.Constant) and type(value.value) is str)
                    or (kind == 'str' and isinstance(value, ast.Name)
                        and value.id == parameter and isinstance(value.ctx, ast.Load)))
            if not safe:
                return False, False
            returns = True
        elif isinstance(statement, ast.If):
            if not _condition(statement.test, parameter, kind):
                return False, False
            body_safe, body_returns = _block(statement.body, parameter, kind)
            else_safe, else_returns = _block(statement.orelse, parameter, kind)
            if not body_safe or not else_safe:
                return False, False
            returns |= body_returns and else_returns
        else:
            return False, False
    return True, returns


def summaries(fns, sigs, owned_str_fns):
    """Certify only static literals or the sole STR argument on every path.

    The caller must consume the returned view before freeing its source owner.
    These summaries do not authorize changing the public owned-return ABI.
    """
    result = {}
    for fn in fns:
        if not isinstance(fn, ast.FunctionDef) or fn.name not in owned_str_fns:
            continue
        params, return_kind = sigs.get(fn.name, ((), None))
        args = fn.args
        positional = [*args.posonlyargs, *args.args]
        if (return_kind != 'str' or len(params) != 1 or len(positional) != 1
                or args.vararg or args.kwarg or args.kwonlyargs or args.defaults
                or args.kw_defaults or fn.decorator_list or getattr(fn, 'type_params', ())):
            continue
        parameter, kind = params[0]
        if kind not in ('str', 'int', 'float') or positional[0].arg != parameter:
            continue
        body = fn.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and type(body[0].value.value) is str):
            body = body[1:]
        safe, returns = _block(body, parameter, kind)
        if safe and returns:
            result[fn.name] = {'parameter': parameter, 'parameter_kind': kind,
                               'function': fn}
    return result
