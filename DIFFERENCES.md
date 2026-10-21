# DIFFERENCES

Rows added by branch job-fuzz11-10220826 (2026-10-21). All five are silent differences from
CPython 3.12 found by the fuzz11 probes and are still open.

| id | area | difference |
|---|---|---|
| C?-job-fuzz11-10220826-1 | generators | A generator that is still suspended when the program ends (or when it becomes unreachable) does not run its `finally` blocks; CPython finalizes it and prints them. Natural exhaustion and an explicit `g.close()` do run them. |
| C?-job-fuzz11-10220826-2 | generators | `g.close()` on an outer generator that uses `yield from` as a statement (rewritten to a `for ... yield` loop on the general path) runs the outer `finally` but not the subgenerator's: the inner `finally` is skipped. |
| C?-job-fuzz11-10220826-3 | generators | `iter(g)` of a generator returns an iterator wrapper, so `iter(g) is g` is false (CPython returns the generator itself). The wrapper also has no `.close()`, which is why the subgenerator in row 2 is not closed. |
| C?-job-fuzz11-10220826-4 | generator expressions | A generator expression used as a value is materialised eagerly. After `list(g)` exhausts it, a second `list(g)` produces the items again instead of an empty list. |
| C?-job-fuzz11-10220826-5 | generators | A bare `except:` inside a generator does not catch the GeneratorExit that `g.close()` throws (it is compiled as `except Exception`, and the internal GeneratorExit class is not an Exception subclass), so the handler's output is skipped and close returns quietly where CPython takes the handler and then raises RuntimeError for the ignored exit. |
