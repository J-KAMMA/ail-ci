# job job-hybex1-11041922  started 2026-11-04T10:23:28Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The review body was empty ("review 1 skipped"), so I audited every task requirement against the current code and ran the probes myself.

## What I checked (all pass)

**Builds** — all 6 examples build with `build --cpython`; 4 hot functions are accelerated, 2 are not (matching the README):
- accelerated: `collatz.longest`, `mandel_rows.mandel_checksum`, `prime_count.prime_count`, `fallback_demo.triple`
- not: `checksum_text.rolling_hash` (rejected: `a call can raise or have side effects`), `sum_squares_list.sum_squares` (no unit, empty `rejected`)

**CPython equality** — stdout + exit status match for the test args and 34 boundary probes (0, 1, 2, 3, negatives, empty, odd/even, 10 000 000/10 000 001). `collatz` with `9223372036854775809` and `18446744073709551616` matches through the int64 boundary fallback (`482` steps).

**README findings** — each minimal program reproduces its stated result: `%` variable divisor refused; `ord` refused; `list[float]` emits no unit while `list[int]` is accelerated (verified side by side); direct float call demotes the module; `2 ** 63 + 1` literal stops unit emission.

**Timings** (median of 3, default args): collatz 1384→67 ms (20.6×), mandel 685→26 ms (26.5×), prime 897→42 ms (21.4×), checksum 14.2→16.5 ms (0.9×), sum_squares 130→125 ms (1.0×), fallback 12.0→23.6 ms (0.5×). Three are ≥2×, matching the filled table.

**Default path** — 5/6 compile and match at default args; `fallback_demo` stops loudly at compile time on the out-of-int64 literal, and `collatz` stops loudly on `2**63+1` in both the default and `AIL_UNIFIED_FORCE=1` builds — allowed, since the value cannot be carried in int64. No silent difference.

**Tests** — `test_ail_examples_hybrid` 12.0 s ok, `test_ail_safetynet` 132.2 s ok, plus `test_ail_files` ok and `test_ail_corpus_findings3` ok. `update_manifest.py --check` and `ci_shards.py --check` exit 0; the new module lands in shard 0.

## Fix applied

The only spec gap was that two acceleration rule bullets had no one-line example. I added verified examples for the top-level/method and `is`/int64 rules (`class` method and `return a is b` emit no unit; `return n * n` is accelerated via the overflow wrapper) and committed as `045f689`.

I did not push (the run instructions explicitly forbid it), so the 20 shard checks were not run.
[commandcode stop=end_turn turns=40 out_tokens=34497]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: hybex1 fix commit

**What the change does:** README-only, +6/−3 in `examples/hybrid/README.md`. It adds one-line examples to the two acceleration-rule bullets that lacked them (top-level vs method; `is` and int64/overflow). No compiler, runtime, example program or test changed (`git diff --stat work..HEAD` = README only), so generated C is trivially unchanged and base comparison is moot.

**Probes (`/tmp/rprobes/`, hybrid `build --cpython`, checked against `python3`)**

| probe | claim tested | result |
| --- | --- | --- |
| `toplevel.py` | module-level fn is candidate, nested is not | `accelerated:['f']`, matches |
| `classmethod.py`, `classplus.py` | class method not a candidate; class doesn't demote top-level fn | `[]`; `['f']`, matches |
| `isonly.py` / `eqonly.py` | `return a is b` keeps fn in CPython | `[]` / `['g']`, matches |
| `square.py` @ 3, ±2³², 2⁶³−1 | `n*n` safe via overflow fallback | `['f']`, matches CPython incl. `18446744073709551616²` |
| `bigliteral.py` | module-level `2**63+1` emits no unit | `[]`, matches |

All new bullet examples are true. Minor observation (not a false claim): an `is` comparison demotes **all** units in the module, not only the function — `iseq.py` gave `[]` for both functions. Wording still literally holds.

**Test runs (HEAD):** `test_ail_examples_hybrid` ok 12.4s, `test_ail_safetynet` ok 133.5s (0 failed, `-j 2`). Manifest check rc=0; module registered in `tests.d`.

**Report claims:** build/4-accelerated/2-not — verified by the test's README-row assertions; collatz big-int (482 steps) — verified; default path 5/6 match, `fallback_demo` loud compile-time stop and `collatz` loud runtime stop on 2⁶³+1 — verified with `cmp.sh` and both builds; timing direction verified (measured collatz 1375.6→64.5 ms, 21.3×), though the README table's 1500→79 differs numerically from the report's 1384→67.

**Pre-existing:** none observed.

**Unverified:** the worker's other 34 boundary probes and the `%`/`ord`/`list[float]`/direct-float finding details (present in the base README, outside this diff); timings for the other five examples.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=21 out_tokens=12926]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T11:58:03Z
