# job job-pyproof1-11051132  started 2026-11-05T02:34:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `0aa7d3c` on `job-pyproof1-11051132` (not pushed, per runner instructions).

- Census: **54 programs** — **typed 24 / 54, general 16, refused 14, wrong 0**; geomean speed-up **6.19x**.
- Top buckets with verified reproducers: `import of 'X' is not available` (6), int64 literal/constant overflow (3), field list/dict mixing bools and numbers (1).
- Added `lab/pyproof/{programs.txt,report.py,results.jsonl,RESULTS.md,README.md,repro/*.py}` and the test module + `tests.d` registration; manifest updated and `--check` passes.
- Passing tests: `test_ail_pyproof_report`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- CI shards were not run because pushing is forbidden in this environment.
[cost $0.0000, opencode tokens {"total": 4329394, "input": 201266, "output": 18740, "reasoning": 19148, "cache.write": 0, "cache.read": 4090240}]
    tool time: bash 32.9 min, write 0.0 min, edit 0.0 min
        712s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/pyproof/report.py -j 2 > /tmp/pyproof-run.log 2>&1; ech
        711s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/pyproof/report.py -j 2 > /tmp/pyproof-run2.log 2>&1; ec
        531s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/manifest.d/9a.txt AIL_CURRENT/manifest.d/f7.txt && f
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import re p='lab/pyproof/report.py' s=open(p).read() s
          3s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 AIL_CURRENT/test_ail_pyproof_report.py -v 2>&1 | tail -30
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='AIL_CURRENT/test_ail_pyproof_report.py' s=open(p).r
          3s bash   cd /tmp/probe1 && for f in general refused; do echo "=== $f default"; python3 -B /home/runner/work/ail-ci/ail-
          3s bash   cd /tmp && rm -rf probe1 && mkdir probe1 && cd probe1 && printf 'print("hi")\n' > typed.py && printf 'def f(x)

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `0aa7d3c` (`work..HEAD`). The change adds a `lab/pyproof` census (runner, fixed list, `results.jsonl`, `RESULTS.md`, README, 3 repros), a test module, and manifest entries. No compiler/runtime file is touched, so there is no C delta or regression path to probe.

**Verified**
- `results.jsonl` has 54 rows in `programs.txt` order: **typed 24 / 54, general 16, refused 14, wrong 0**; geomean recomputes to **6.1886 → 6.19x**.
- `par_check.py -j 2 test_ail_pyproof_report test_ail_safetynet`: 2/2 ok (199 s). `tools/update_manifest.py --check`: rc 0.
- All three reproducers were run with `~/tools/cmp.sh`: the import and int64 ones refuse on both builds with the bucket text; the field one is a general fallback with the same `note:` on the default build and refuses under `--strict`.
- Fresh `report.py --only lab/pyperf/bench/generators.py --out /tmp/rprobes/ppout` reproduces `general` with `strict_reason: why not typed: this language has no generators.`

**Pre-existing:** none observed (no source behaviour changed).

**Unverified:** the 20 CI shards (not pushed), `test_ail_files`/`test_ail_corpus_findings3` (outside the requested set), the full ~12 min census rerun and the `scar_life` 240 s timeout, and base-vs-HEAD C comparison (diff has no compiler/runtime files).

