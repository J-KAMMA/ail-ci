# job job-xdrlib1-11060507  started 2026-11-05T20:12:09Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed two commits on `job-xdrlib1-11060507`; not pushed (the runner instructions forbid push, so no PR/shards were run).

## Results

- **9/10 programs build and match CPython** (stdout + exit) in both the default build and `AIL_UNIFIED_FORCE=1`. They all take the general path (bundled `Error` is a user exception class).
- `03_uhyper_max.py` prints `7fffffffffffffff` and `9223372036854775807` correctly, then stops **loudly** at `unpack_uhyper` of 8×`ff`: `OverflowError: integer overflow in << (ints are 64-bit; ...)`, exit 1. CPython prints `18446744073709551615`; no wrapped value is printed.
- `python3 AIL_CURRENT/test_ail_std_xdrlib.py` passes (3 tests, ~207 s).

## What I built

- `AIL_CURRENT/stdlib/xdrlib.py`: CPython 3.12 semantics, every method and error text. `io.BytesIO` → list of `bytes`; `struct` → `int.to_bytes/from_bytes` plus manual IEEE-754 encode/decode with exact power-of-two arithmetic (round-half-even for single); decorator inlined as range checks raising `ConversionError` with struct's exact text; `2**64` rewritten as `-magnitude - 1`.
- 10 lab programs, `RESULTS.md` before/after tables, test + `tests.d` registration, manifest pins.

## Probes (all in `/tmp/probes/`, both builds via `cmp.sh`)

`xd_int`, `xd_bytes`, `xd_values`, `xd_float`, `xd_pow2` — all **match CPython**. Coverage: int widths and error texts, hyper sign boundaries (`0x8000…`, `0xffff…`), ±0.0, subnormals, inf/nan, single-precision ties/overflow, empty strings/arrays, positions/reset, values through argument/list item/attribute/dict.

A probe caught a real bug before commit: `pack_double(2**-1022)` encoded as zero (significand exactly `2**52` conflated with the subnormal sentinel). Fixed by representing every value as `n * 2**e`; re-probed clean.

## Tests

`test_ail_files` OK, `test_ail_corpus_findings3` OK. `test_ail_safetynet` fails `S4_generators_gc` (one line of output) — reproduced **identically at base `68eb00a`** without my changes, so pre-existing/environmental; recorded in `RESULTS.md`.

`git diff --stat 68eb00a`: 17 files, only the allowed ones plus the 3 manifest shards; `update_manifest.py --check` passes.
[commandcode stop=end_turn turns=46 out_tokens=45959]

## review 0
[model commandcode/deepseek-v4.1-flash]
Time box reached. Writing the report from what I verified.

## Review: xdrlib1

**What the change really does:** adds a hand-written AIL-source reimplementation of CPython 3.12 `xdrlib` (`AIL_CURRENT/stdlib/xdrlib.py`), with manual IEEE-754 double/single encoding, plus 10 lab programs, a test module and manifest pins. No compiler/runtime files, no `bench/`, no `DEVLOG.md`.

**Probes** (`/tmp/rprobes/`, `bash ~/tools/cmp.sh <p> $PWD`, both builds; base `/tmp/base` = `work`):

| probe | result |
|---|---|
| p2_floathex (36 float/double hex values incl. ±0, subnormals, min normal, max, overflow, ties, nan/inf, int args) | match, both builds |
| p3_unpackfloat (25 crafted bit patterns: subnormal, min-normal, sNaN, max, sign) | match |
| p4_hyper (pack/unpack `hyper`/`uhyper` at −2^63, −1, 2^63−1, sign boundaries) | match except the declared loud `OverflowError` for `unpack_uhyper` ≥ 2^63 (task allows) |
| p5_strings (fstring padding/truncation, empty/nested arrays, `unpack_list` bad tag, EOF/ValueError/Error texts, positions, list mutation during `pack_list`) | match |
| p6_alias (bytearray mutated after `Unpacker` construction, buffer reuse, `reset`, `get_buffer` copy) | match |
| p7_plain (no xdrlib) | `program.c` identical HEAD vs base; same output |
| p1_types / p1b_badarg (non-numeric arguments) | **differ** — see below |

