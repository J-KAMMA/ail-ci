# DEVLOG

## 2026-10-21 — fuzz11 (generators and closures, branch job-fuzz11-10220826)

Ran 97 small programs in /tmp (45 general generator/closure shapes, 11 generator edge probes,
35 closure/default/global shapes, 6 final boundary probes) on both builds with
`bash ~/tools/cmp.sh`. Silent differences found, fixed in this branch:

* generator return values: StopIteration now carries `value`/`args`, `next(g)` keeps the
  generator's StopIteration (and `next(g, default)` still returns the default);
* `g.close()` throws GeneratorExit at the yield so `finally` runs, and `except Exception`
  does not swallow the close;
* a nested function's own `global` declaration no longer becomes a local of the enclosing
  function when that function has a local of the same name.

Remaining observed (not fixed; see DIFFERENCES C?-job-fuzz11-10220826-1..5): unclosed
generators at exit and dropped generators do not run finally; closing an outer generator
whose `yield from` was rewritten to a loop does not close the subgenerator; `iter(g)` is not
`g`; a generator expression is eager (re-iterating it after exhaustion repeats its items); a
bare `except:` does not catch the GeneratorExit thrown by `close()`.
