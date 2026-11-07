# Typed parallel: no lock, no data race

State as of 2026-11-05. This note describes the three mechanisms that decide whether a threaded
Python program runs on the lock-free typed path, on the general path under one interpreter lock,
or is refused. It cites the current source; line numbers are from `origin/integ` at the export of
this job.

## 1. The `parallel for` ownership proof (`parallel.py`)

The loop is spelled `for i in par_range(a, b)`; the source pass turns it into a range loop with a
`.par` marker (`AIL_CURRENT/python/pkg-v12/parallel.py:29`), and the typed parallel lowering uses
the private spelling `_ail_par_range(lo, hi, workers)` (`parallel.py:32`). `is_par` recognises
exactly those two call names (`parallel.py:41-43`); `prepare()` rewrites every such loop, and
refuses one inside a struct method or a class (`parallel.py:455-466`).

The body may write only names it assigns itself and elements `xs[i]`, `xs[i*K + j]` (with
`j` from an inner `for j in range(0, K)`) or `xs[i*K + c]`; every read and write of the same list
must use one provably distinct shape (`parallel.py:54-72`, `parallel.py:142-162`). `check_owned`
enforces that uniqueness (`parallel.py:264-271`). An expression statement (a call, `print`, `append`)
is refused (`parallel.py:131-139`) -- except the one buffered `out.append(v)` shape of D3 (below) --
as are `try`, `return`, a nested parallel loop and a runtime step (`parallel.py:82-140`,
`parallel.py:405-413`, `parallel.py:447`). A called function
must be a top-level int/float-only function with no `@extern` and no recursion
(`parallel.py:283-303`).

A refusal raises the compiler's `Unsupported`, and `prepare`/`parallel` attach the source line
(`parallel.py:46-51`). On the typed path that is an error; when the general path can still build
the program, `pyc` turns it into the one-line note `note: ... built on the general path ...`
(`AIL_CURRENT/python/pkg-v12/pyc.py:1172-1175`).

## 2. The fork-join lowering (`typedpar.py`)

`typedpar.rewrite_text` runs before `threadlib` in the Python surface pass
(`AIL_CURRENT/ail_syntax.py:4582-4586`). It lowers only these shapes
(`AIL_CURRENT/python/pkg-v12/typedpar.py:5-19`):

* `ThreadPoolExecutor(max_workers=k).map(f, xs[, ys])` and `multiprocessing.Pool(k).map(f, xs)`
  when `f` is a top-level function of int/float/tuple arguments that only computes
  (`typedpar.py:152-164`); the result is the generated `_ail_pmap` loop
  `for i in _ail_par_range(0, len(xs), k)`.
* `ex.submit(f, ...)` groups read through `.result()` (`typedpar.py:591-691`), including a group made
  inside a `with` block whose results are read after it: the region runs at the submit (inside the
  block) and the later `.result()` / `for f in futs` reads are rewritten in place
  (`typedpar.py:698-711`). A future read in a shape the lowering cannot rewrite is refused by name,
  so the program falls back to the lock instead of keeping an undefined name.
* `enumerate(ex.map(f, xs))` with an `(i, v)` for target (`typedpar.py:392-402`): the map is
  materialised as a list first, so `enumerate` sees the results in order.
* `ts = [threading.Thread(target=w, args=(k, out, ...)) for k in range(T)]`, then
  `for t in ts: t.start()`, then `for t in ts: t.join()` (or the append-and-start spelling), when
  all three happen in one block (`typedpar.py:813-988`). The body is inlined into
  `for k in _ail_par_range(0, T, T)`; it may read any list and write `out[k]` only
  (`typedpar.py:5-17`).

Every other use, and every program whose check fails, is returned as written with a note whose text
starts `not run in parallel (it runs under the general path's lock):`
(`typedpar.py:1106`). The note also gets a `write instead:` line when the pass has one.

## 3. The general path's lock (`threadlib.py`, `thread_prelude.py`, `threadrt.py`)

