# DEVLOG

## 2026-10-23 - method bounds with annotated returns (job-perf3b-10240813)

The earlier method-field analysis did not fire on the real accessors: the AIL front end writes
`-> int` as the bare name `__ail_checked_int__`, and `inline_candidate` walked the `FunctionDef`
including its return and argument annotations, so that load made every annotated zero-argument
method look impure and `remaining()` was never analysed in place. Annotations are not runtime body
expressions; `rangecheck.py` now collects the id of every annotation node and skips those nodes in
the candidate walk. Nothing else changes: a method with an assignment, loop, try or non-builtin
call is still rejected, and a field store, unknown call or alias still forgets its facts.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 40.8/47.2/9.8/9.5 | 0.866 [0.863, 0.871] faster | 4.145 [4.119, 4.170] slower |

Before (HEAD 4ffe276) the AIL/C ratio was `4.728 [4.701, 4.824] slower`; the ranges do not overlap
(13.4% less AIL time, above the 3% keep threshold). Result:
`bench/results/2026-10-23-12f2492.json`. The new test checks that generated
`Cursor__read_u8`/`read_u32_le` contain no `ail_bytes_get`, while the unguarded method keeps its
check.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`cursor_fields.py` and `bcursor_fields.py` (annotated `remaining`/`read_*` analysed in place,
u8/u16/u32 widths, empty, exact short and long boundaries, negative position, aliasing, values
through an argument, a list item, an attribute and a dict value), `method_side_effects.py`
(annotated methods with a store, a loop and a try are not inlined; out-of-range reads still raise),
`range_guards.py` (plain guarded reads on bytes/list plus unguarded bytes indexing). Tests:
`test_ail_range_checks.py`, `test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`,
`test_ail_files.py`, `test_ail_corpus_findings3.py` all pass.

## 2026-10-23 - range proofs through struct fields and safe method inlining (job-perf3b-10240127)

`binary_cursor_records` was 4.99x slower than C because every `read_*` method rechecked the same
cursor invariants: `remaining()` validated `position`, each byte read paid `ail_bytes_get`'s bounds
check, and the index arithmetic paid `ck_add`. The value-range analysis only reasoned about plain
locals, so it could not connect a guard on a method result to the receiver's fields.

`rangecheck.py` now tracks fields of a single unaliased object parameter (`#fld:o.f`, plus
`#len:#fld:o.f` for bytes/list fields), and records the identity of a subtraction between two exact
symbols. A guard on the difference (`available < 4`) therefore refines its operands
(`position <= len - 4`). Zero-argument methods whose bodies are only guards and a return, with no
assignment, loop, try or non-builtin call, are analysed in place against the caller's field facts,
so `remaining()`'s guard proves `position <= len` inside each `read_*`; `prove_le` now follows a
chain such as `start -> position -> len` that was previously stopped at an already-seen symbol.
Field facts are forgotten on a field store, an unknown method call, an unanalysed construct, or a
field passed to other code, and a function with any parameter besides the receiver is not tracked,
so an aliased argument cannot leave stale facts. `pyfunc.py` wires the class field/method lookups
into `rangecheck.Info` and marks bytes-field subscripts for the same resolver.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 41.4/51.3/10.5/10.0 | 0.803 [0.801, 0.806] faster | 3.975 [3.943, 4.031] slower |

The base ratio was `4.986 [4.904, 4.997] slower`; the ranges do not overlap (19.3% less AIL time).
Result: `bench/results/2026-10-23-3b21283-dirty.json`. The generated C for `read_u8`, `read_u16_*`
and `read_u32_*` has no `ail_bytes_get`/`ck_add`/`ck_sub` left, and every timed run matched the
Python oracle byte-for-byte.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`field_remaining_reads.py` (inlined `remaining`, u8/u16/u32, exact boundary, invalid position),
`field_mutation_soundness.py` (field store, bytes-field reassignment, unknown method call, aliased
object argument all keep the out-of-range read checked), `field_guard_bounds.py` (direct
`len(field) - 1` guard and negative index). Tests: `test_ail_range_checks.py`,
`test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`, `test_ail_files.py`,
`test_ail_corpus_findings3.py` all pass.

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
# Devlog

## 2026-10-22