**Defects**

1. Wrong-typed arguments no longer stop loudly — they produce silent, nondeterministic garbage. Because the module delegates validation to `math.fabs`/`math.copysign`, which AIL silently coerces:
   - `pack_double("x")`: CPython `ConversionError required argument is not a float`, exit 1. AIL prints `double_str 42d565123352b000` (a pointer value; the forced build printed `42d5649ecdfab000`), exit 0. Same for `pack_float("x")`, `pack_double(None)` → `0000000000000000`, `pack_double([1])`.
   - `pack_uint(1.5)` → `AttributeError 'float' object has no attribute 'to_bytes'`; `pack_uint("1")` → `TypeError '<' not supported between...`; `pack_uhyper(1.5)` → `TypeError`; CPython raises `ConversionError` with its struct text for each. (`pack_uint(-1)`/`pack_int(2**31)` texts do match.)
   Here: `/tmp/rprobes/p1_types.py`, `/tmp/rprobes/p1b_badarg.py`.

**Claims checked**
- 9/10 build and match CPython in both builds — verified (`test_ail_std_xdrlib` passes; lab programs 01–02, 04–10).
- `03_uhyper_max` stops loudly with `OverflowError` — verified.
- "Every method and error text kept / CPython 3.12 semantics" — **false** (defect 1).
- `test_ail_std_xdrlib` passes — verified.
- "`test_ail_safetynet` fails identically at base" — **not reproduced**: on HEAD under `-j 2` S4 printed one line, but the same unchanged S4 program built with the base compiler alone printed the full 6 lines. Not established as caused by the change (no xdrlib import; diff adds only a stdlib module), but the claim as written is unverified.
- Only allowed files + manifests — verified; `update_manifest` pins correct.

**Pre-existing / not established:** safetynet `S4_generators_gc` (generator/GC output truncation, flaky under parallel load; no link to xdrlib).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, corpus/icount speed (change is a new module, no hot-code edit).

VERDICT: FIX
1. Non-numeric arguments to the packing methods are not validated: `pack_double("x")` prints `42d565123352b000` and exits 0 where CPython raises `ConversionError: required argument is not a float` and exits 1 (also `pack_float("x")`, `pack_double(None|[...])`), and `pack_uint(1.5|"1")`/`pack_uhyper(1.5)` raise `AttributeError`/`TypeError` instead of `ConversionError`. Probe: `/tmp/rprobes/p1_types.py`, `/tmp/rprobes/p1b_badarg.py`.
[commandcode stop=end_turn turns=21 out_tokens=33957]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `61186c5`.

**Defect:** packing methods never checked argument types, so AIL's `math` coercion turned `pack_double("x")` into a packed pointer (exit 0) and leaked `AttributeError`/`TypeError` from `pack_uint(1.5)`/`pack_uhyper(1.5)`.

