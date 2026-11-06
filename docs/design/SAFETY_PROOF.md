# SAFETY_PROOF: Rust's safety without writing lifetimes

Status: design + census, 2026-11-06.  Measurements are in `lab/proof/census.json` and
`lab/proof/RESULTS.md`; the script that produces them is `lab/proof/census.py`.  Nothing in this
document changes compiler behaviour: every number below comes from analyses that already run.

## 1. The claim, in one paragraph

Write plain Python.  For code the compiler can type, it infers who owns each reference value,
proves that every index is in bounds and that a parallel body cannot observe another iteration,
and emits no run-time bookkeeping for any of it.  Where it cannot complete a proof it does not
guess: it keeps the run-time check (retain/release pair, bounds helper, or the interpreter lock),
which is CPython's own behaviour, and it prints one line naming the file, the line, the property
and the reason.  So every accepted program is memory-safe and race-free on the paths the proof
covered, every uncovered path is still exactly CPython, and no program silently changes meaning.
The job is to move as much of real code as possible from "checked at run time" to "proved", and to
make the boundary visible.

## 2. What "proved" means, precisely

A function is *fully proved* when all three properties hold with no run-time check left in it.
Each rule below is the rule the source already implements; the census measured them, not a new
design.

### 2.1 Ownership and memory safety (`ir/borrow.py`, `ir/ownership.py`, `ir/effects.py`)

A reference value (list, dict, set, bytearray, exception, class instance, file, socket) has
exactly one owner at every program point.  The rules:

* **O1 borrowed parameter.** A parameter takes no entry retain and no exit release iff, on every
  path of the callee, it is only read: not stored into a field/list/dict/global/closure, not
  returned, yielded or raised, not rebound, not bound by `except`, and not passed to a position
  the callee does not itself borrow.  Computed as a fixpoint over the call graph; methods are
  merged by intersection because the emit point keys by bare name (`ir/borrow.py:226`).
* **O2 one release per owner.** Every owner local and every owning parameter is released exactly
  once on every exit — the normal returns, and the cleanup frame the emitter links so a longjmp
  through the function releases it too (`pyfunc._to_c_once`, `owned`/`object_refs`).
* **O3 share, move, borrow, or refuse.** `ys = xs` is resolved to a move, a move-then-borrow, a
  rename, or `Rule X` (two overlapping owners) which **refuses the function** rather than guessing
  (`ir/ownership.py:1`).  A surviving `list.share` reaching the verifier is an error.
* **O4 no view outlives its container.** Every length-changing op writes `Spine(...)` and
  `Rebind(...)` and every element access reads `Elem(...)` (`ir/effects.py`), so a hoisted span or
  a `list.ref` is only legal while no such op is reachable.  `licm.py` re-asks after every pass.
* **O5 no use after release.** `ir/verify.py` checks SSA def-before-use, place types, region
  shape and that a declared effect summary covers the body.  Today it covers S0 (scalars and
  places); owned values arrive with S3, and there is **no verifier that recomputes O1-O4** — the
  guarantee is "by construction in the emitter".  That gap is job P9 below and it is the honest
  limit of the word "proved" at this commit.

### 2.2 Bounds (`ir/passes/ranges.py`, `ir/passes/symbounds.py`)

An index site `c[i]` is **proved** iff the range analysis derives `0 <= i <= len(c)-1` at that
point in a form that survives every path to it:

* the interval domain gives `lo(i) >= 0`, and
* either `hi(i)` is at most a length value that no length-changing op and no unknown call can
  have invalidated between the two (`list_lengths_safe()`), or a guard of a versioned loop
  dominates the access (the `symbounds.py` forms: `up >= 0`, `up + w - 1 < len(c)`, one check per
  loop entry for the whole body).

Otherwise the site keeps its checked helper (`ail_list_get`, `ail_pslist_get`,
`ail_bytearray_get`), which raises `IndexError` exactly where CPython does.  The analysis says why
it gave up — `AIL_BCE_EXPLAIN` already records `index may be negative`, `list length may change
(length-changing op or unknown call)`, `no length value of this container`, `sum rule needs the
offset at most -1` — and that vocabulary is the `<reason>` of the diagnostic in section 4.

`AIL_BCE_AUDIT=1` is the existing counter-check: every **removed** check is re-inserted as a loud
stop (`ail_bce_audit_fail("<fn>", <site>)`, exit 86).  It is a per-build self-test of the bound
proof, not a default: keeping it on would cost an extra compare per access.

### 2.3 Race freedom (`parallel.py`, `typedpar.py`)

A region runs without a lock iff all five hold:

* **R1 bounded borrow (D5).** The fork and the join are in one block, so every value given to a
  worker is borrowed for a known interval: `ThreadPoolExecutor.map`, `Pool.map`, a group of
  `submit`s whose results are read inside the block, and `Thread` started *and* joined in one
  block.  Any other threading shape is returned unchanged and runs under the general path's lock.
* **R2 write set (D1).** A body writes only names it assigns itself and container elements whose
  shape is provably distinct per iteration: `xs[i]`, `xs[i*K + j]`, `out[k]`; every access to the
  same container in the body must use that one shape (`_Body.check_owned`).
