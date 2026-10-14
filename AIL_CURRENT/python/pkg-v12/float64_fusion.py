"""Conservative AST proofs for a private binary64 decode/map/encode fusion."""
import ast


def _body(fn):
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _params(fn):
    args = fn.args
    if (fn.decorator_list or args.posonlyargs or args.vararg or args.kwarg
            or args.kwonlyargs or args.defaults or args.kw_defaults or len(args.args) != 2):
        return None
    names = tuple(arg.arg for arg in args.args)
    return names if len(set(names)) == 2 else None


def _assignment(node):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None


def _call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and len(node.args) == 2 and not node.keywords and not any(isinstance(arg, ast.Starred) for arg in node.args))


def _name(node, name):
    return isinstance(node, ast.Name) and node.id == name


def _bindings(fn):
    nodes = tuple(ast.walk(fn))
    names = {node.id for node in nodes if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
    names.update(node.arg for node in nodes if isinstance(node, ast.arg))
    names.update(node.name for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler)) and node is not fn and node.name)
    names.update(alias.asname or alias.name.split('.')[0] for node in nodes if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names)
    return names


def _multiply(node, value, scalar):
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
        return None
    if _name(node.left, value) and _name(node.right, scalar):
        return False
    if _name(node.left, scalar) and _name(node.right, value):
        return True
    return None


def _append(node, result):
    if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and _name(node.value.func.value, result)
            and node.value.func.attr == 'append' and len(node.value.args) == 1 and not node.value.keywords):
        return node.value.args[0]
    return None


def summaries(fns, sigs, blocked=()):
    """Return decoder/encoder name sets and map names with multiplication order."""
    blocked = set(blocked)
    result = {'decoders': set(), 'encoders': set(), 'maps': {},
              'builtin_blocked': blocked | set(sigs)}
    for fn in fns:
        if not isinstance(fn, ast.FunctionDef) or fn.name in blocked or fn.name not in sigs:
            continue
        params = _params(fn)
        if params is None:
            continue
        kinds, ret = sigs[fn.name]
        if tuple(name for name, _ in kinds) != params:
            continue
        kinds = tuple(kind for _, kind in kinds)
        body = _body(fn)
        if len(body) == 1 and isinstance(body[0], ast.Return) and _call(body[0].value):
            call = body[0].value
            for method, expected, returned in (('decode', ('bytes', 'int'), 'flist'), ('encode', ('flist', 'int'), 'bytes')):
                builtin = 'float64_' + method
                if (call.func.id == builtin and builtin not in result['builtin_blocked']
                        and builtin not in _bindings(fn) and kinds == expected and ret == returned
                        and all(_name(arg, name) for arg, name in zip(call.args, params))):
                    result[method + 'rs'].add(fn.name)
            continue
        if kinds != ('flist', 'float') or ret != 'flist' or len(body) != 3:
            continue
        initial = _assignment(body[0])
        loop, returned = body[1:]
        if (initial is None or not isinstance(initial[1], ast.List) or initial[1].elts
                or not isinstance(loop, ast.For) or loop.orelse or not isinstance(loop.target, ast.Name)
                or not _name(loop.iter, params[0]) or not isinstance(returned, ast.Return)
                or not _name(returned.value, initial[0])):
            continue
        local, value = initial[0], loop.target.id
        distinct = [*params, local, value]
        expression = None
        if len(loop.body) == 1:
            expression = _append(loop.body[0], local)
        elif len(loop.body) == 2:
            item = _assignment(loop.body[0])
            if item and _name(_append(loop.body[1], local), item[0]):
                if isinstance(loop.body[0], ast.AnnAssign) and not _name(loop.body[0].annotation, 'float'):
                    continue
                distinct.append(item[0])
                expression = item[1]
        reverse = _multiply(expression, value, params[1])
        if reverse is not None and len(set(distinct)) == len(distinct):
            result['maps'][fn.name] = {'reverse': reverse}
    return result