* fuzz21 (unpacking): the general path's `UNPACK_SEQUENCE` errors now use CPython's wording and
  counts -- `too many values to unpack (expected N)`, `not enough values to unpack (expected N, got M)`,
  `(expected at least N, got M)` for a starred target, and `cannot unpack non-iterable X object`.
  Added `AIL_CURRENT/test_ail_fuzz21.py` and registered it in `ail_check.MODULES`.
## 2026-10-23 - fuzz45: float // and % use CPython's float_divmod

The general path's boxed operators and the unified pass emitted `floor(a / b)` for float `//` and a
bare `fmod` for float `%`.  `1.0 // 0.1` was 10.0 (CPython 9.0), `-0.0 % 2.0` was -0.0 (CPython
0.0), `-5.0 // inf` was -0.0 (CPython -1.0) and `inf // 2.0` was inf (CPython nan).  Both now use
one CPython float_divmod helper, so `//`, `%` and `divmod` agree, including zero-remainder signs,
infinities and NaNs.  Added `test_ail_fuzz45.py` (5 programs, two builds each).
## 2026-10-22

- job-fuzz39-10230820 (review fix): a name whose bindings mix a tuple and a number is no longer treated as a known
  tuple for the number check, so `x = (1,); x = 2.5; z = 2.5; x is z` is refused with C115 again instead of printing
  False. The `is(` spelling no longer bypasses the refusal in `numidentity.py` / `pyboxed2.py` (text gate is a word
  match, not the literal `' is '`). Added both cases to `test_ail_fuzz39.py`.
- job-fuzz39-10230820: `is` / `is not` with an equal tuple constant (including one passed to both parameters of a
  generic function) is refused by name instead of answering False where CPython answers True. Added
  `AIL_CURRENT/test_ail_fuzz39.py` and extended `numidentity.py`; `tuplib.py` leaves such a comparison for the refusal.
## 2026-10-23 - fuzz43: str.startswith/endswith tuple member type names

A non-str member of a tuple passed to `str.startswith`/`str.endswith` raised the right
`TypeError` but named the runtime tag rather than the member's class: a bytes member printed
`not instance` where CPython prints `not bytes`, and a user-class member was flattened to
`instance` too. The message now resolves the member object's class name (the prelude bytes class
or the user class) on both builds. Added `test_ail_fuzz43.py`, which also keeps valid tuples,
short-circuiting before a later bad member, empty receivers and windowed calls compared with
CPython. Other observed differences, not fixed here: `bytes.__contains__` with a str item and
bytes search with wrong-type bounds still print different TypeError text (different causes);
the non-ASCII `lower`/`upper` limit remains a documented pre-existing difference.
## 2026-10-23

- fuzz70: `assert cond, msg` now keeps the message object in `AssertionError.args` on the general
  path (`ail2x_raise_builtin`), so tuple/list/dict/None/custom messages match CPython's `str(e)`
  and `e.args`. A mixed-mode typed clone is no longer selected for a function that asserts, so a
  failed assert inside a helper is caught by the surrounding boxed `try`. Typed-only builds still
  refuse a tuple assert message by name. New coverage: `test_ail_fuzz70.py`.
## 2026-10-22 - fuzz8 review 2 fixes (job-fuzz8-10221632)

1. `_attribute_kind` / `_attribute_container` now add the attribute to the recursion guard `seen`
   and return `None` on a cycle instead of recursing forever.  `b.x = b.x + 1` (or `b.x = b.x`)
   together with `itertools.accumulate(..., initial=b.x)` or `groupby([b.x, ...])` no longer aborts
   every build with `RecursionError`; the typed path declines and the default build falls back,
   matching CPython (`[2, 3.5]`, `1 [1, 1]` / `2 [2]`).
2. Corrected `DIFFERENCES.md` row `C?-job-fuzz8-10221632-2`: mutable-element groupby keys do not
   run on a typed recompute.  `--strict` refuses the pattern (`'_ilN_gc' is read before it is
   assigned`) and the default build uses the general path.

`AIL_CURRENT/test_ail_fuzz8.py` covers self-referential and cross-name attribute cycles through
arguments, list items, dict values, nested attributes and groupby.  Probes:
`/tmp/probes/attr_cycle_acc.py`, `attr_cycle_self.py`, `attr_cycle_groupby.py`,
`attr_cycle_two_names.py`, `attr_cycle_nested.py`, `attr_cycle_float.py`,
`attr_cycle_dict_list.py`.

