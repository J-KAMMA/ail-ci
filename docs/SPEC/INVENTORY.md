# Inventory of AIL semantic decisions

This is the first-pass inventory behind the specification: every decision already made somewhere
in the repository that a program can observe. The chapters expand these rules. Sources are the
files where the decision was taken or is enforced.

The inventory is not the whole of `docs/spec/DIFFERENCES.md`: that file has the long tail of small
CPython differences (`A*` and `C*`). This page collects the decisions that define the language, so a
reader can see the shape of AIL before meeting the edge cases. Where the two disagree, the
`DIFFERENCES.md` row wins and this page is corrected.

Rule ids are stable. A chapter uses the same id as this table.

## Values and types (VT)

| id | rule | source |
|---|---|---|
| VT1 | The surface syntax is Python; annotations are optional hints, never a run-time contract. | [`docs/WHY.md`](../WHY.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) introduction |
| VT2 | `int` is signed 64-bit by default. An overflow stops loudly; a constant outside int64 is refused by name; `--exact-int` / `AIL_EXACT_INT=1` gives exact arbitrary-precision ints (about 20x slower). | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 1-2, [`docs/MIGRATING.md`](../MIGRATING.md) 1-2 |
| VT3 | A per-value `BigInt` annotation gives exact ints without making the whole program exact. | [`docs/design/BIGINT_TYPE.md`](../design/BIGINT_TYPE.md) |
| VT4 | `None` is an exact tagged value; there is no `None` in the place of a `str` or `bytes`. | [`docs/ROADMAP.md`](../ROADMAP.md) P1, [`docs/design/CALLSITE_SPEC.md`](../design/CALLSITE_SPEC.md) |
| VT5 | `float` is IEEE 754 binary64; a single operation is C's, and algorithms that CPython implements specially follow CPython's algorithm. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A15 |
| VT6 | `bool` is a distinct truth type; `is` on numbers follows the identity rules, not object identity. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C114, C115, C115-silent2-2 |
| VT7 | `str` is Unicode text. The typed path carries UTF-8; the general runtime is 16-bit and therefore stops by name above U+FFFF in the places listed. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A13, A22, A59, C191, C192 |
| VT8 | `str` and `bytes` are separate types. A `str` is never compared with `bytes`; the mixing is refused rather than coerced. | [`lab/compare_cand/RESULTS-log_scan.md`](../../lab/compare_cand/RESULTS-log_scan.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A71, A72 |
| VT9 | `bytes` and `bytearray` exist on the general path as prelude classes; the built codecs are UTF-8, ASCII and Latin-1 (and their aliases), with `strict`, `ignore` and `replace`. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A59, A72, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 16 |
| VT10 | `list`, `tuple`, `dict`, `set` and `frozenset` are the containers. `set` and `frozenset` iterate in insertion order; `set` operations keep the left operand's order, then new elements of the right. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2, C4 |
| VT11 | A dict view is a snapshot here; keeping one in a name, field, item or container is refused. Call `d.items()` where it is used, or keep `list(...)`. | [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 3, [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C105-C107, C116 |
| VT12 | A class may have one base. Only `@staticmethod` and `@functools.lru_cache` / `@cache` decorators are modelled. | [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 6-7, [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A51 |
| VT13 | Text I/O is UTF-8 by default (also ASCII and Latin-1 when named); `sys.argv` is `str`; the wall clock is a program input and can be pinned with `AIL_CLOCK`. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A16, A28, A29 |

## Arithmetic and errors (AR)

| id | rule | source |
|---|---|---|
| AR1 | Integer arithmetic never wraps. A result outside int64 stops with `OverflowError` and the operation's name; a statically known out-of-range value is refused at build time. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 1-2 |
| AR2 | `int / int` is rounded once from the exact quotient, not from two rounded doubles. | [`DIFFERENCES.md`](../../DIFFERENCES.md) C?-job-fz227-11050703-1, `test_ail_fz227.py` |
| AR3 | `int ** n` with a non-constant negative exponent stops loudly; a constant negative exponent gives CPython's float. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A5 |
| AR4 | Float `//`, `%` and `divmod` use CPython's `float_divmod`, including zero-remainder signs, infinities and NaNs. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C173 |
| AR5 | `sum()` of floats uses CPython 3.12's compensated (Neumaier) algorithm bit for bit, including the start value and int/float mixes. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C1, A15 |
| AR6 | `ail_array` sums and dot/matmul products use one fixed 16-lane, 1024-block order; the builtin `sum(a)` keeps CPython's meaning. | [`AIL_CURRENT/docs/design/TYPED_ARRAY.md`](../../AIL_CURRENT/docs/design/TYPED_ARRAY.md) TA3, TA4, section 3.5 |
| AR7 | NaN has no object identity in an unboxed float: searches that need it stop by name or refuse; a tuple comparison reaching NaN raises `ValueError`; sorting NaN keys is refused. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A7, C119, C140, C141, C?-job-refuzz95-10300605-1 |
| AR8 | Complex numbers are not a type. A complex literal or constant complex result is refused; a run-time complex result is a known bug, not a rule. | [`docs/MIGRATING.md`](../MIGRATING.md) 11-12, [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C5 |
| AR9 | Set arithmetic is deterministic in the order of VT10; it does not follow CPython's hash order. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2 |
| AR10 | `re` has no `None` for an unmatched group: `m.group(i)` of a group that did not take part raises `ValueError`. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A8, [`docs/MIGRATING.md`](../MIGRATING.md) 13 |
| AR11 | Trap messages that a program can read match CPython 3.12 for the operations listed in A12; uncaught stderr text is outside the promise. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A12, A4 |
| AR12 | A negative shift count raises `ValueError`; `abs(-0.0)` is `0.0`; `round()` of NaN/inf and out-of-int64 values follows CPython's classes. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C183, C225, C251, C180 |

## Evaluation order and determinism (EO)

| id | rule | source |
|---|---|---|
| EO1 | Expressions and statements run in source order. A lowering may not move a visible side effect before an earlier operand that can raise or run code. | [`DIFFERENCES.md`](../../DIFFERENCES.md) C?-job-fz216-11021859-1, `test_ail_fz216.py` |
| EO2 | Changing a dict or set while iterating it raises `RuntimeError("dictionary changed size during iteration")` / `"Set changed size during iteration"` at the next step. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C4 |
| EO3 | A generator expression whose body can raise is lazy; one saved as a value whose lazy body can raise is refused rather than made eager. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C241, C242, C?-job-stdlib2-11011233-1, C?-job-stdlib2-11020039-1 |
| EO4 | The typed path evaluates every `__str__` of a `print()` before writing anything; CPython writes each argument after its own `__str__`. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A52(b) |
| EO5 | The clock, environment and file system are inputs. `AIL_CLOCK` pins the clock; a program whose inputs are fixed has a fixed result. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A28 |
| EO6 | Sorting is stable; NaN keys are refused; the number and order of `__lt__` calls may differ from Timsort without changing the order. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A52(a), C?-job-refuzz95-10300605-1 |
| EO7 | A typed map returns its results in input order; an exception is raised at the input index where CPython would raise it, not in completion order. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A66, A74, A75 |
| EO8 | Addresses, object ids, thread ids and hash order are not part of the promise; a comparison that would expose them is refused or documented. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2, A39, A72, C?-job-std_pprint-11011616-2 |
| EO9 | The parallel-region combine follows iteration order, so the value and the first exception are the sequential ones (see CO3-CO8). | [`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md), [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) |

## Memory and ownership (MO)

| id | rule | source |
|---|---|---|
| MO1 | Assigning a container to another name shares it, as CPython does; the IR default is the answer, and the legacy emitter's copy is not the rule. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A65(a)(b) |
| MO2 | An augmented assignment to an item mutates the object in place (`xs[0] += [3]`, `d["k"] += [4]`), including through aliases. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C85 |
| MO3 | A typed container field may be a snapshot; a shape that would expose the difference is refused. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C85, [`docs/design/ARENA1.md`](../design/ARENA1.md) |
| MO4 | A read-only parameter is borrowed. A list parameter the callee writes element by element is passed as the caller's buffer, not copied, so the caller sees the writes. | [`AIL_CURRENT/DEVLOG.md`](../../AIL_CURRENT/DEVLOG.md) entry 2026-11-07 "fclist1", [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) O1-O3 |
| MO5 | A dict view kept past a change of the dict is refused, because a stored view would be a snapshot (VT11). | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C106, C107, C116 |
| MO6 | A file is closed by `close()`, `with` or at exit, never when its last reference goes away; unclosed data is flushed at exit, also before an uncaught exception. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A17 |
| MO7 | FFI `bytes` is borrowed and never copied; `bytearray` may be written by C but its length cannot change; a compiled program copies it in and out around the call. | [`docs/FFI.md`](../FFI.md) "What is not supported yet" |
| MO8 | `is` on numbers is not object identity. A shape the compiler cannot decide is refused (C114/C115) or stops loudly; `None`, `True`, `False` and small ints keep their defined identities. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C114, C115, C115-silent2-1, C115-silent2-2 |
| MO9 | The CPython hybrid copies a `list[int]` / `list[float]` argument, refuses a mutated list, and falls back to the original Python function on any boundary failure. | [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md) section 2-3 |
| MO10 | Ownership, bounds and race freedom are proved where possible; where a proof fails the runtime check is kept (retain/release, bounds helper, lock), never undefined behaviour. | [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) sections 1-3 |

## Concurrency (CO)

| id | rule | source |
|---|---|---|
| CO1 | `threading`, `queue` and `concurrent.futures` are built on the general path under one interpreter lock with CPython's GIL semantics; such a program prints the general-path note and is about 20x slower. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A38, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 14 |
| CO2 | The typed path runs only recognised fork-join shapes without a lock: `ThreadPoolExecutor.map`, `Pool.map`, a group of `submit`s read in the block, and a `Thread` list started and joined in one block. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A66, A67, A74, A75, [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) |
| CO3 | **D1:** a read-modify-write of one shared int in a parallel body is refused and the loop runs under the lock (or the user writes `out[k]` partials). The exact reduction is a later job. | [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D1, [`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md) |
| CO4 | **D2:** a shared float accumulator is allowed only behind an explicit opt-in, with one fixed chunking at every thread count; not built. | [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D2 |
| CO5 | **D3:** a parallel body that appends to a shared list is refused today; the accepted future lowering uses per-chunk buffers concatenated in iteration order. | [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D3 |
| CO6 | **D4:** a hybrid-mode native call that takes a container keeps the GIL; calls with only scalars release it. | [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D4, [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) "CPython hybrid" |
| CO7 | **D5:** a value is borrowed by a worker only for a known interval: fork and join are in one block. A region that outlives its inputs stays under the lock. | [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) R1 |
| CO8 | A parallel body writes only its own locals and provably disjoint elements, calls only pure top-level int/float functions, and holds no `str`, `bytes` or object reference. | [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) R2-R5, [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) sections 1-2 |
| CO9 | An FFI callback declared `threads=True` is refused; calling one from another thread or after the C call returned aborts the program. | [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) "FFI", [`docs/FFI.md`](../FFI.md) |

## Modules and FFI (MF)

| id | rule | source |
|---|---|---|
| MF1 | A program is built whole. `eval`, `exec`, `compile`, `importlib.import_module`, `__import__` and a non-literal `open()` mode are refused by name. | [`docs/MIGRATING.md`](../MIGRATING.md) 4-8, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 5, 9 |
| MF2 | A function-local import is hoisted to module scope only when none of the modules has an effect at import time; otherwise it is refused by name. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C148 |
| MF3 | The standard library is a declared subset. A name outside it is refused by name with the list or the first missing name; it is never silently missing. | [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 10-12, `lab/stdcensus/RESULTS.md` |
| MF4 | An `@extern` declaration is checked against the C header; `trust=True` drops the prototype comparison for a type the stub cannot spell. | [`docs/FFI.md`](../FFI.md) |
| MF5 | FFI integers are range-checked for the declared C width; a `uint64` result above int64 is a loud stop unless exact ints are on. | [`docs/FFI.md`](../FFI.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1, A69 |
| MF6 | FFI pointers are `bytearray`/integer handles; `Handle` frees once, newest first at exit; no function pointers to AIL code. | [`docs/FFI.md`](../FFI.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A63 |
| MF7 | `ail build --cpython` is an explicit hybrid mode: selected top-level functions run natively, every boundary failure runs the original Python function. The standalone build is unchanged. | [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md) |
| MF8 | A module must be named at each use; it cannot be stored, passed or compared. The same holds for `sys.stdin` / `sys.stdout` streams that are used as plain values. | [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 8, 13 |
| MF9 | A callback must name a module-level `def`; a lambda, closure, method or variable is refused, and `retain=True` / `threads=True` are refused. | [`docs/FFI.md`](../FFI.md) |

## Errors and diagnostics (ED)

| id | rule | source |
|---|---|---|
| ED1 | A refusal exits 2 (syntax/size) or 3 (construct outside the subset), prints one message on stderr, and names the construct and location. | [`docs/LIMITATIONS.md`](../LIMITATIONS.md) conventions, [`docs/CLI.md`](../CLI.md) |
| ED2 | A runtime trap exits 1, prints `Kind: message` (and the line under `--debug`) on stderr, and keeps the stdout already written. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A4, A12, [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 2 |
| ED3 | An uncaught exception prints no traceback; `--debug` / `AIL_DEBUG=1` adds a `raised near file:line` line. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A4, C?-job-relrterr4-11042111-1 |
| ED4 | A proof that fails prints one compile-time line `file:line: could not prove <property>: <reason>; runtime check kept`, with a closed reason vocabulary. | [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) section 4 |
| ED5 | Falling back to the general path prints one `note: ... built on the general path` line; `--strict` / `AIL_NO_GENERAL=1` refuses instead. | [`docs/CLI.md`](../CLI.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A62 |
| ED6 | `ail run --diff` compares the native run with CPython and reports one machine-readable line (or a JSON object); exit 3 is a difference, 4 a documented loud stop, 124 a timeout. | [`docs/CLI.md`](../CLI.md) |
| ED7 | A trap message a program reads matches CPython for the A12 list; the rest of the runtime's own wording is outside the promise. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A12 |
| ED8 | An agent-readable error format is a roadmap item. No `docs/design/AGENT_ERRORS.md` exists in this tree; the current contract is ED1-ED6. | [`docs/ROADMAP.md`](../ROADMAP.md) P2 |

## Compatibility (CM)

| id | rule | source |
|---|---|---|
| CM1 | The default build is not "CPython unless broken". It is AIL semantics, with a general fallback that promises CPython's answer where no declared difference applies. | [`docs/WHY.md`](../WHY.md), [`docs/MIGRATING.md`](../MIGRATING.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) |
| CM2 | A CPython-identical mode is a compatibility target, not the definition. Today the closest tools are `ail run --diff` (an oracle) and `ail build --cpython` (a hybrid); `--compat cpython` does not exist yet and is an open question. | [`docs/CLI.md`](../CLI.md), [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md), [OPEN.md](OPEN.md) O11 |
| CM3 | Every difference from CPython is either a named refusal or a declared difference; a silent difference is a bug. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) introduction |
| CM4 | Build modes: default (typed with general fallback), `--strict` / `AIL_NO_GENERAL=1` (typed only), `--exact-int` / `AIL_EXACT_INT=1` (exact ints), `AIL_UNIFIED_FORCE=1` (forced general path, measurement), `--cpython` (hybrid). | [`docs/CLI.md`](../CLI.md), [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A62, A65 |
| CM5 | The promise covers stdout and exit status; stderr text, addresses, object ids, hash order and timing are outside it unless a rule says otherwise. | [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2, A4, A39, A72 |
| CM6 | The compatibility claim is tested by `ail run --diff`, compare-lab, the corpus, the migrating samples and the daily fuzz; a result is quoted only from a committed result file. | [`docs/CLI.md`](../CLI.md), [`docs/WHY.md`](../WHY.md), `lab/*/RESULTS.md` |
| CM7 | A compatibility result is dated. A number in a document names the commit and the task set it came from; a stale number is corrected, not carried. | [`docs/ROADMAP.md`](../ROADMAP.md), [`docs/COMPARISON.md`](../COMPARISON.md) |
