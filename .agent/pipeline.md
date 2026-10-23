# job job-fuzz69-10231457  started 2026-10-23T05:58:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `bbd3b03`.

**Change:** `round(x, n)` with negative `n` now rounds the double’s exact decimal expansion instead of scaling by an inexact `10**k`, on both typed and general paths. Also fixed `n > 323` (returns `x`) and general-path `ndigits` type handling (`TypeError` for float/str, `None` as one-argument form).

**Files:** `cruntime.py`, `pyfunc.py`, `pyboxed2.py`, `ail_check.py`, `MANIFEST.json`, new `test_ail_fuzz69.py`.

**Tests (final commit, `-j 2`):** `test_ail_fuzz69`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 332s. Manifest `--check` clean.

**Probes:** `f01`, `f02`, `f04`, `f04b`, `f04c`, `f04d`, `f04e`, `f04f` match CPython on both builds. `f04c`/`f04d` cover dynamic ndigits and overflow through arguments, lists, dicts and attributes.

**Other differences seen (not fixed):**
- `f03`: `int(1e300)` stops with `integer overflow`; CPython returns a big int (pre-existing int64 boundary).
- `f05`: same stdout/exits, but zero-division messages differ (`division by zero` vs `float division by zero`, and `divmod` wording).
- `f06`: general path `inf // 2.0` prints `inf`, CPython prints `nan`; default build matches.

