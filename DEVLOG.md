# DEVLOG

## 2026-10-24 - cov7: the census's internal-crash refusals now build

The gdev census (510 programs, `AIL_NO_CACHE=1`) refused 53 before this job.  Grouped by the
first line of the build output, the most common group was the 3 internal tracebacks (not
deliberate refusals): two programs using `functools.partial` crashed in
`pyboxed2._refuse_lambda_forward_defaults` because the general path's partial rewrite made
`Lambda` nodes without a line number, and one visitor program crashed in
`pyfunc._dispatcher` with `KeyError: 'Visitor__visit_directory'` because an abstract base method
(removed as a stub) was chosen as the dispatcher's representative.  The partial rewrite now
copies locations onto both lambdas, and the dispatcher falls back to the first concrete
implementation when the base has no body.  `g17_004`, `g17_024` and `g13_036` now compile and
print what CPython prints on both builds; the census refused 50 afterwards.  Added the positional
partial program to `test_ail_silent6.py` and an abstract-visitor hierarchy to
`test_ail_typed_inherit.py`.
## 2026-10-24 - GC rooting in the statistics helpers (job-gcroot-10241807)

The general path's native `statistics` helpers kept a heap result in a C local across an
allocating call. `ail2q_partials` built its result list and then boxed every float in it, and
`ail2q_ssd_dd` boxed its first tuple element before allocating the second; both relied on
`AIL2Z_PAUSE` to stop collection. `AIL_GC_STRESS` collects at every allocation regardless of
the threshold, so the unrooted list/tuple elements were freed and overwritten:
AddressSanitizer reported a heap-use-after-free in `ail2q_partials` on
`corpus/gdev/g03_000.py` and `g03_018.py`. Both now register the live locals with
`AIL_ROOT1` / `AIL_ROOT_N` until the last allocation. Added
`test_ail_gcstress.PROGRAMS['statistics_partials']` and its test; it fails with the old
runtime and passes now. The analogous code in `jsonbrt.py` was checked: `ail_tuple_new`
already roots the item array it is given, so no change was needed there.
## 2026-10-23 - binary_cursor_records: runtime traps are noreturn (job-perf3-10240012)

`BinaryCursor__remaining` checks `0 <= position <= len(data)` and then calls `ail_raise_named`, but the
runtime declared that trap as an ordinary `void` function. GCC therefore had to keep the fall-through
path alive and could not use the test to prove the subtraction cannot overflow, so `ck_sub` stayed in
the accessor. `ail_exception_uncaught` has the same property (it ends in `_Exit(1)`), so both now have
an explicit `__attribute__((noreturn))` declaration in `cruntime.py`. No app source changed.

Profiling: rdtsc instrumentation of the generated C (40M records, 496 MiB) put the per-record loop at
709,541,927 of 1,193,992,702 cycles (59.5% of the function). The accessor checks are inside that loop;
hand-edited generated C put the `ck_sub` in `remaining()` alone at ~8% overall and all unchecked reads
at ~16%, so the 9.1% below is in line with that ceiling.

`python3 bench/compare.py --app binary_cursor_records`:

| | AIL/C | AIL new/base/C/Rust ms | RSS MiB new/base/C/Rust | binary KiB new/base/C/Rust |
| --- | ---: | ---: | ---: | ---: |
| before | 5.091 [5.041, 5.253] | 50.8/50.8/10.0/9.6 | 1.7/1.7/2.5/2.7 | 39/39/15/1912 |
| after | 4.630 [4.607, 4.674] | 46.0/51.0/9.9/9.6 | 1.7/1.7/2.5/2.7 | 35/39/15/1912 |

