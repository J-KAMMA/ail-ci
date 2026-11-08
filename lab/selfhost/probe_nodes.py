"""shport0 class probe: the shape of the planned `ailast` node classes."""


class AST:
    _fields = ()
    _attributes = ("lineno", "col_offset")

    def __init__(self, lineno: int):
        self.lineno = lineno
        self.col_offset = 0


class Name(AST):
    _fields = ("id", "ctx")

    def __init__(self, lineno: int, id: str):
        super().__init__(lineno)
        self.id = id
        self.ctx = None


class Constant(AST):
    _fields = ("value", "kind")

    def __init__(self, lineno: int, value, kind):
        super().__init__(lineno)
        self.value = value
        self.kind = kind


class BinOp(AST):
    _fields = ("left", "op", "right")

    def __init__(self, lineno: int, left, op: str, right):
        super().__init__(lineno)
        self.left = left
        self.op = op
        self.right = right


class Expr(AST):
    _fields = ("value",)

    def __init__(self, lineno: int, value):
        super().__init__(lineno)
        self.value = value


class Module(AST):
    _fields = ("body",)

    def __init__(self, body):
        super().__init__(0)
        self.body = body


def main():
    c = [Constant(1, 7, None), Constant(1, 2.5, None), Constant(2, "s'q", "u"), Constant(3, b"\x00b", None)]
    tree = Module([Expr(1, BinOp(1, c[0], "Add", c[1])), Expr(2, c[2]), Expr(3, BinOp(3, Name(3, "x"), "Mult", c[3]))])
    queue = [tree]
    i = 0
    while i < len(queue):
        node = queue[i]
        i += 1
        print(type(node).__name__, node.lineno, node._fields, isinstance(node, AST), isinstance(node, Expr))
        if isinstance(node, Module):
            for s in node.body:
                queue.append(s)
        elif isinstance(node, Expr):
            queue.append(node.value)
        elif isinstance(node, BinOp):
            queue.append(node.left)
            queue.append(node.right)
        elif isinstance(node, Constant):
            print(" ", repr(node.value), node.kind is None)
        elif isinstance(node, Name):
            print(" ", node.id, node.ctx is None, AST._attributes)


main()
