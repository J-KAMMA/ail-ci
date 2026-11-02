# prog30 typed reach: eight real programs (2026-11-02)

Hot functions from CPython 3.12 `cProfile`, sorted by `tottime` (own time).  A single run of
these programs is below the clock's resolution, so the figures repeat `main` (200--20000 times,
stdout discarded; the same functions in the same proportions).  "Typed" is the default
`compile --syntax python` path: does the program's own module build on the typed path?  The
CPython hybrid (`docs/design/CPYTHON_HYBRID.md`) accelerates exactly those typed units.

| Program | Hot function(s) (own time) | Typed? | First reason / action |
| --- | --- | --- | --- |
| `gdev/g11_022.py` | `stabilize` 72.9% (plus list append/pop and set.add 27.1%) | **yes** | Already typed at the base; kept as a regression. |
| `gdev/g09_034.py` | `count_no_adjacent_zeros` 38.6%, `main` 26.8% (plus `print` 34.6%) | **yes** | Already typed at the base; kept as a regression. |
| `gdev/g23_004.py` | `minor` 51.8%, `determinant` 35.0%, `main` 8.2% | no | `minor`: `a comprehension target that is not a name` (line 10).  It also has two-generator nested comprehensions.  Follow-up: comprehension lowering needs tuple targets and more than one `for`-clause. |
| `gdev/g02_012.py` | `fib_pair` 43.9%, `main` 34.3%, `fib_iterative` 9.1%, `fib` 3.2% (plus `print` 9.5%) | **yes** | Already typed at the base; kept as a regression. |
| `gdev/g03_008.py` | `trapezoidal` 62.1% (plus `math.sin` 35.7%), `main` 1.4% | no | `trapezoidal`: `call to f(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one. write instead: define `f` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str)` (line 8).  Follow-up: a function-valued parameter needs higher-order specialization. |
| `corpus/.../t266.py` | `main` 40.5%, `dfs` 15.6% (plus list.append 14.0%, next 7.0%, str.join 5.0%) | **yes** | Fixed: a local `it = iter(data)` and `next(it)` kept the whole file on the general path.  They now become an index cursor over the same list/str/bytes. |
| `dev/t244.py` | `main` with its product genexpr 56.7% (plus `sum` 32.5%, str.join 6.9%) | **yes** | It was typed at the base but **wrong**: `lines += [<join comprehension>]` printed only the first half, because the hoisted comprehension's temp was freed before the `extend` that read it.  Fixed in `nested_lists.py`; all `in*.txt` cases now match CPython. |
| `corpus/.../t172.py` | `main` 41.3%, its line-13 genexpr 19.5%, `strip` 10.8%, `split` 7.6% | no | `import of 'collections' with a use that is not built: Counter, defaultdict (int, float, str, list, lambda: <constant>), OrderedDict and deque are built for str / int / tuple keys and int / float / str / tuple elements; the rest of the module is not (namedtuple and ChainMap are built by the library pass)` -- this program needs a defaultdict whose factory is `dict.fromkeys`, i.e. a dict of dicts.  The notes add `unpacking a value that is not a tuple of known shape` (line 13), `iterating over a tuple` (lines 18, 20, 21, 23, 24), and the general path itself cannot build it (`a generator expression nested inside another generator expression`).  Follow-up: dict-of-dict values plus generator unpacking and tuple iteration. |

## Compiler changes

