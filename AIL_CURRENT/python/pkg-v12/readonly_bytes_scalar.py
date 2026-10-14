"""Closed one-input integer scans whose BYTES argument cannot escape."""
import ast


def summaries(fns, sigs, clones, classes, exception_names, *, blocked=()):
    result = set()
    numeric_ops = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
                   ast.LShift, ast.RShift, ast.BitAnd, ast.BitOr, ast.BitXor)
    comparisons = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    for fn in fns:
        if not isinstance(fn, ast.FunctionDef) or fn.decorator_list:
            continue
        params, returned = sigs.get(fn.name, ((), None))
        args = fn.args
        if (returned != 'int' or len(params) != 1 or params[0][1] != 'bytes'
                or clones.get(fn.name) or len(fn.body) > 12
                or args.defaults or args.kw_defaults or args.vararg or args.kwarg
                or args.kwonlyargs or len(args.posonlyargs) + len(args.args) != 1):
            continue
        parameter = params[0][0]
        if len(fn.body) == 1 and isinstance(fn.body[0], ast.Return):
            value = fn.body[0].value
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == 'len' and len(value.args) == 1 and not value.keywords
                    and 'len' not in set(sigs) | set(classes) | set(blocked) | {parameter}):
                decoded = value.args[0]
                if (isinstance(decoded, ast.Call) and not decoded.args and not decoded.keywords
                        and isinstance(decoded.func, ast.Attribute) and decoded.func.attr == 'decode'
                        and isinstance(decoded.func.value, ast.Name) and decoded.func.value.id == parameter):
                    result.add(fn.name)
                    continue
        nodes = list(ast.walk(fn))
        loops = [node for node in nodes if isinstance(node, ast.For)]
        if (len(nodes) > 256 or len(loops) != 1 or loops[0].orelse
                or not isinstance(loops[0].iter, ast.Name)
                or loops[0].iter.id != parameter
                or not isinstance(loops[0].target, ast.Name)):
            continue
        locals_ = {node.id for node in nodes
                   if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        if parameter in locals_:
            continue
        exceptions = set(exception_names) - set(sigs) - set(classes) - locals_ - {parameter}

        def expression(node):
            if isinstance(node, ast.Name):
                return isinstance(node.ctx, ast.Load) and node.id in locals_
            if isinstance(node, ast.Constant):
                return type(node.value) is int and -(1 << 63) <= node.value < (1 << 63)
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
                    value = node.operand.value
                    return type(value) is int and -(1 << 63) <= -value < (1 << 63)
                return isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert, ast.Not)) and expression(node.operand)
            if isinstance(node, ast.BinOp):
                return isinstance(node.op, numeric_ops) and expression(node.left) and expression(node.right)
            if isinstance(node, ast.BoolOp):
                return isinstance(node.op, (ast.And, ast.Or)) and all(map(expression, node.values))
            if isinstance(node, ast.Compare):
                return (all(isinstance(op, comparisons) for op in node.ops)
                        and expression(node.left) and all(map(expression, node.comparators)))
            return False

        def target(node):
            return isinstance(node, ast.Name) and node.id in locals_ and node.id != parameter

        def statement(node):
            if isinstance(node, ast.Assign):
                return len(node.targets) == 1 and target(node.targets[0]) and expression(node.value)
            if isinstance(node, ast.AnnAssign):
                return (target(node.target) and isinstance(node.annotation, ast.Name)
                        and node.annotation.id == 'int' and node.value is not None
                        and expression(node.value))
            if isinstance(node, ast.AugAssign):
                return target(node.target) and isinstance(node.op, numeric_ops) and expression(node.value)
            if isinstance(node, ast.If):
                return expression(node.test) and all(map(statement, node.body + node.orelse))
            if isinstance(node, ast.Return):
                return node.value is not None and expression(node.value)
            if isinstance(node, ast.Raise):
                exception = node.exc
                if isinstance(exception, ast.Call) and not exception.args and not exception.keywords:
                    exception = exception.func
                return (node.cause is None and isinstance(exception, ast.Name)
                        and exception.id in exceptions)
            if node is loops[0]:
                return target(node.target) and all(map(statement, node.body))
            return False

        if all(map(statement, fn.body)):
            result.add(fn.name)
    return result
