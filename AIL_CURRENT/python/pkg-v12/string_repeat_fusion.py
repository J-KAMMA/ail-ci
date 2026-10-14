"""Pure AST proof for unused-index loops of independent literal string appends."""
import ast


def _scalar_count(node):
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Constant):
        return type(node.value) is int
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)) and _scalar_count(node.operand)
    if isinstance(node, ast.BinOp):
        return _scalar_count(node.left) and _scalar_count(node.right)
    return False


def _bindings_before(function, target):
    """Only prior direct bindings on the enclosing suite path count as initialized."""
    def scan(body, bound):
        current = set(bound)
        for statement in body:
            if statement is target:
                return current
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for field in ('body', 'orelse', 'finalbody'):
                    suite = getattr(statement, field, ())
                    found = scan(suite, current) if isinstance(suite, list) else None
                    if found is not None:
                        return found
                for handler in getattr(statement, 'handlers', ()):
                    found = scan(handler.body, current)
                    if found is not None:
                        return found
            if isinstance(statement, ast.Assign):
                current.update(name.id for name in statement.targets if isinstance(name, ast.Name))
            elif (isinstance(statement, ast.AnnAssign) and statement.value is not None
                  and isinstance(statement.target, ast.Name)):
                current.add(statement.target.id)
        return None
    return scan(function.body, {argument.arg for argument in function.args.args})


def candidate(node, function):
    if (not isinstance(node, ast.For) or not isinstance(node.target, ast.Name) or node.orelse
            or not isinstance(node.iter, ast.Call) or not isinstance(node.iter.func, ast.Name)
            or node.iter.func.id != 'range' or node.iter.keywords or len(node.iter.args) != 1
            or not node.body or not _scalar_count(node.iter.args[0])):
        return None
    updates = []
    for statement in node.body:
        if (not isinstance(statement, ast.AugAssign) or not isinstance(statement.target, ast.Name)
                or not isinstance(statement.op, ast.Add)
                or not isinstance(statement.value, ast.Constant)
                or type(statement.value.value) is not str or not statement.value.value):
            return None
        updates.append((statement.target.id, statement.value))
    names = {name for name, _ in updates}
    if len(names) != len(updates) or node.target.id in names:
        return None
    if any(isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load)
           and value.id == node.target.id for value in ast.walk(function)):
        return None
    bound = _bindings_before(function, node)
    count_names = {value.id for value in ast.walk(node.iter.args[0]) if isinstance(value, ast.Name)}
    if bound is None or not names <= bound or not count_names <= bound or count_names & names:
        return None
    return {'count': node.iter.args[0], 'index': node.target.id, 'updates': updates}