No `DEVLOG`/`DIFFERENCES` files exist in this export, so none were added.
[cost $0.0000, opencode tokens {"total": 8997063, "input": 161189, "output": 22530, "reasoning": 37920, "cache.write": 0, "cache.read": 8775424}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

Scope: `git diff work..HEAD` (commit `bbd3b03`) changes `round(x, n)` for negative `n`, positive `n > 323`, and general-path `ndigits` typing.

**Values / feature checks (pass)**
- Negative `n` values match CPython on both builds: `p01`, `p02`, `p03`, `p04`, `p08`, `p19`; plus a reimplementation fuzz over 60k random `(x, n)` cases found no numeric mismatch.
- `n > 323` boundary (`323/324/400/1000`) matches: `p06`, `p19`.
- `round(x, None)` and numeric `x` with float/str `ndigits` match: `p05`, `p12`, `p15`.
- Non-feature program `p11`: generated `program.c` is byte-identical to `/tmp/base` (only temp paths in `native_report.json` differ).
- Tests on HEAD: `test_ail_fuzz69`, `test_ail_safetynet` = 0 failed, 124s; `test_ail_files`, `test_ail_corpus_findings3` = 0 failed, 209s (333s total, matching the report). Manifest `--check` clean.
- Speed: `perf_event_open` is denied here (`perf_event_paranoid=4`). Wall-clock over 300 runs is identical (`g21_016` 0.32s/0.32s, `g21_038` 0.23s/0.23s head/base).

**Defects**

1. The new `ail_bi_round_obj` checks `ndigits` **before** checking whether `x` supports `__round__`. For non-numeric `x`, CPython reports the `x` type error regardless of `ndigits`; HEAD reports the `ndigits` type error. Base matched CPython. Probe `/tmp/rprobes/p21.py`:
   ```python
   def r(x, n):
       try: return repr(round(x, n))
       except Exception as e: return type(e).__name__ + ": " + str(e)
   print(r([], 2.0)); print(r("x", 2.0)); print(r(None, 2.0))
   print(r({}, 2.0)); print(r((1,), 2.0)); print(r([], "2")); print(r([], [2]))
   ```
   Expected (CPython, and base both builds):
   `TypeError: type list doesn't define __round__ method` / `... str ...` / `... NoneType ...` / `... dict ...` / `... tuple ...`
   Actual HEAD (both builds):
   `TypeError: 'float' object cannot be interpreted as an integer` / `... 'str' ...` / `... 'list' ...`
   The same ordering also preempts a user `__round__` (`/tmp/rprobes/p20.py`: `round(c, 2.0)` should call `__round__(2.0)`); base passed a garbage int there, so that case was already wrong, but the new check still prevents correct dispatch.

2. Default/typed path overflow message differs. Probe `/tmp/rprobes/p17.py`:
   ```python
   try:
       print(repr(round(1.7976931348623157e308, -308)))
   except Exception as e:
       print("caught Exception", type(e).__name__, str(e))
   ```
   Expected: `caught Exception OverflowError rounded value too large to represent`
   Actual default build: `caught Exception OverflowError integer overflow`
   The general build matches CPython. Base returned `inf` (no exception), so this is not identical on base.

**Pre-existing (identical head vs base)**
- `f03`: `int(1e300)` stops at the int64 boundary (`integer overflow`).
- `f05`: `divmod`/float-by-zero message wording differs.
- `f06`: general path `inf // 2.0` prints `inf` instead of `nan`; default build matches.

Claim check: files, test timings, manifest, `n > 323`, negative-`n` values, and the listed f03/f05/f06 differences verified. The claim about general-path `ndigits` handling is only partially true: correct for numeric `x`, wrong ordering for non-numeric `x`.

VERDICT: FIX
1. `ail_bi_round_obj` must let non-`__round__` `x` determine the error, or dispatch `AIL_T_INST.__round__` first; currently `round([], 2.0)` gives the `ndigits` TypeError instead of `type list doesn't define __round__ method` (p21).
2. Typed/default path must raise `OverflowError("rounded value too large to represent")`; currently it raises `OverflowError("integer overflow")` (p17).
[cost $0.0000, opencode tokens {"total": 2920829, "input": 173634, "output": 15284, "reasoning": 42887, "cache.write": 0, "cache.read": 2689024}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed as `23af80d`.

**Fixes**
- `ail_bi_round_obj` now validates the receiver before `ndigits`; non-numeric `x` raises its own `TypeError`, and general-path user `__round__` receives the raw `ndigits` value (`dunderrt.py` patch).
- Typed/default-path negative-`ndigits` overflow now raises `OverflowError("rounded value too large to represent")`; the message is mapped by the `OVERFLOWEXC` splice.
- Added both regressions to `test_ail_fuzz69.py`.

**Probes** — all match CPython on both builds:
`p17` overflow message; `p20`/`p25`/`p26` user `__round__` with float/str/list/None; `p21`/`p22`/`p23` non-numeric receiver ordering (direct, argument, list item, attribute, dict); `p24` numeric receiver with bad `ndigits`; `p27`/`p28` overflow through arguments, lists, attributes and dicts.

**Tests on final commit** (`-j 2`): `test_ail_fuzz69`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 258s. Manifest `--check` clean.

No `DEVLOG`/`DIFFERENCES` files exist in this export, so none were added. Pre-existing differences left untouched: `f03` `int(1e300)` int64 boundary, `f05` zero-division wording, `f06` general-path `inf // 2.0`.
[cost $0.0000, opencode tokens {"total": 3173204, "input": 261332, "output": 9803, "reasoning": 10165, "cache.write": 0, "cache.read": 2891904}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Scope:** `git diff work..HEAD` (`bbd3b03`, `23af80d`); probes in `/tmp/rprobes/p1.py`–`p16.py`, HEAD and `/tmp/base`, both builds.

**Verified**
- Negative `ndigits`, ties, subnormals, `-308/-309`, `>323`: `p1`, `p5`, `p14`, plus a 60-random-double × 22-`n` fuzz (`p12`) match CPython on both builds.
- Receiver-before-`ndigits` ordering and user `__round__` value for float/str/list: `p2`, `p3` match.
- Overflow values/message through literal, argument, list, attribute, dict: `p4`, `p5` match.
- Non-feature `p15`: generated C differs only by the added `"rounded value too large..."` `strcmp` mapping (behaviour-neutral).
- `test_ail_fuzz69`, `test_ail_safetynet`: 0 failed (123s); manifest `--check` clean.
- `perf_event_open` denied, so speed was not measured.

**Pre-existing:** `f03`, `f05`, `f06` as reported; one-argument `round(u)` for a required-`n` `__round__` is identical on base/HEAD.

**Claim check:** fixes for review-0 items 1 and 2 are verified; the claim that general-path `__round__` always gets the raw `ndigits` is false for `None`, and the new `ndigits` gate is too narrow.

VERDICT: FIX
1. Valid `__index__` `ndigits` are now rejected. Probe:
   ```python
   class I:
       def __index__(self): return 2
   def r(x, n):
       try: return repr(round(x, n))
       except Exception as e: return type(e).__name__ + ": " + str(e)
   print(r(1.5, I())); print(r(1234.5, I())); print(r(1, I())); print(r(True, I()))
   ```
   Expected (CPython **and** base, both builds): `1.5`, `1234.5`, `1`, `1`.
   Actual HEAD (both builds): `TypeError: 'instance' object cannot be interpreted as an integer` for all four. The `ail__is_intlike(n.tag)` check must handle index-like instances instead of rejecting them.
2. `round(u, None)` passes `None` to `__round__` instead of calling it with no arguments. Probe:
   ```python
   class U:
       def __round__(self, n): return ("n", n)
   def r(x, n=None):
       try: return repr(round(x, n))
       except Exception as e: return type(e).__name__ + ": " + str(e)
   u = U(); print(r(u, None)); print(r(u, 2)); print(r(u))
   ```
   Expected CPython: `TypeError: U.__round__() missing 1 required positional argument: 'n'`, `('n', 2)`, the same `TypeError`.
   Actual HEAD: `('n', None)`, `('n', 2)`, `('n', None)`. (Base also failed `round(u, None)` differently, returning `('n', 0)`; the new dunder patch still does not implement the no-argument call.)
[cost $0.0000, opencode tokens {"total": 1532168, "input": 77961, "output": 10073, "reasoning": 32934, "cache.write": 0, "cache.read": 1411200}]

FINAL VERDICT: FIX  2026-10-23T07:41:35Z