## 2026-10-22 - fuzz8 review fixes (job-fuzz8-10221632)

1. `itertools.groupby` no longer reuses a stale look-ahead key for a list of mutable elements.
   The typed path still declines that pattern (`--strict`: `'_ilN_gc' is read before it is
   assigned`) and the default build falls back to the general path, which matches CPython.
   Scalar/str element lists stay on the typed path and call the key once per element.  Probe
   `gb_cache_regress_len.py` prints `1 3` / `3 1`.
2. `itertools.accumulate(xs, initial=v)` on the typed path is refused by name when the types of
   `v` and the elements differ.  One-argument `round()` is now classified as `int` through local
   bindings, list items, attributes and dict values, so the float-list probe falls back to the
   general path and prints `[2, 3.5, 6.0]` instead of `[2.0, 3.5, 6.0]`.

`AIL_CURRENT/test_ail_fuzz8.py` has both cases; the typed groupby/accumulate modules, safetynet,
files and corpus_findings3 pass on the final commit.


## 2026-10-21 - fuzz8: iteration tools (job-fuzz8-10220554)

Ran 65 small differential programs over chain / islice / product / permutations / combinations /
combinations_with_replacement / accumulate / groupby / zip_longest / starmap / enumerate /
zip(strict=) / sorted / min / max / reversed / map / filter, each through `bash ~/tools/cmp.sh`
on the default build and `AIL_UNIFIED_FORCE=1`.  Fixed three causes (all now in
`AIL_CURRENT/test_ail_fuzz8.py`, with probes in `/tmp/probes`):

1. `itertools.accumulate(..., initial=None)` now treats None as "not given", as CPython 3.12 does
   (`cruntime.ail_it_accumulate`).  Constant, argument, list-item, attribute and dict-value routes
   are tested.
2. `sorted` / `list.sort` call their key on the input in the original order even for
   `reverse=True`, and call it once for a one-element list (`cruntime.ail_list_sort`).  Before, the
   elements were reversed before the key calls, which only showed with a key that has a side effect.
3. The typed path's `itertools.groupby` reuses the look-ahead key, so it calls the key exactly once
   per element instead of twice on each group boundary (`itlib.Groupby`).

Remaining differences found are recorded in `DIFFERENCES.md`; they were not fixed in this job.
## 2026-10-23

- job-fuzz82: typed path refuses `del` on an item of a module-level numeric list by name.
  Before, `del xs[-1]` was a silent no-op (the const table's `.n` write was dropped) and an
  earlier index memmoved over const data and crashed; the default build now falls back to the
  general path and matches CPython. Added `AIL_CURRENT/test_ail_fuzz82.py`.
# Development log

## 2026-10-23 — job-fuzz61-10231419

- String encoding: a run-time encoding name now accepts every CPython alias of `utf-8`, `ascii`
  and `latin-1` (`csascii`, `cp367`, `ibm367`, `csisolatin1`, `ibm819`, `utf8_ucs2`,
  `utf8_ucs4`, ...), on both builds. Literal spellings are accepted by `safetyrt.ENCODINGS`
  instead of refused by name. New test: `test_ail_fuzz61`.
# Development log

## 2026-10-23 — job-fuzz65-10231438 (heapq/bisect)

- Found: `heappush(h, "x")` on an annotated `list[int]` raises TypeError after CPython has already appended the string. When the same file also compares tuples (a `bisect` on `list[tuple[int, int]]`), `tuplegen.lrepr` generated an int-specialized `str(x)` for each element, so `print(h)` showed `x` instead of `'x'` (silent wrong stdout, exit 0, both builds). The same helper raised a spurious TypeError while printing a `list[str]` that held an appended int.
- Fixed `tuplegen.lrepr`: scalar list elements use `repr(x)`, so the value's own repr is used; compound elements keep their existing helper.
- Added `AIL_CURRENT/test_ail_fuzz65.py` and registered it in `ail_check.py`.
- Other observed, not fixed: `list[tuple]` heaps with a wrong-typed item still fail while printing (`int` not subscriptable) instead of printing CPython's list; `nan`/`inf` literals remain refused by name.
