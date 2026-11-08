"""Stage 1 reference: convert a CPython 3.12 ``ast`` tree into ``ailast`` nodes.

    python3 selfhost/ref/from_cpython.py LIST

CPython only: it imports ``ast`` to read the tree, which AIL does not build.  ``convert`` copies each
node's fields in CPython's order and its four position attributes (lineno, col_offset, end_lineno,
end_col_offset) when the node has them.  The result dumps with ``ailast.dump`` exactly as the CPython
tree dumps with ``ast.dump``.
"""
import ast
import sys

import ailast


def convert(node):
    if isinstance(node, ast.AST):
        cls = getattr(ailast, node.__class__.__name__)
        values = []
        for field in node._fields:
            values.append(convert(getattr(node, field)))
        for attr in cls._attributes:
            values.append(getattr(node, attr, None))
        return cls(*values)
    if isinstance(node, list):
        return [convert(item) for item in node]
    return node


def dump_path(path, include_attributes=False):
    with open(path, "rb") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    return ailast.dump(convert(tree), include_attributes=include_attributes)


def main():
    lines = [line for line in sys.stdin.read().split("\n") if line != ""]
    for path in lines:
        print("== " + path)
        print(dump_path(path))
        print(dump_path(path, True))


if __name__ == "__main__":
    main()
