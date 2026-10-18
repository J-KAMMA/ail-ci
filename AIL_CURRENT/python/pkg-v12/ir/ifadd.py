"""`if <test> { x += K }` (no else; x an int local; K a nonzero int literal) -> `x += select(<test>, K, 0)`.

The same test is evaluated once and the same (checked or proven) add runs - adding 0 never overflows -
but the update is a conditional move rather than a branch. On loaded data the test is the
unpredictable branch of a neighbour count (a grid-life program: eight of them per cell). The legacy path does the
same rewrite on the AST (`pyfunc._if_add_fusion`); this is the IR twin, kept here so `lower.py` only
carries the call.
"""
import ast


def fusable(test):
    """The tests worth turning into a conditional add: one comparison (or its `not`) that reads a
    container element - data-dependent, so the branch it would feed mispredicts. A test made of
    `and`/`or` stays a branch (the short-circuit is one anyway) and so does a comparison of locals
    (predictable in a counting loop: k_nucleotide's `if i >= m - 1 and key == target` ran 3% slower)."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        test = test.operand
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
        return False
    nodes = list(ast.walk(test))
    return (any(isinstance(n, ast.Subscript) for n in nodes)
            and not any(isinstance(n, (ast.BoolOp, ast.Call, ast.NamedExpr, ast.Lambda, ast.IfExp)) for n in nodes))


def match(node):
    """(target name, op, K, the AugAssign) when `node` is an `ast.If` of that shape, else None."""
    if not isinstance(node, ast.If) or node.orelse or len(node.body) != 1:
        return None
    s = node.body[0]
    if not (isinstance(s, ast.AugAssign) and isinstance(s.op, (ast.Add, ast.Sub))
            and isinstance(s.target, ast.Name)
            and isinstance(s.value, ast.Constant) and type(s.value.value) is int
            and 0 < abs(s.value.value) < (1 << 62)):
        return None
    if not fusable(node.test):
        return None
    return s.target.id, s.op, s.value.value, s