def _number(node):
    return (isinstance(node, ast.Name)
            or isinstance(node, ast.Constant) and type(node.value) in (int, float)
            or isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float))


def _consume_origin(body, index, name, all_nodes, excluded, builtin_blocked, disabled):
    if disabled or index <= 0:
        return None
    previous = _assignment(body[index - 1])
    if previous is None or previous[0] != name:
        return None
    call = previous[1]
    if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
            or call.func.id in excluded or call.func.id in builtin_blocked or call.keywords
            or any(isinstance(arg, ast.Starred) for arg in call.args)
            or call.func.id not in ('read_bytes', 'read_stdin_bytes') or len(call.args) != 1):
        return None
    uses = [node for node in all_nodes if isinstance(node, ast.Name) and node.id == name]
    if (sum(isinstance(node.ctx, ast.Store) for node in uses) != 1
            or sum(isinstance(node.ctx, ast.Load) for node in uses) != 1
            or any(isinstance(node.ctx, ast.Del) for node in uses)
            or any(isinstance(node, ast.arg) and node.arg == name for node in all_nodes)
            or any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler))
                   and node.name == name for node in all_nodes)
            or any((alias.asname or alias.name.split('.')[0]) == name
                   for node in all_nodes if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names)):
        return None
    return call


def candidate(body, index, fn, summaries, blocked=()):
    """Prove a three-assignment chain; the caller must check settled argument types."""
    nodes = tuple(body[index:index + 3])
    if len(nodes) != 3:
        return None
    assignments = tuple(_assignment(node) for node in nodes)
    if any(item is None or not _call(item[1]) for item in assignments):
        return None
    targets = tuple(item[0] for item in assignments)
    decode, mapper, encode = (item[1] for item in assignments)
    builtin_blocked = summaries.get('builtin_blocked', set()) | set(blocked)
    if not (decode.func.id in summaries['decoders'] or decode.func.id == 'float64_decode' and decode.func.id not in builtin_blocked):
        return None
    if not (encode.func.id in summaries['encoders'] or encode.func.id == 'float64_encode' and encode.func.id not in builtin_blocked):
        return None
    map_info = summaries['maps'].get(mapper.func.id)
    if (map_info is None or not _name(mapper.args[0], targets[0]) or not _name(encode.args[0], targets[1])
            or not isinstance(decode.args[0], ast.Name) or not all(_number(arg) for arg in (decode.args[1], mapper.args[1], encode.args[1]))):
        return None
    external = {arg.id for arg in (decode.args[0], decode.args[1], mapper.args[1], encode.args[1]) if isinstance(arg, ast.Name)}
    if len(set(targets)) != 3 or external & set(targets):
        return None
    excluded = set(blocked) | _bindings(fn)
    if any(call.func.id in excluded for call in (decode, mapper, encode)):
        return None
    all_nodes = tuple(ast.walk(fn))
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in all_nodes):
        return None
    for name in targets[:2]:
        uses = [node for node in all_nodes if isinstance(node, ast.Name) and node.id == name]
        if (sum(isinstance(node.ctx, ast.Store) for node in uses) != 1
                or sum(isinstance(node.ctx, ast.Load) for node in uses) != 1
                or any(isinstance(node.ctx, ast.Del) for node in uses)
                or any(isinstance(node, ast.arg) and node.arg == name for node in all_nodes)
                or any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler))
                       and node.name == name for node in all_nodes)
                or any((alias.asname or alias.name.split('.')[0]) == name
                       for node in all_nodes if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names)):
            return None
    return {'nodes': nodes, 'targets': targets, 'data': decode.args[0], 'read_order': decode.args[1],
            'factor': mapper.args[1], 'write_order': encode.args[1], 'reverse': map_info['reverse'],
            'consume_origin': _consume_origin(body, index, decode.args[0].id, all_nodes, excluded,
                                              builtin_blocked, summaries.get('_disable_consumption', False))}