* **R3 no shared mutation (D1, D3).** No write to a shared scalar or global, no
  `append`/`pop`/`insert`/`sort`, no resize.
* **R4 callee purity (D2).** A called function is top-level, takes and returns only int/float,
  does no I/O, no `@extern`, and does not recurse (`parallel.check_callee`).
* **R5 no reference values (D4).** No str, bytes or object value and no attribute read in a body:
  the arena, the reference counts and the cleanup chain are not thread-safe.

Four counts of what the rules already accept are in `lab/proof/RESULTS.md`.

## 3. When a proof fails: degrade, never guess

| property | failure | what is kept | cost | still CPython's meaning? |
|---|---|---|---|---|
| ownership | a parameter is not read-only | the retain/release pair (or the owned-local release) | 2 RC ops per call | yes |
| bounds | the index range is not proved | the checked helper | one compare + branch | yes, it raises where CPython does |
| races | the body or the shape breaks a rule | the general path's lock | no parallelism | yes |
| races | the region outlives its inputs | the lock (D5) | no parallelism | yes |

There is no fourth option: a failed proof never becomes undefined behaviour, a wrap, a copy, or a
different order.  The one exception is `AIL_BCE_AUDIT=1`, which turns a proved site into a loud
stop — a build-time audit, off by default, documented as such.

## 4. The diagnostic

Format, one line per unproved site, on stderr at compile time:

```
file:line: could not prove <property>: <reason>; runtime check kept
```

Emitters keep the format literal; `<property>` is `ownership`, `bounds` or `race-freedom`;
`<reason>` is a fixed phrase from a closed vocabulary (table below), so a tool can count them.

```
lab/compare/src/rail_transfer/typed.py:13: could not prove ownership: parameter 'h0' is stored
  into field 'G.h0'; retain/release kept
lab/compare/src/tally_lang/typed.py:120: could not prove bounds: list length may change
  (length-changing op or unknown call); runtime check kept
lab/race/racy/global_add.py:8: could not prove race-freedom: the body writes the shared name
  'total' (rule D1); lock kept
```

Three delivery modes, on the switch `AIL_PROOF`:

* `AIL_PROOF=off` (default): the program-level `note:` line the compiler already prints when a
  program falls back, unchanged.
* `AIL_PROOF=summary`: one line per program —
  `proof: 412/538 typed functions fully proved, 126 partly, 0 none; 4112 checks kept`.
* `AIL_PROOF=report` (plus `--strict` in CI): every line above, in file order.

The data already exists: `ir/driver.py` records per function `{path, reason, passes}` in
`AIL_IR_STATS`; `ranges.dump_explain` records a per-site reason in `AIL_BCE_EXPLAIN`;
`typedpar.rewrite_text` returns `(line, note)`; `pyc.fallback_note` prints the program-level line;
`ir/borrow.py` returns the demoted parameters; `native_diagnostics.py` carries structured
diagnostics to the editor.  Two things are missing, and they are jobs P1 and P2: the **reason
vocabulary is not closed** (each site reports whatever string its analysis happened to make), and
**an IR index site has no source line** (`I.SRC` is filled only with `--debug`), so today the
diagnostic can name the function but not the line.

## 5. Which existing modules each part builds on