VERDICT: FIX
1. **Blocker buckets omit every general fallback, so the ranking is wrong.** `report.py:359` filters `result != 'refused'`, but the task asks for blockers that would move programs to typed, and step 3 explicitly allows a reproducer for a "refusal or fallback". Recomputing with the runner's own `normalise` over the 16 general `first_reason`s gives: `import of 'X' is not available` **6**, read-only list parameter **3** (nqueens, scimark_fft, spectral_norm), int64 overflow **3**, constant None **2** (richards, csv_rollup). Actual `RESULTS.md`: import **6**, int64 **3**, then the 1-program `a field list or dict gets bools and numbers` bucket. Expected top three: import 6, list-parameter 3, int64 3 (None 2 next); actual third is a 1-program bucket, and the list-parameter and None blockers are absent.
2. **`strict_path` is wrong for all 16 general rows.** `report.py:215-216` overwrites the strict failure with the default path. Fresh run on `lab/pyperf/bench/generators.py`: `strict_reason` says `why not typed: this language has no generators.` but `strict_path` is `general`; expected `refused` (strict is typed or refusal).
3. **The program list is incomplete.** `lab/pyperf/run.py:302` has a `__main__` path, is not a test module/`typed.py`/`.ail`, and is under `lab/pyperf/`, so it meets the stated inclusion rule; it is absent from `programs.txt` and not listed in the README exclusions. Expected 55 rows (or a documented exclusion); actual 54.
4. **`repro/an-integer-literal-or-constant-expression-overflows-int64.py` is 2 lines** (`wc -l`), below the required 3-15 lines.
[cost $0.0000, opencode tokens {"total": 1825648, "input": 114998, "output": 5660, "reasoning": 37150, "cache.write": 0, "cache.read": 1667840}]
    tool time: bash 3.6 min
        201s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pyproof_report test_ail_safety
          7s bash   date; python3 lab/pyproof/report.py --only lab/pyperf/bench/generators.py --out /tmp/rprobes/ppout -j 1 >/tmp/
          4s bash   cd /tmp/rprobes; for f in *.py; do echo "################ $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-
          2s bash   cd /tmp && rm -rf fieldrepro && mkdir fieldrepro && cp /home/runner/work/ail-ci/ail-ci/lab/pyproof/repro/a-fie
          1s bash   cd /tmp/rprobes; for f in a-field-list-or-dict-gets-bools-and-numbers.py an-integer-literal-or-constant-expres
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -20; echo "rc=$?"
          0s bash   date; pwd; git status --short | head -50; echo ---; git log --oneline work..HEAD; echo ---; git diff --stat wo
          0s bash   python3 - <<'EOF' import json,importlib.util spec=importlib.util.spec_from_file_location('rep','lab/pyproof/re

## worker report 1
[model commandcode/deepseek-v4.1-flash]
All four reviewer defects are fixed and committed as `8ebe06c`.

What changed:
- **Buckets now include general fallbacks** (and strips the `built on the general path … because` prefix). Ranking is now `import of 'X' is not available` 6, `a list parameter is read-only` 3, int64 overflow 3, dict-of-containers 2, constant None 2 — matching the reviewer's recomputation. Reproducers exist for the top three (plus two extras).
- **`strict_path` no longer overwritten**: all 15 general rows now record `strict_path: refused`.
- **List completed**: added `lab/pyperf/run.py` (`argv:--help`); `programs.txt` and `results.jsonl` both have 55 rows in order.
- **int64 reproducer** is now 3 lines and still refuses with `int64 constant expression out of range` on both builds.

Verification:
- Final census: **typed 24 / 55, general 15, refused 16, wrong 0**, geomean **6.32x**.
- All 5 reproducers behave as their buckets say via `report.py` and `~/tools/cmp.sh` (refused/refused or refused/general with the same reason).
- `python3 AIL_CURRENT/test_ail_pyproof_report.py`: 4 tests OK on this commit.
- Required modules: `test_ail_pyproof_report`, `test_ail_files`, `test_ail_corpus_findings3` pass; `test_ail_safetynet` failed its `S4_generators_gc` only when wrapped in my `ulimit -v 1500000`, then passed 373 s without the cap (harness memory artifact; no compiler file touched).
- `tools/update_manifest.py --check` rc 0; diff is confined to `lab/pyproof/`, the test module, its `tests.d` registration, and the manifest fragment.

Note: `ticket_audit` is a genuine timeout, not a bucket — re-running it alone still hits the 120 s build limit on both builds, which is why general is 15 rather than the 16 in the older run. Both timeout programs are documented in the README.
[commandcode stop=end_turn turns=34 out_tokens=21541]

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All checks done. Here is my review.

**What the change really does (one line):** adds a lab-only census harness (`lab/pyproof/report.py`) with a fixed 55-program list, recorded `results.jsonl`, generated `RESULTS.md`, five reproducers, a unit test and manifest entries — it touches no compiler or runtime file.

**Claims checked**

| claim | verdict |
|---|---|
| Buckets include general fallbacks; ranking import 6, list 3, int64 3, dict 2, None 2 | verified mechanically (`bucket_counts` on the jsonl reproduces exactly) |
| all 15 general rows now record `strict_path: refused` | verified |
| `programs.txt` and `results.jsonl` both 55 rows, same order | verified |
| int64 reproducer is 3 lines and refuses on both builds | verified via `cmp.sh` |
| 5 reproducers show their bucket via `report.py` | verified (3 refused/general, 2 refused/refused, each maps to its bucket) |
| `test_ail_pyproof_report.py` 4 tests OK | verified |
| `test_ail_pyproof_report` + `test_ail_safetynet` pass | verified (`par_check -j 2`: both ok, 180 s) |
| manifest `--check` rc 0; diff confined | verified |
| typed 24/55, general 15, refused 16, wrong 0, geomean 6.32x | **counts/geomean match the file, but the data is wrong — see defect 1** |
| `ticket_audit` genuine timeout | unverified |

Nothing compiled can change: the diff contains no compiler/runtime file, so there is no "unused feature" C-output probe to run.

**Defects**

1. **Six crate rows are not refusals — the census dropped the lab's build step.** `report.py` copies only sibling `*.py` and never runs `ail_cargo.py build`, so the generated `*_ffi.py` and static library are absent. With the lab's own runner:
   - `examples/crate/rle/main.py`: default compile rc 0, **no** general-path note, AIL run rc 0, stdout == CPython. Census says `refused` / `import of 'rle_ffi' is not available`.
   - `examples/crate/textstat/main.py`: same (typed, matches). Census says `refused`.
   - `examples/crate/fnvhash/main.py`: compiles typed rc 0, but the default binary exits 1 with `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)` while CPython exits 0 and prints five exact big ints. Under the task's rule this is a **`wrong` row** (silent/loud difference) that must be reported at the top with a reproducer; with the lab's `--exact-int` it matches.
   Consequence: the #1 bucket (`import of 'X' is not available`, alone 6) is an artifact, the typed share is understated by at least 2 (24 → 26), `refused` is inflated, and the claimed `wrong 0` is false. Root cause: `census_one` never runs CPython for a refused row, so an oracle failure (missing generated module) is indistinguishable from a language refusal. The three `bench.py` rows import the same FFI and are likely affected too (I did not rebuild them individually).

2. **Base provenance is wrong.** `integ_sha()` silently falls back to `HEAD`; the recorded `0aa7d3c07be…` is the worker's own census commit, not `integ` (no `origin/integ`/`integ` ref exists; the real base is `work` = `803122d…`). `RESULTS.md` prints `Base: integ 0aa7d3c…`. The README discloses the fallback, but the generated report still mislabels the base.

**Pre-existing:** none (no compiler/runtime file changed, so no probe can differ on the base).

**Unverified:** `ticket_audit`/`scar_life` timeout claim; `test_ail_files` and `test_ail_corpus_findings3`; the three crate `bench.py` rows; a full 55-row re-run (I re-ran 4 rows plus the 3 crate mains); speed impact (no hot code touched).

VERDICT: FIX
1. Six crate rows misclassified. Probe (existing): `examples/crate/rle/main.py` and `examples/crate/textstat/main.py` — expected default compile rc 0 on the typed path and stdout == CPython (verified via `AIL_CURRENT/test_ail_examples_crate.py`); actual census `refused` / `import of 'rle_ffi' is not available`. Probe: `examples/crate/fnvhash/main.py` — expected `wrong` (typed build, AIL exits 1 `OverflowError: integer overflow in +` vs CPython exit 0 with exact values), or matching with `--exact-int`; actual `refused` with the import text. Fix: run `ail_cargo.py build` for the crate rows (and their `bench.py` input), and run CPython for every row so a missing artifact cannot masquerade as a refusal.
2. `RESULTS.md` reports `Base: integ 0aa7d3c…`, which is `HEAD`, not `integ` (actual base `work` = `803122d…`). Expected the base ref/sha; actual the worker's own commit.
[commandcode stop=end_turn turns=37 out_tokens=36276]

FINAL VERDICT: FIX  2026-11-05T04:48:11Z