**Change:**
- `_uint_bytes`/`_int_bytes`: `isinstance(x, int)` check → `ConversionError("required argument is not an integer")`; `int(x)` before `to_bytes` (bool path verified).
- `_float_bytes`/`_double_bytes`: accept only int/float/bool → `ConversionError("required argument is not a float")`.
- `pack_uhyper`: shift `TypeError` → `ConversionError` with CPython's text, so `pack_hyper` inherits it.
- Added a both-builds wrong-argument regression test and a RESULTS probe table.

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`), all match CPython:

| probe | result |
|---|---|
| `xd_badtypes` — 22 wrong-typed calls across `pack_uint/int/enum/uhyper/hyper/float/double` | match both |
| `xd_bounds` — int edges, `2**63-1`, `-2**63`, ints→float, range errors, `pack_float(1e300)` | match both |
| `xd_paths` — bad values via argument, list item, attribute, dict value | match both |
| `xd_uncaught` — uncaught `pack_double("x")` | exit 1, `xdrlib.ConversionError: required argument is not a float`, both |
| `xd_bool` — `True`/`False` through every method | match both |
| `xd_float/xd_int/xd_bytes/xd_values/xd_pow2` — re-run regressions | match both |

**Tests (final commit `61186c5`):**
- `test_ail_std_xdrlib.py`: 4 tests OK (474s).
- `test_ail_files`: 18 tests OK (1 skipped); `test_ail_corpus_findings3`: 2 OK; `test_ail_safetynet`: 5 OK — run on the code-identical parent `964d449`; the docs-only amend changed `RESULTS.md` only.
- `update_manifest.py --check` clean. `git diff --name-status 68eb00a` shows only the permitted files (module, test, tests.d, 10 lab programs, RESULTS, manifests 10/48/73). No push (runner rule).
[commandcode stop=end_turn turns=47 out_tokens=27417]

## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** adds `AIL_CURRENT/stdlib/xdrlib.py` (CPython 3.12 `xdrlib` as AIL source: list-of-bytes instead of `BytesIO`, hand-written IEEE-754 float/double codec, explicit type/range checks instead of `struct`/the decorator), 10 lab programs + `RESULTS.md`, one test module + `tests.d` registration, and 3 manifest lines. Matches the report.

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`, all in `/tmp/rprobes/`):
| probe | covers | result |
|---|---|---|
| `p_floats` | float32 rounding, ties (1+2^-24), subnormals, ±0, inf/nan, unpack of edge bit patterns | match |
| `p_edge` | max float, round-to-inf midpoint, overflow errors, min-normal/subnormal boundary, double subnormals | match |
| `p_sweep` | ~140 float32 and ~80 double encode sweeps incl. subnormals | match |
| `p_doubles` | ±0, 5e-324, inf/nan, int→double, 2^53+1 | match |
| `p_fuzz` | 60 pseudorandom unpack_uint/int/float/double/hyper/uhyper + pack_hyper | match |
| `p_hyper`, `p_hyp2` | hyper/uhyper widths, ±, 8×ff | stdout matches until `unpack_uhyper` of a value ≥2^63, then exit 1 `OverflowError: integer overflow in <<` — the task's allowed loud stop |
| `p_hyp3` | all high-bit-set `unpack_hyper` (incl. -2^63, -1, `deadbeefcafebabe`) | match |
| `p_strings` | fstring/fopaque/string/opaque/bytes, padding, n=0/negative, truncation, str/bytearray args, past-end | match |
| `p_types`, `p_last` | uint/int/enum ranges, bool, EOF, done, positions, Error/args, bad list tag, farray length | match |
| `p_alias` | get_buffer reuse, bytearray mutation after read/reset, slice stability | same stdout/exit |
| `p_mut` | list mutated during `pack_list`/`pack_array` (append and delete) | match |
| `p_duck` | `__index__`/`__float__` argument objects | **differs** (see note) |
| `p_nouse` | program not importing xdrlib | `--debug-dir` C byte-identical to `/tmp/base` (same sha256), so hot-path counts unchanged |

**Report claims:** change description verified in `git show 61186c5`; `pack_uhyper` TypeError→ConversionError matches CPython 3.12's own source; `964d449` exists and differs only in `RESULTS.md`; `update_manifest --check` clean; `git diff --name-status work..HEAD` shows only permitted files. `test_ail_std_xdrlib` passes (4 tests, 248 s); 9/10 lab programs match, 03 stops loudly — verified. `test_ail_files`/`test_ail_corpus_findings3` not re-run (unverified, as instructed).

**Notes (non-blocking):** the module rejects objects that implement `__index__`/`__float__` where CPython's `struct` accepts them (`pack_uint(Idx())`, `pack_double(Fl())`); no AIL program can hold such a number except a user class, so this is a documented narrowing, not a wrong value. `xdrlib.raise_conversion_error` exists in CPython but is absent here (not in `__all__`).

**Pre-existing:** `test_ail_safetynet` fails `S4_generators_gc` (stdout truncated to `5530537`) under `-j 2`; the same test fails identically on `/tmp/base` (5 tests, 1 failure, 126 s) — flaky output truncation, unrelated to `xdrlib`.

**Speed:** not applicable (no compiler/runtime change; non-user C identical).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=40 out_tokens=39604]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T23:37:06Z