`threading`, `queue` and `concurrent.futures` are built on the general path only
(`AIL_CURRENT/python/pkg-v12/threadlib.py:1-18`, `threadlib.py:29`). The typed-path check refuses
any such import with the message that they are "built on the general path only (one interpreter
lock, CPython's GIL semantics)" (`threadlib.py:573-580`), and `pyc` calls that check before choosing
the typed path (`AIL_CURRENT/python/pkg-v12/pyc.py:675`). The runtime is one interpreter lock with
CPython's GIL behaviour (`AIL_CURRENT/python/pkg-v12/thread_prelude.py:6-7`,
`AIL_CURRENT/python/pkg-v12/threadrt.py:1-2`); it is memory-safe and not parallel.

## Reductions: `acc += e` in a parallel body (fbred3)

The exact shared-int reduction of `docs/design/PAR_REDUCE.md` is lowered by `parallel.py` and
`pyfunc._par_for`/`_par_outline` onto `cruntime.PARRED`'s `ail_par_reduce_run`. The accepted shape
is `acc += e` or `acc -= e` on an int local of the enclosing function that the body touches nowhere
else (no other store, no read); several accumulators are allowed. `parallel._Body` records the
accumulators and their sign in the loop's `.par` facts (`reductions`), and `_par_for` asks for the
`PARRED` part. `_par_outline` lifts the body twice instead of once: a chunk function that keeps,
per accumulator, the chunk partial sum and its largest/smallest prefix in `__int128` (so a
chunk-local overflow is not a trap, and the global total may still fit), and a re-run function that
is the same loop with the ordinary checked add, writing `acc[]` after every update so a caught stop
leaves the last prefix that fitted. The call site keeps the accumulator values in `_arK[]`, calls
`ail_par_reduce_run`, and writes them back to the enclosing locals, so a read after the loop sees
the sequential value. Only the chunk where the sequential loop stops (the first failed chunk, or
the first whose `B + mx`/`B + mn` leaves int64) is re-run alone; every other chunk adds its partial
sums. The proof is `PAR_REDUCE.md`'s; the runtime's differential test is `test_ail_par_reduce_rt`.

Scope in v1: only the Python surface (`AIL_SURFACE=python`) is lowered, so the AIL surface keeps
the old refusal. Refused by name, with a `write instead:` line: a float accumulator, the
accumulator read in the body, a mixed `+=`/`-=` on one name, a body that also writes a
list/bytearray element (`PAR_REDUCE.md`) -- the re-run would repeat those writes, so the shape is
out of scope rather than approximated -- and a `parallel for` inside `try`.
The `sum(ex.map(f, xs))` / `sum(pool.map(f, xs))` shapes already lower through `typedpar`'s
`_ail_pmap` and are already exact (the map finishes, in order, before the left-to-right sum; so a
map exception after the overflow index wins, as in the sequential map); fbred3 changes nothing
there. `sum(parallel_map)` inside a parallel body stays refused by the container-returning-call
rule. See `lab/race/reduce/RESULTS.md`.

## Appends: `out.append(v)` in a parallel body (fbpmap3, owner decision D3)

A map-like body (the `par_range` loop, including the loop `typedpar` inlines a scoped
`Thread` list into; not a free-running thread list) may append to **one** list `out` defined
before the loop, when its only use in the body is `out.append(v)` -- any number of times per
iteration, conditional or not, with `v` an int, float or str value.
`parallel._Body._append` accepts that expression statement, refuses any other use of `out`, a
second appended list, a list of objects and a body that also reduces, and records the name in the
loop's `.par` facts (`appends`). The receiver names are collected from the whole body before the
walk, so a read, an element write or `len(out)` that textually precedes the first append is refused
too (the walk order does not matter). `pyfunc._par_for` then asks for the `PARBUF` part.
Scope in v1: the Python surface only (`AIL_SURFACE=python`); the AIL surface's `parallel for`
keeps the old refusal.

