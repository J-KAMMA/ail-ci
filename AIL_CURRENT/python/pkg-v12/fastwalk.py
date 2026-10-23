"""`ast.walk` without the generator layers (same breadth-first order, same nodes).

Every pass in the front end walks function bodies, and several walk the same body once per
function per round of a fixed point, so `ast.walk` was one of the most-called functions of a C
generation run: its per-node cost is two nested generators (`iter_child_nodes` -> `iter_fields` ->
`getattr` + `isinstance` for every field) wrapped in `deque.extend(map(...))`. This yields the
identical sequence with one flat loop -- measured 1.8x-2.8x faster on this compiler's own trees.

`install()` replaces `ast.walk` for the rest of the process, so every module that writes
`ast.walk(x)` -- the whole front end -- gets it without touching 300 call sites. It is the same
node sequence, so nothing a walk returns can change: `test_ail_frontend_speed` asserts that it
yields exactly the standard library's nodes on the programs it compiles, and the emitted C is
compared byte for byte before and after.

`AIL_FASTWALK=0` keeps the standard library's own walk (measurement only: which of the two a
difference came from).
"""
import ast
import os

_ON = os.environ.get('AIL_FASTWALK') != '0'


def walk(node):
    """`ast.walk(node)`: every node of the subtree, breadth first, children before their own."""
    todo = [node]
    append = todo.append
    index = 0
    while index < len(todo):
        current = todo[index]
        index += 1
        for name in current._fields:
            try:
                field = getattr(current, name)
            except AttributeError:
                continue
            if isinstance(field, ast.AST):
                append(field)
            elif isinstance(field, list):
                for item in field:
                    if isinstance(item, ast.AST):
                        append(item)
        yield current


def install():
    """Use `walk` for every `ast.walk(...)` in this process (idempotent, and a no-op under AIL_FASTWALK=0)."""
    if _ON and ast.walk is not walk:
        ast.walk = walk