Ratio improved 9.1%; `compare.py` checked every timed run byte-for-byte against its Python oracle.
Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`,
`test_ail_exception_values_core`, `test_ail_exception_values_app`, `test_ail_excfix`,
`test_c_api_bridge`, `test_ail_parallel_for`, `test_ail_short_style_traps` all pass. Probes
`/tmp/probes/perf3_*.py` match CPython on both the general and default builds.
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
## 2026-10-23 - csv_table: inline small leaf loops (job-perf4-10240813)

`field += ch` was already in place and its slow path is about 1% of calls, so this job took
the next cost. Profiling a 132 MB three-million-row input (`gprof -pg`) put
`csv_table_group_scan` at 79% and `parse_int64_decimal` at 2.15% flat. Flat cost understates
it: replacing the parse with a constant saved 7.3% of wall time, while asking gcc to inline
that same nine-statement leaf loop saved 20% (1.24 s -> 0.99 s, user 1.08 s -> 0.84 s). The
extra is the call boundary in the row loop, not the digit loop. The feed/chunk copy was a
larger upper bound (14.5% if the chunk buffer is reused unsafely) but safe per-chunk ownership
saved only 1.6%, so it was rejected.

The compiler now asks for `always_inline` on a function whose body is one `for` loop, no
other loop/try/with/yield, no call to another function or class constructor, a scalar numeric
return, at most 12 statements and 180 AST nodes; recursion, entry points and the existing
straight-line rule are unchanged. In `csv_table` this fires on `parse_int64_decimal` and
`parse_int64_decimal_bytes` only. String/list/object returns are excluded: inlining
`json_quote` as well measured 1.42 s, slower than 1.25 s.

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 14.5/14.5/6.1/6.9 | 0.995 [0.992,1.016] tie | 2.390 [2.341,2.456] slower | 2.093 [2.053,2.252] slower |
| 12.1/14.6/6.1/6.9 | 0.841 [0.814,0.852] faster | 1.979 [1.972,2.031] slower | 1.770 [1.717,1.800] slower |

RSS 5.5/5.5/3.3/3.8 -> 5.5/5.5/3.3/3.6 MiB, binary 107/107/20/1928 -> 111/107/20/1928 KiB,
build disk 400/400/44/1952 -> 412/400/44/1952 KiB. The app's boundary controls and Python
oracle still pass byte-for-byte.

Tests: `test_ail_integer_codec test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_csv_writer test_ail_utf8_stream_fuzz test_csv_column_stats_stream` (24 tests) and
`test_ail_safetynet test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass.
Probes `/tmp/probes/loop_inline.py` and `/tmp/probes/loop_inline_objects.py`
(`bash ~/tools/cmp.sh`) cover negative/empty/invalid parse paths, early return, break/continue,
loops reached through arguments, list items and dict values, and string/list/dict mutations;
both builds match CPython stdout on every case.

## 2026-10-23 - csv_table: one UTF-8 scan per chunk (job-perf4-10240013)

`field += ch` was already in place. The generated code calls `ail_str_cat`, whose first
cases return the existing value or a view when the operands are adjacent, and whose
remaining case appends into the newest arena block with amortized growth
(`AIL_SARENA_TOPS`). The slow path is about 1% of calls; forcing the builder-local path
(`ail_bl_append`, which copies `key = field` per row) measured 3.29 s against 2.48 s on a
263 MB file, so it was rejected.

Profiling the rest (`gprof -O3 -pg`, same file) put `_utf8_complete_length` at 11.2% and
`ail__utf8_validate` at 9.1%: `utf8_decode_feed` scanned `combined` to find the last
character boundary and then `decode("utf-8")` scanned it again to validate. A chunk only
ends mid-character at a chunk boundary, so `_utf8_tail_complete` now checks the final byte
(and at most three continuation bytes) and sends the whole buffer straight to decode. The
full `_utf8_complete_length` scan still runs for the rare split chunk, so the pending bytes,
the feed on which an error is reported, and the decoded text are unchanged. Amdahl bound
about 11%; measured 7.0% on the app (AIL/base 0.930).

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 16.5/16.5/6.9/7.8 | 1.006 tie | 2.387 slower | 2.126 slower |
| 15.5/16.7/7.0/8.0 | 0.930 faster | 2.200 slower | 1.933 slower |

RSS 5.5/5.5/3.2/3.8 -> 5.5/5.5/3.2/3.6 MiB, binary 107/107/20/1928 KiB unchanged, build
disk 400/400/44/1952 KiB unchanged. The app's boundary controls and the Python oracle still
pass byte-for-byte.

