"""The same accelerated function called with values the native ABI cannot carry.

`triple` is accelerated.  A bool in its int position, a float, and an int above int64 all fail
the boundary conversion, so each of those calls re-enters the original Python function.  The
results (and their types) are therefore exactly CPython's.

The float call goes through the alias `g = triple`.  A direct `triple(2.5)` would make the
whole-module kind analysis demote `triple` before the hybrid ever sees a unit; reaching the same
wrapper through an alias keeps the function accelerated and still exercises the boundary.
"""
import sys


def triple(n: int) -> int:
    return n * 3 + 1


base = 7
if len(sys.argv) > 1:
    base = int(sys.argv[1])

g = triple
big = int("9223372036854775809")

for value, result in (
    (base, triple(base)),
    (True, triple(True)),
    (2.5, g(2.5)),
    (big, triple(big)),
):
    print("%r -> %r (%s)" % (value, result, type(result).__name__))