* `python/pkg-v12/iterlower.py`: a local `it = iter(seq)` followed by one-argument `next(it)`
  becomes an index cursor (`temp = seq[i]; i += 1`) when `seq` is a known list/str/bytes (or a
  list/str/bytes literal), the iterator is bound exactly once directly in the function body with
  no rebinding or delete, every use of `it` is such a `next`, every `next` textually follows the
  binding, and no effectful receiver/argument is evaluated before it.  An `AugAssign` whose value
  holds a `next` is only lowered when its target is a plain name: CPython evaluates the target
  before the value, so a subscript / attribute target (`a[items.pop(0) % 2] += next(it)`) may run
  code that the hoisted cursor read would otherwise overtake.  A `try` anywhere, a `while`-test
  use, `next(it, default)` and a source deleted or rebound after `iter()` stay on the general
  path.  The rewrite also refuses when `iter` or `next` is bound in the function's own scope
  (a local, a parameter, or a nested def/class name, an import, `except ... as`, or a loop
  target), because that binding replaces the builtin the calls would otherwise reach; those
  programs stay general and match CPython.  A shadow inside a nested function's own scope does
  not affect the outer function, which still lowers.  This is what makes `t266.main` and
  `t266.dfs` typed.
* `python/pkg-v12/nested_lists.py`: a hoisted comprehension temp (`__ail_itemsN` / `__ail_rowsN`)
  is marked `_ail_synth`, so `_last_use_free_points` cannot decide the prelude loop is its last
  mention (both share the comprehension's source position) and free it before the statement that
  consumes it.  Fixes the wrong `t244` output and the same shape for a nested list.

## Follow-ups (not fixed here; exact first message)

* `g23_004`: `a comprehension target that is not a name` (and two-generator nested comprehensions).
* `g03_008`: `call to f(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one. ...`
* `t172`: `import of 'collections' with a use that is not built: ... defaultdict ...` (dict of dicts), plus the tuple/generator notes above.

## Verification

* `AIL_CURRENT/test_ail_prog30.py` (registered through `AIL_CURRENT/tests.d/test_ail_prog30.txt`)
  compiles `t266` and compares every `in*.txt` case with CPython; compiles the newly typed
  iterator shapes (list literal, named list, str, bytes, append after `iter()`, `next` in an `if`
  test, an exhausted cursor, `xs += [<comprehension>]` for str and nested lists); checks the
  shapes that stay general (`try`, `while` test, two-argument `next`, effectful argument, effectful
  augmented-assignment target, rebind, `del`, use before the binding); and keeps `g11_022`,
  `g09_034`, `g02_012`, `t244` typed and
  `g23_004`, `g03_008` general, each compared with CPython.  `t172` is checked as refused by name.
* Probes in `/tmp/probes`: `p30_iter_{basic,named,float,multi,if,empty,exhausted,arg,attr,dictval,
  del,rebind,before,nested,try,while,default,unsafe}.py`, `p30_aug_{comp,comp2,comp3,comp4,comp5,
  lines,target,target2,target_name,target_arg,target_attr,target_dict_value,target_next_in_target,
  target_pop_index}.py`, `p30_joincomp_{a,b,c,d}.py`, `p30_nested_aug.py`, `p30_nested_sum.py`.
  Every one matches CPython's stdout and exit status on both `cmp.sh` builds.  The
  effectful-target probes stay on the general path; `target_name` (`total += next(it)`) stays
  typed on the default build.  The exhausted-cursor probes
  match on stdout/exit; the typed runtime names the uncaught trap `list index out of range` where
  CPython says `StopIteration` (recorded as `C?-job-prog30-11021835-1`).
* Review fix probes `rv_next_{nested,local,param}_shadow.py`,
  `rv_iter_{nested,local,param}_shadow.py`, `rv_{iter,next}_module_shadow.py`,
  `rv_nested_only_shadow.py`, `rv_next_after_use.py`, `rv_iter_for_target.py`,
  `rv_next_except_target.py` and `rv_next_import_shadow.py` asked for a shadowed builtin; all
  match CPython's stdout and exit status on both `cmp.sh` builds.  The shadowed programs stay
  general; `rv_nested_only_shadow.py` (the shadow is inside the nested helper's own scope) still
  builds typed and matches.
* The generated C of the ten `lab/compare/src/*/main.ail` tasks is byte-identical to the base
  commit (10/10 compared with `--debug-dir`).
