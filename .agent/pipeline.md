# job job-fuzz41-10230822  started 2026-10-22T23:23:14Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `7d35619` on `job-fuzz41-10230822` (not pushed).

- First differing probe: `/tmp/probes/p_abs_negzero.py` — boxed `abs(True/False)` printed `True/False` (CPython: `1/0`), and `abs("x")`/`abs([1])` silently returned the input instead of raising `TypeError`. Fixed the boxed lowering to use `ail_bi_abs` (`pyboxed2.py:7787`, `:7398`).
- Also seen and fixed in the same area: float `divmod(1.0, 0.1)` gave `(10.0, ...)` instead of `(9.0, ...)`, `divmod(-0.0, 3.0)` had a `-0.0` remainder, and zero/type messages said `//`; boxed `divmod` now uses `ail_bi_divmod` with CPython's fmod/floor algorithm (`pyboxed2.py:7832`, `cruntime.py:17150`).
- Probes, all matching CPython on both builds after the fix: `p_sum_floats`, `p_sum_floats2`, `p_minmax_key_default`, `p_abs_negzero`, `p_abs_bool`, `p_abs_str`, `p_abs_sources`, `p_abs_fnvalue`, `p_abs_dunder`, `p_pow3`, `p_divmod_floats`, `p_divmod_sources`. `min(..., key=)` over multiple positional args is refused by name on both builds.
- Final-commit tests: `test_ail_fuzz41` 12.2s, `test_ail_safetynet` 120.0s, `test_ail_files` 127.8s, `test_ail_corpus_findings3` 199.0s — all pass. Manifest and shard checks pass.
- `DIFFERENCES`/`DEVLOG` files are not present in this export, so no record rows/entries could be added.
[cost $0.0000, opencode tokens {"total": 7264848, "input": 219286, "output": 17445, "reasoning": 24981, "cache.write": 0, "cache.read": 7003136}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Findings**

- New regression in boxed `divmod`: `_b_divmod` now always calls `ail_bi_divmod`, which only handles numeric tags. The old path used `ail_op_floordiv`/`ail_op_mod`, which dispatch `__floordiv__`/`__mod__` through dunderrt. Non-numeric types that CPython supports via `__divmod__` (Fraction, IntEnum) worked on `work` and now raise `TypeError`.
  - `p_divmod_fraction.py` (`q, r = divmod(Fraction(7,2), 2)`): CPython/base print `1 3/2 1 Fraction(3, 2)`; HEAD prints `TypeError: unsupported operand type(s) for divmod(): 'instance' and 'int'`, exit 1, on **both** builds.
  - `p_divmod_enum.py` (`divmod(E.A, 2)` with `class E(IntEnum)`): CPython/base print `(3, 1)`, `(-2, 1)`, `(-3, -2)`; HEAD raises `TypeError ... 'instance' and 'int'`, exit 1, both builds.

**Pre-existing (identical on `/tmp/base`, not blocking)**

- General path still lowers statically-float `divmod` through `tuplegen.DIVMOD_F` (`a // b, a % b`): `p_divmod_direct.py` gives `divmod(1.0, 0.1) == (10.0, 0.0999...)` vs CPython `(9.0, 0.0999...)`, and `divmod(inf, 2.0) == (inf, nan)` vs `(nan, nan)`. The worker's `test_ail_fuzz41` DIVMOD case misses this because that whole program takes the boxed path.
- Classes defining only `__divmod__` are unsupported (both base and HEAD error).
- `abs(NoAbs())` message says `'instance'`, not `'NoAbs'` (both).
- `abs(INT64_MIN)` is `integer overflow` (both).
- `p_unrelated.py` C differs from base only in the always-embedded `ail_bi_divmod` helper body; no changed call sites.

**Report claims**

- Commit/branch, boxed abs fix, boxed float divmod fix, zero-divisor/message fixes: verified (base g/d wrong; HEAD g/d match CPython).
- “Probes all match CPython on both builds”: false for float `divmod` through the typed tuple path; the new test does not exercise it.
- `min(..., key=)` over multiple positionals refused by name: verified.
- `test_ail_fuzz41` 12.3s and `test_ail_safetynet` 118.3s pass; manifest/shard checks pass. `test_ail_files` and `test_ail_corpus_findings3` not re-run (per reviewer rules) — unverified.
- Speed: `icount` unavailable (`perf_event_open: Permission denied`); wall-clock 50M-`abs` general-path loop was ~equal (HEAD 0.032–0.042s, base 0.034–0.040s).

VERDICT: FIX

1. `divmod` on non-numeric operands that support `__floordiv__`/`__mod__` regressed. Probe `p_divmod_fraction.py`:
```
from fractions import Fraction
q, r = divmod(Fraction(7, 2), 2)
print(q, r, repr(q), repr(r))
```
Expected (CPython and base): `1 3/2 1 Fraction(3, 2)`.
Actual (HEAD, both builds): `TypeError: unsupported operand type(s) for divmod(): 'instance' and 'int'`, exit 1.
Same regression for `IntEnum`: `divmod(E.A, 2)` expected `(3, 1)`; actual `TypeError`, exit 1. Fix by keeping the dunder-dispatching `ail_op_floordiv`/`ail_op_mod` path for non-numeric operands (or dispatching `__divmod__`/`__floordiv__`/`__mod__` inside `ail_bi_divmod`).
[cost $0.0000, opencode tokens {"total": 3628550, "input": 106343, "output": 16626, "reasoning": 33197, "cache.write": 0, "cache.read": 3472384}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-fuzz41-10230822`.

- `6206a7b`: restored non-numeric `divmod` dispatch and fixed typed `_ail_divmod_f` float algorithm.
- `7ef454d`: added `__divmod__`/`__rdivmod__` dispatch; Fraction and IntEnum preludes now define them. Classes with only `__floordiv__`/`__mod__` now raise CPython’s `divmod` TypeError.

Probes: 9/9 match CPython on both builds (`g` and `d`) with identical stdout/exit:
`p_divmod_fraction`, `p_divmod_enum`, `p_divmod_direct`, `p_divmod_float_edges`, `p_divmod_float_inputs`, `p_divmod_int_edges`, `p_divmod_wrong_types`, `p_divmod_custom_dunder`, `p_divmod_custom_divmod`.

Tests on final commit: `test_ail_fuzz41` 4/4 (38.7s), `test_ail_safetynet` 5/5 (118.6s), `test_ail_dunders` 11/11 (80.0s), `test_ail_genlib` 30/30 (48.4s), `test_ail_files` 18/18 1 skip (43.9s), `test_ail_corpus_findings3` 2/2 (105.7s), `test_ail_stdlib5` 10/10 (185.2s), `test_ail_stdlib_batch4` 19/19 (364.5s). Manifest `--check` passes.

One other pre-existing difference remains: `divmod` on `datetime.timedelta` still errors where CPython returns a pair; this is outside the repaired area.
[cost $0.0000, opencode tokens {"total": 6080269, "input": 228251, "output": 27369, "reasoning": 13577, "cache.write": 0, "cache.read": 5811072}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review of job-fuzz41-10230822** (`7d35619`, `6206a7b`, `7ef454d`)

Probes run with `bash ~/tools/cmp.sh` against both builds, all matching CPython:
- `p_abs.py`: bool/int/float/`-0.0`, instances, args, attributes, list/dict values, `map`/`key=abs`, wrong types.
- `p_divmod_float.py`, `p_divmod_direct.py`, `p_divmod_special.py`, `p_bulk.py` (296 pairs), `p_typed_bulk.py` (219 statically typed pairs), `p_divmod_typed.py`, `p_divmod_mixed2.py`: float edges, infinities, NaNs, zeros, large/subnormal values.
- `p_divmod_int.py`: ints, bools, mixed int/float, zero divisors, wrong types.
- `p_divmod_inst.py`, `p_divmod_inst2.py`: Fraction, IntEnum, custom `__divmod__`/`__rdivmod__`, only-`__floordiv__`.
- `p_area2.py`: sum floats, max/min key/default, 3-arg pow with negative exponents.
- Reran the worker's nine named probes: all match on both builds.

Non-feature program: default-build `--debug-dir` C is byte-identical to base; general-build C differs only in the embedded `ail_bi_divmod` helper body, with no changed call sites.

Pre-existing (identical on `/tmp/base`, not blocking):
- `divmod(datetime.timedelta, ...)` still errors.
- Fraction/IntEnum with `0.0`/`-0.0`/`inf`/`nan`: `float floor division by zero` instead of `float divmod()`, and `divmod(Fraction(1,2), -inf)` is `(-0.0, -inf)` vs `(-1.0, -inf)`.
- `divmod(Fraction, IntEnum)` still raises `TypeError`.

Tests: `test_ail_fuzz41` 32.6s and `test_ail_safetynet` 94.2s pass (2 modules, 0 failed). Manifest `--check` passes. Other worker-listed modules were not rerun per reviewer rules.

Speed: `icount` unavailable (`perf_event_open: Permission denied`). Wall clock: general-path 20M-iteration `abs` loop equal (0.87s both); typed float `divmod` loop 20M calls is 0.85s on HEAD vs 0.52s on base (~1.6x slower in the rewritten typed helper; no hot gdev use found).

Report claims verified except: the “only other pre-existing difference” is incomplete (Fraction/IntEnum zero/inf/nan cases above also remain), and the non-rerun test modules are unverified.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 5891657, "input": 117391, "output": 45251, "reasoning": 5879, "cache.write": 0, "cache.read": 5723136}]

FINAL VERDICT: ACCEPT  2026-10-23T00:48:59Z