Tests: `test_ail_utf8_stream_fuzz test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_splitlines_utf8 test_csv_column_stats_stream` (18 tests) and `test_ail_safetynet
test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass. Probe
`/tmp/probes/utf8_tail.py` (`bash ~/tools/cmp.sh`) compares the old and new boundary logic
on 5,232 curated and random byte strings: same stdout, 0 mismatches, in both builds.
## 2026-10-24 - bytes.count memmem: self-contained declaration (job-perf7-10240917)

Review found the short-needle `bytes.count` path called `memmem` without a declaration in the
emitted C, so `gcc -std=c11` (a mode AIL uses for `to_c` and C-object builds) assumed an implicit
`int` return and truncated the pointer (segfault). The `BYTES` block now declares `memmem`
itself on non-Windows, after `<string.h>`; glibc and musl both export the symbol, and the
declaration is compatible with the header's when `_GNU_SOURCE`/`_DEFAULT_SOURCE` is set.
`rp7_count_small.py` now prints `4 2 2` under `-std=c11 -O2` and `-std=gnu17`; all count probes
match CPython on both builds, and `binary_search` is unchanged at 64.9 ms vs base 92.0 ms
(`ail/base 0.711 [0.706,0.717]`). Required tests pass.

## 2026-10-24 - bytes.count: memmem for short needles (job-perf7-10240917)

`binary_search` (`count` of a 7-byte needle over a 64 MiB file) spent ~69 ms of its 94 ms in
`ail_bytes_count_range`, which used the byte-pair Horspool scan. For a short needle glibc
`memmem` is about twice as fast on the same data (38 ms vs 71 ms), so the non-Windows
short-needle path now uses the same non-overlapping `memmem` loop as the C reference; Windows
keeps Horspool. `bench/compare.py --app binary_search`: base 98.2 ms, new 69.2 ms
(AIL/C 1.414 -> 0.994, ranges non-overlapping). Probes for empty, negative, windowed and
64-byte needles through arguments, list items, attributes and dict values match CPython on both
builds.
## 2026-10-23 - str format spec: a space sign names CPython's ValueError (job-pre18-10240245)

The first pre-existing difference recorded by the fuzz66 reviewer still reproduces on this tree:
`format('x', ' z')` raised `ValueError: Sign not allowed in string format specifier`, where CPython
says `Space not allowed in string format specifier`. The same wording bug covered every str spec
with a space sign.

`AIL_CURRENT/python/pkg-v12/safetyrt.py` now distinguishes the space flag from `+`/`-` in
`ail2f_format`'s str branch. `AIL_CURRENT/python/pkg-v12/pyboxed2.py` sends a str spec that carries
any sign to `safetyrt.FMT` instead of the core formatter, which silently ignored the flag (so
`format('x', '+')` returned `x` and `format('x', ' ')` padded it). Numeric sign flags and str specs
without a sign are unchanged.

`test_ail_pre18.py` covers the recorded case, all sign spellings, literal and computed specs,
widths/alignment, empty and non-ASCII values, values from an argument/list item/attribute/dict
value, and numeric sign formatting on both builds. It and `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` pass on the final commit.
## 2026-10-23 - pre19: refuse `del` bounds a constant cannot evaluate in int64 (job-pre19-10240254)

The first still-differing case recorded after pre7 is `maxi`, `del a[2**63 - 1]`: the final value
fits in an AIL int64, but evaluating `2**63` first trapped `integer overflow` on both builds where
CPython raises IndexError. `negmin`, `powhuge` and `slicebig` (`del a[2**100:2**101]`, a silent
exit-1 versus CPython's exit 0) have the same cause. `pyfront.refuse_unrepresentable_delete_bounds`
evaluates the constant index or slice bounds exactly, including the intermediate values, and
refuses the `del` by name when any value leaves the 64-bit signed range; it is called from both the
typed path (`pyfunc.py`) and the general path (`pyboxed2.py`). In-range constants and the same
expression outside a `del` are unchanged, and the C runtime is untouched.

Tests on this commit: `test_ail_pre19` (new, both builds), `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`; `update_manifest.py --check` rc 0.
## 2026-10-23 - A constant power outside int64 is refused by name (job-pre2)

The pre-existing `r_aliasing.py` difference was `2 ** 63`: CPython prints
9223372036854775808, while AIL compiled it and then stopped with `integer overflow`. The value is
known at compile time and has no int64 answer, so `_check_int64_literals` now evaluates a constant
integer `**` and raises `int64 constant power out of range: <base> ** <exponent>` before codegen
(the same place an out-of-range literal is refused). `2 ** 62`, `(-2) ** 63` (INT64_MIN) and the
float/small-power cases still compile and match CPython. `test_ail_pre2.py` covers both builds and
both syntaxes.
## 2026-10-23 - pre22: `with` around `yield` (job-pre22-10240312)

The p12/p23/p24 case still differs on this tree: a generator with `with` around its `yield`
and then `g.close()` runs no `__exit__` at all, because the general path's generator close finishes
the fiber without running the suspended frames (CPython raises `GeneratorExit` there and passes it
to `__exit__`). Building real `GeneratorExit` close semantics is a runtime change outside this job,
so the construct is refused by name before file-lowering removes the `with`:

* `withlib.refuse_with_yield` (called from `pyboxed2.Compiler.compile`) refuses any `with` whose
  body yields in the same function, for every manager expression and for `with open(...)` too.
* `test_ail_pre22.py` covers the refusal on both builds and checks that a `with` beside (not
  around) a `yield` still runs and matches CPython.
## 2026-10-24 -- pre26: repr(e.args[i]) keeps the argument's kind

On the typed path `e.args[i]` reads as text, so `repr(e.args[i])` repr'd that text: a
`ValueError(3.0)` handler printed `'3.0'` where CPython prints `3.0`, and int, bool and None
arguments were quoted the same way.  The handler rewrite now lowers `repr(e.args[i])`,
`f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor that formats
the stored argument (a str keeps its quotes, a number does not).  Both builds agree with
CPython; `test_ail_pre26.py` keeps the probe, including negative and out-of-range indexes.

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
## 2026-10-23 -- job-fuzz89-10231611

- Fixed the general path's `bytes`/`bytearray` whitespace `split`/`rsplit` when `maxsplit` is
  reached: the remainder now keeps the outer whitespace, as CPython does
  (`b" a ".split(None, 0) == [b"a "]`, `b"  a  b  ".rsplit(None, 1) == [b"  a", b"b"]`).
  The typed-path loops already had CPython's rule.
- Added `test_ail_fuzz89.py` (both builds against CPython) and registered it in `ail_check.py`.
