# DEVLOG

Exported CI mirror note: this tree carries no DIFFERENCES.md, so the entries below name the difference
ids (`C?-<branch>-N` placeholders) and the test module that holds the programs.

## 2026-10-21 — job fuzz9: collections and data structures (Counter, defaultdict, OrderedDict, deque, namedtuple, heapq, bisect)

72 small generated programs in the collections area were compared with CPython 3.12 on both builds (the
default build and `AIL_UNIFIED_FORCE=1`). Three causes were fixed, each with probes in `/tmp/probes/` and
tests in `AIL_CURRENT/test_ail_fuzz9.py`:

* `C?-job-fuzz9-10220555-1` — `print(f, f["y"])` of a defaultdict / OrderedDict / deque built the repr text
  of the collection while that argument was evaluated, i.e. before the later arguments ran, so a key a
  later argument inserted was missing (`defaultdict(<class 'int'>, {'x': 1}) 0` instead of
  `..., 'y': 0}) 0`). `collib.py` now binds every argument that is not itself converted to a local first,
  in order, so the conversion runs after all of them. A converted collection keeps its own name: a second
  name for a container would be a copy, not an alias.
* `C?-job-fuzz9-10220555-2` — a deque's `q[i] = x`, `del q[i]` and `q[a:b]` on the general path worked on
  the two-element wrapper (`[data, maxlen]`) instead of the data list: after `q += [3]`, `q[0] = 9`
  overwrote the wrapper's data pointer (`len(q)` then printed 122, or the program segfaulted) and `q[1:]`
  printed `[None]` where CPython raises TypeError. `cruntime.py` now indexes the data list (IndexError
  "deque index out of range") and raises CPython's TypeError for a slice or a non-int index.
* `C?-job-fuzz9-10220555-3` — `del c[k]` with a missing key on a Counter raised KeyError on the general
  path and lost the rest of the output; Counter.__delitem__ ignores a missing key in CPython. The Counter
  flag (`ail_gcobj.flags`) is now honoured by `ail_op_delitem`, while `del d[k]` on a defaultdict still
  raises KeyError.

Found but not fixed (each its own cause for a later job): `b.c["k"] += 2` where the Counter is a class
field raises KeyError 'k' (the read is a plain dict lookup); `list(od)` of an OrderedDict with int keys
raises TypeError "argument of type 'int' is not iterable" on the general path; `move_to_end(k,
last=False)` and `print(d, d.popitem())` are refused by name and the general path cannot build them
either.