`_par_outline` rewrites the emitted `ail_list_push(&v_out, ...)` (or `ail_flist_push` /
`ail_slist_push`) into `ail_par_buf_push_i/f/s(_pbK, ...)` and declares
`ail_par_buf *_pbK = ail_par_buf_for(_lo)` in the worker. `cruntime.PARBUF` keeps one buffer per
block start (the worker's `_lo`), grows it with `realloc` (thread-safe, never shared), and after the
region appends the buffers to `out` in block-start order with `ail_list_push` /
`ail_flist_push` / `ail_slist_push`. Blocks are contiguous, so that is the sequential order. A str
buffer holds `ail_str` views and the join copies the structs, so there is no extra retain.

`ail_par_buf_run` is the `ail_par_run` gating (the timed probe prefix, the guided block size) with
the final re-raise moved **after** the join: a block that traps keeps its partial buffer, and the
join stops after the failing block's start, so `out` holds exactly what the sequential loop leaves
before its exception. The run then raises the recorded exception on the calling thread. Raw-element
buffers mean the whole output is held twice at the join, which is the owner's 2x RSS allowance.
Probes and numbers: `lab/race/append/RESULTS.md`; test: `AIL_CURRENT/test_ail_par_append.py`.

## Which path a program gets

1. If the program uses `threading`/`queue`/`concurrent.futures`, `threadlib.refuse_typed` stops the
   typed path (`pyc.py:675`), and the general path runs it under the lock, unless a shape was already
   lowered by `typedpar` (`ail_syntax.py:4582-4586`).
2. A map/thread shape that passes `typedpar` and `parallel` runs on the typed path with no lock;
   its C carries `ail_par_run` (`AIL_CURRENT/python/pkg-v12/cruntime.py:30882`).
3. Anything else is the ordinary typed path, or is refused by name.
`AIL_NO_GENERAL=1` asks for the typed path alone; `--strict`/`AIL_STRICT=1` refuses instead of
falling back. `AIL_UNIFIED_FORCE=1` forces the general path for every program (measurement only,
`pyc.py:1182-1185`).

## `AIL_THREADS`

The parallel runtime reads `AIL_THREADS` once per process, caches it, defaults to the online CPU
count, and clamps it to `1..256` (`AIL_CURRENT/python/pkg-v12/cruntime.py:30754-30770`). The typed
`_ail_par_range` passes its worker cap to `ail_par_run_n` (`cruntime.py:30959-30963`), so both the
environment variable and the call's own worker count bound the pool.

## Can `par_range` be written in a `.py` program CPython also runs?

No. CPython has no `par_range` builtin, so the loop raises `NameError` there; defining a helper of
that name is refused by the compiler because it shadows the built-in spelling used by the lowering
(`AIL_CURRENT/python/pkg-v12/shadowing.py:13`, `shadowing.py:46`, `shadowing.py:67`). Tested
directly: `def par_range(a, b): return range(a, b)` compiles to
`not in the subset: AIL function 'par_range' shadows the built-in name par_range`. The response is
to write the CPython shape (`ThreadPoolExecutor.map`, `Pool.map`, or the started-and-joined
`Thread` list), which is exactly what `typedpar` recognises.

## CPython hybrid

The hybrid build (`ail build --cpython`) accelerates selected top-level functions in a CPython
extension. A native call whose arguments are only int, float, bool or str is surrounded by
`Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS`; a call that takes a list keeps the GIL while it
runs (owner decision D4, 2026-11-05), the provisional safe default while other CPython threads may
hold containers. `docs/design/CPYTHON_HYBRID.md:125-141` states the same. The hybrid accepts int,
float, bool, str, `list[int]` and `list[float]` (`ail_cpython_hybrid.py:35-36`, `555-575`); a
`bytearray` parameter, a mutated list, or a function that may raise stays in CPython, and an
accelerated function cannot index (so it cannot read a module-level container).

## FFI

A callback declared with `threads=True` is refused at construction
(`AIL_CURRENT/ail_ffi.py:247-252`), and a callback called from another thread (or after the C call
returned) aborts the program (`ail_ffi.py:87-88`, `ail_ffi.py:620`). A parallel body also cannot
call an `@extern` function (`parallel.py:283-291`).
