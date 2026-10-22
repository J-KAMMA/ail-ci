# job job-cov6-10221632  started 2026-10-22T07:32:28Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `56f9090` on `job-cov6-10221632`.

Fixed all 5 findings:
- `urlencode` now expands list/tuple values with `doseq` for pair sequences.
- `urlsplit`/`urlparse` validate bracketed netlocs, including IPv6, IPvFuture, and bracketed IPv4 errors.
- `IPv4Address.is_private` uses `192.0.0.0/24` plus `.9`/`.10` exceptions; `is_global` now marks multicast global.
- `IPv4Address` rejects `/` before octet parsing.
- `IPv4Address.__hash__` hashes `hex(value)`; removed the runtime re-hash that affected any class with `__int__`, with `IntEnum.__hash__` adjusted accordingly.

Probes (`bash ~/tools/cmp.sh ...`), all `same stdout` on both builds:
- `probe_doseq.py`
- `probe_url_brackets.py`
- `probe_ip_fixes2.py`
- `probe_hash_props.py`

Tests on final content:
- `test_ail_stdlib6`: 4 passed
- `test_ail_fuzz1.HashValues`: 5 passed
- `test_ail_stdlib5.CompiledPrograms`: 2 passed
- `test_ail_safetynet`: 5 passed
- `test_ail_files`: 18 passed, 1 skipped
- `test_ail_corpus_findings3`: 2 passed
- `update_manifest.py --check`: exit 0
[cost $0.0000, opencode tokens {"total": 5519712, "input": 511350, "output": 18184, "reasoning": 18402, "cache.write": 0, "cache.read": 4971776}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `56f9090`; probes in `/tmp/rprobes`, base in `/tmp/base`.

**Verified**
- #1 `urlencode` doseq over pairs: `probe_urlencode.py` matches CPython on both builds; base shows the old `a=%5B...` output.
- #2 bracketed netloc: `probe_urlbracket.py` matches (IPv6, IPvFuture, bracketed IPv4, misplaced brackets, `urlparse`); base accepts them. A 100k random-netloc comparison of the new check against CPython had 0 mismatches.
- #3 `is_private`/`is_global`: `probe_ipfix.py` flags match; a 200k-address comparison against CPython had 0 mismatches.
- #4 `/` rejection: `probe_ipfix.py` messages match CPython (`Unexpected '/' in ...`); base differs.
- #5 IPv4 hash property: `probe_ipfix.py` gives `(hash(A)==hash(hex(int(A))), hash(A)==hash(int(A))) == (True, False)`; base gives `(False, True)`.
- `IntEnum` and user `__hash__`/`__int__` cases match (`probe_enumbig.py`, `probe_hashclass.py`). `update_manifest.py --check` exits 0.
- Tests: `test_ail_stdlib6`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5`, `test_ail_fuzz1.HashValues` all pass.
- No speed check needed: the only runtime change removes a branch, and no gdev hot path hashes these types.

**Pre-existing**
- AIL's absolute `str`/`bytes` hashes differ from CPython on both base and HEAD (AIL uses a fixed FNV-style hash, CPython uses salted SipHash); only equality relations are meaningful.
- `10**30` still fails with `integer overflow` on both base and HEAD (`probe_bignum.py`).
- Full `test_ail_fuzz1` cannot run its `Generator` tests because `tools/difffuzz.py` is absent in both trees; `HashValues` alone passes.

VERDICT: FIX

1. `Fraction.__hash__` regressed for large integral numerators. Probe `/tmp/rprobes/probe_fracbase.py` (`from fractions import Fraction`; loop over `n` calling `hash(Fraction(n, 1))`): CPython and base print `frac 2305843009213693952 1 1 True` and `frac 2305843009213693951 0 0 True`; HEAD on both builds prints `frac 2305843009213693952 2305843009213693952 1 False` and `frac 2305843009213693951 2305843009213693951 0 False`. Cause: `prelude_fraction.py:260-263` returns the raw numerator for `denominator == 1`, and removing the `ail_dun1(x, AIL_D1_INT)` rehash in `dunderrt.py:354` no longer canonicalises it; `IntEnum` was adjusted but `Fraction` was not.
[cost $0.0000, opencode tokens {"total": 2819991, "input": 137332, "output": 11340, "reasoning": 25431, "cache.write": 0, "cache.read": 2645888}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `f1e0fd0` on `job-cov6-10221632`.

**Fix**
- `prelude_fraction.py`: integral `Fraction` now hashes via `hash(numerator)`, so it matches the equal `int` again (`Fraction(2**61, 1)` → `1`, `Fraction(2**61 - 1, 1)` → `0`, `-1` → `-2`).
- Added the integral hash cases to `test_ail_stdlib5` (compiled `f1` and direct prelude test); updated DEVLOG and MANIFEST.

**Probes (both builds)**
- `/tmp/probes/probe_fractionhash.py`: same stdout as CPython on `g` and `d`; covers `0`, negatives, `2**61±`, `2**63-1`, normalized values, argument/list/attribute/dict/set paths.
- `/tmp/rprobes/probe_fracbase.py`: the flagged integral lines now match CPython on both builds; only the pre-existing non-integral `half` hash difference remains, unchanged from base.
- `update_manifest.py --check`: OK.

**Tests on final commit**
- `test_ail_stdlib5`: 10 passed
- `test_ail_safetynet`: 5 passed
- `test_ail_files`: 18 passed, 1 skipped
- `test_ail_corpus_findings3`: 2 passed
[cost $0.0000, opencode tokens {"total": 975679, "input": 105138, "output": 6884, "reasoning": 4457, "cache.write": 0, "cache.read": 859200}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (`f1e0fd0`, `56f9090`) against `/tmp/base`; probes in `/tmp/rprobes`.

**Verified claims**
- Integral `Fraction` now hashes via `hash(numerator)`: `probe_frac2.py` / `probe_fractionhash.py` match CPython on both builds (`0,1,5,-1,-5,2**61-1,2**61,2**61+1,2**62,2**63-1`, negatives, normalized, arg/dict/set paths).
- Tests/DEVLOG/MANIFEST updated; `update_manifest.py --check` exits 0. `probe_fracbase.py` integral lines now match; only the known `half` difference remains.
- Test results reproduced: `test_ail_stdlib5`, `test_ail_stdlib6`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass with `-j 2`; `test_ail_fuzz1.HashValues` 5/5; `test_ail_cov2` (IntFlag hash) passes.
- Re-probed the five earlier fixes: `urlencode([("a",["1","2"]),("b","3")],doseq=True)` → `a=1&a=2&b=3`; bracketed netloc errors match (`Invalid IPv6 URL`, `'abc' does not appear...`, bracketed IPv4); `192.0.0.8` → `(True,False)`, `224.0.0.1` → `(False,True)`, `1.2.3.4/24` → `Unexpected '/' in '1.2.3.4/24'`; IPv4 hash equals `hash(hex(int))` and not `hash(int)`. Random fuzz: 150k bracketed hosts and 200k IPv4 addresses vs CPython, 0 mismatches.
- Non-feature program: both builds same stdout; generated C differs only by the intentionally removed rehash line.

**Pre-existing**
- Non-integral `Fraction(1,2)` hash differs on both base and HEAD (`1000005` vs CPython `1152921504606846976`). Large non-integral values changed value when the rehash was removed, but remain the known approximation; equal-fraction hashes stay consistent.
- Absolute `str`/`bytes` hashes are process-independent but not CPython's salted hashes.
- `doseq` still does not expand set/range values (same on base).

Speed: `perf_event_open` is denied in this runner, so no instruction counts; the only runtime change removes a branch, so no hot-path slowdown is plausible.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2377451, "input": 97510, "output": 10923, "reasoning": 22746, "cache.write": 0, "cache.read": 2246272}]

FINAL VERDICT: ACCEPT  2026-10-22T08:40:36Z