| part | already there | to add |
|---|---|---|
| ownership proof | `ir/borrow.py` (rc2), `pyfunc._to_c_once` (retain/release), `ir/ownership.py` (M/M'/B/X), `ir/effects.py` (Elem/Spine/Rebind) | `ir/proof.py` joining the demotion to a reason and a line |
| ownership verification | `ir/verify.py` (S0 structural) | S3 rules O2/O3 checked, not trusted |
| bounds proof | `ir/passes/ranges.py`, `symbounds.py`, `licm.py` (versioning), `ir/emit_c.py` (`bce_audit`), `cruntime.py` `BCEAUDIT`, `boundbuiltin.py`/`rangecheck.py` (legacy path) | source positions on accesses; per-site provenance for the legacy path |
| race proof | `parallel.py`, `typedpar.py`, `threadlib.py`, `cruntime.py` PAR part | D3 chunked append (owner decision 2026-11-05), per-region reason → line |
| diagnostics | `pyc.fallback_note`, `AIL_IR_STATS`, `AIL_BCE_EXPLAIN`, `native_diagnostics.py` | the closed vocabulary and the three modes above |
| measurement | this census | re-run it in CI after every job that touches these modules |

## 6. Staged plan (each job ≤ 2 h), ordered by census blockers removed

Counts are from `lab/proof/census.json` (306 programs, 4958 functions, 1552 on the typed path,
2875 blocker instances).  "Moves" is what the job converts from checked to proved, or from
unmeasured to measured; where it is a projection, it says so.

| # | job | blocker it removes | count today | moves |
|---|---|---|---:|---|
| P1 | **typed reach, top reason first** | "function on the general (boxed) path: no proof applies" | 1703 functions (34%) | up to 1703 functions into the proof's domain; rank by `pyc.last_fallback_reason` (186 functions: a `Decimal` format spec; 164: a dunder other than `__init__`; 156: a `bool` parameter given a non-bool; 120: a `list[str]` given a non-str; 108: a generator expression saved; 108: `d.get(k)` needing `Optional`; 76: a `str` parameter a caller also passes an int to; 67: `Counter`/`defaultdict`; 58: `threading` — table in RESULTS) |
| P2 | **the report itself** | none: visibility | 2875 | names all 2875 with property+reason; the one user-facing deliverable that needs no new analysis |
| P3 | **index sites outside the IR** | `no-index-api` + every legacy-emitter function | 4744 sites / 31 functions | makes 4744 sites measurable; no proof yet (`boundbuiltin.py` reports its own provenance) |
| P4 | **return-transfer borrow** | "parameter returned (or yielded)" 145 + "aliased into a second local" 20 | 165 parameter pairs | up to +330 RC ops elided (16% of the 2050 measured pairs) |
| P5 | **bounds in the compare corpus** | index kept: "no length value" / "list length may change" | 188 of 308 IR sites kept | up to 188 sites; each is one removed check |
| P6 | **source positions on accesses** | none: makes P2/P5 diagnosable per line | 1221 IR sites | the 1221 sites P2 cannot yet locate |
| P7 | **race D3: per-chunk append buffers** | refused regions, rule D3 | 25 accesses in 2 regions | 2 regions move from refused to safe |
| P8 | **race D1: exact shared-int reduction** | refused regions, rule D1 (owner decision D1(c)) | 2 accesses | 2 regions, and `racy/global_add.py` matches CPython without the lock |
| P9 | **ownership verifier** | none: soundness | 0 | turns "safe by construction" into a checked proof; must come before anyone relies on the word "proved" |

Nine jobs, 18 hours.  P1 is first only because it moves the most; P2 is the one to ship first if
the goal is that a user can *see* the boundary.  P3 and P5 are the two bounds jobs the census
ranks highest; P9 has no number attached and is the soundness precondition for the word "proved".

## 7. What Rust still proves that this cannot

1. **Universally, not per function.** A Rust crate is safe for every input and every build; here a
   function is proved only if it is on the typed path, and 34% of real functions are not (census).
   A proof that disappears under an unrelated construct in the same program is not a guarantee.
2. **No aliasing, so no `&mut` exclusivity.** Python has one object with many names; this system
   proves the *absence of a premature free*, not that a writer is alone. `xs.append(x)` while
   another name iterates `xs` is refused or copied, never proved safe; Rust rejects it in the type
   system.  Two threads writing different elements of one list are safe here, but a list cannot be
   handed to two workers at all (R2), so the safe subset is narrower than Rust's.
3. **No `Send`/`Sync`.** Races are avoided by refusing the shapes that could race, not by proving
   that a type is safe to share.  A shape the rules do not recognise falls back to the lock, and
   a closure or a global that escapes a region is refused, not analysed.
4. **The fallback is a run-time stop, not a compile error.** Rust's guarantee is total; this one is
   best effort.  Where the proof fails and no check exists, the program stops loudly — a
   behaviour difference from CPython that has to be declared (`DIFFERENCES.md`), not a proof.
5. **Resources and FFI.** `@extern` calls, the CPython hybrid, files and sockets carry no ownership
   proof: the handle is an int64 index into a pool (section 2.1), so "closed twice" and "used after
   close" are run-time errors, not compile errors.
6. **Dynamic dispatch.** A method reached through an attribute, `getattr`, duck-typed parameters
   and same-named functions are merged or demoted (`ir/borrow.py` merges by intersection), so the
   proof loses precision exactly where Python is dynamic.  Rust's trait resolution is total.
7. **Leak freedom.** Arenas, pools and the region allocator are freed once per program scope, not
   per value; nobody proves that a cycle in a class graph is unreachable.
8. **The general path proves nothing.** 1703 of 4958 functions run on the boxed path, where values
   are boxed, reference-counted or GC-managed at run time.  That code is safe, but by construction
   of the runtime, not by proof.

## 8. Where we stand today (measured, `lab/proof/RESULTS.md`)

| corpus | functions | typed path | boxed | RC pairs elided | IR index sites | checks removed | sites outside the IR |
|---|---:|---:|---:|---:|---:|---:|---:|
| compare (20 programs) | 363 | 220 | 143 | 82.1% | 308 | 39.0% | 1353 |
| pyproof (55) | 769 | 538 | 231 | 91.1% | 3 | 66.7% | 1585 |
| gdev (200) | 2123 | 794 | 1329 | 70.1% | 910 | 4.8% | 1806 |
| **all** | **3255** | **1552** | **1703** | **80.9%** | **1221** | **13.6%** | **4744** |

Read as one sentence: the ownership rule is already doing most of its work (81% of the RC pairs a
call would need are gone), the bounds proof is not (14% of index sites in the functions it reaches,
and four fifths of all index sites are outside its reach), and the race rules accept 79 of 123
shared accesses.  The single largest number is not a proof gap at all: one third of real functions
never reach the typed path, so the honest ceiling of "how much of real Python can this prove" is
31% today, not 81%.
