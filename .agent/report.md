# job job-algo1-11071446  started 2026-11-07T05:46:58Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented `ail check --perf` with three committed steps on branch `job-algo1-11071446` (no push).

**What landed**
- `packaging/ail_lang/perflint.py`: AST rules P1–P6, text + `--json` output, `--strict` exit 5, exit 0 otherwise.
- `packaging/ail_lang/cli.py`: `ail check --perf` entry only.
- `docs/CLI.md`: new documented heading and rule table.
- `AIL_CURRENT/test_ail_perflint.py` + `tests.d` registration: 17 tests.
- `lab/algo/`: census script, before/after cases, and `RESULTS.md`.

**Census (final, hand-checked)**
- `lab/compare` 10 programs: 0 hits.
- Required 50 corpus programs: 1 hit (P3 in `g00_006.py`).
- All 510 `corpus/gdev`: 2 hits (P3 + P1); all 219 `lab/corpus`: 0; `lab/vibe` 24 `.py`: 0.
- Final false positives in required sets: 0. Hand-checking removed four FP shapes before the census (DP P5 comparisons, loop-variable P4, set/dict P1 evidence).

**Applied fixes**
| rule | before | after | speed-up | output identical |
|---|---:|---:|---:|---|
| P1 | 1.501s | 0.020s | 74.2x | yes |
| P2 | 1.703s | 0.029s | 59.2x | yes |
| P3 | 1.997s | 0.049s | 40.5x | yes |
| P4 | 1.099s | 0.017s | 63.1x | yes |
| P5 | 1.199s | 0.021s | 58.4x | yes |
| P6 | 6.441s | 0.020s | 317.3x | yes |

**Verification**
- Probes `/tmp/probes/{p1..p6,negative}.py`: perflint found the expected positives and no negatives; every probe matched CPython stdout/exit on both the general and default builds (`cmp.sh`).
- Final commit tests: `test_ail_perflint`, `test_ail_rundiff`, `test_ail_cli_args`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- `tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 6317141, "input": 154630, "output": 27032, "reasoning": 44087, "cache.write": 0, "cache.read": 6091392}]
    tool time: bash 14.7 min, write 0.0 min, read 0.0 min
        362s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_perflint test_ail_rundiff test_
        247s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_perflint test_ail_rundiff test_
        118s bash   cd /home/runner/work/ail-ci/ail-ci && cat > lab/algo/census.py <<'PY' """Lint the comparison, corpus and vibe 
         58s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/algo/measure.py --runs 3 > /tmp/algo_measure.md && python3 l
         57s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path repls = {  'p1_before.py': [('
         20s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('packaging/ail_lang/per
          7s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import time def run(LIMIT):     global text     text=''
          3s bash   cat > /tmp/probes/p4.py <<'PY' def main():     xs = [3, 1, 2]     total = 0     for _ in range(2):         ord

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds a new static Python-AST linter `packaging/ail_lang/perflint.py` with rules P1–P6 (text/JSON, `--strict` exit 5) and an `ail check --perf` dispatch in `cli.py`; it does not change the compiler or runtime. This matches the report.

**Verified**
- `test_ail_perflint` passes (17 tests, 0.9s); `test_ail_cli_args` + `test_ail_safetynet` pass (2 modules, 0 failed). Registration file and manifest are consistent (`update_manifest.py --check` exit 0).
- Census reproduces exactly: compare 10 = 0 hits; required 50 = 1 (P3 `g00_006`); all gdev = 2; lab/corpus 219 = 0; vibe 24 = 0.
- `lab/algo/measure.py`: every before/after pair prints identical stdout, the hit disappears, speedups match the table (foreground runs 1).
- A non-feature program compiled in the base worktree and HEAD produces byte-identical `program.c` (sha256 equal; both executables print 45); `native_report.json` differs only in temp/debug paths.
- The claim "Final false positives in required sets: 0" is **false** (defect 1).

**Defects**

1. **P3 does not check whether the string is rebound in the loop.** `/tmp/rprobes/p3_reset.py`:
   ```python
   for i in range(5):
       s = ""
       s += str(i)
       print(s)
   ```
   Expected: no P3 hit (the string is reset each iteration; nothing grows, no O(n²)). Actual: `P3 ... line 4 ... copies the whole string (O(n^2))` with a join-after-loop fix that would drop the reset. `/tmp/rprobes/p3_loopvar.py` (`for s in [...]: s += "!"`) is also flagged. This is exactly the required-corpus hit `corpus/gdev/g00_006.py:14:13` (`count_digits` is reset at line 19), so the hand-checked "true positive" is a false positive and the suggested fix would change output. Fix: apply `_loop_touches(loop, name, ignore=node)` to P3 as P4 already does for `sort`.

2. **P6 has the same problem for lists.** `/tmp/rprobes/p6_reset2.py`:
   ```python
   for i in range(5):
       L: list[int] = []
       L = L + [i]
   ```
   Expected: no P6 hit (the list is recreated, length ≤ 1). Actual: P6 claims O(n²). `/tmp/rprobes/p6_loopvar.py` (`for values in [[1], [2]]: values = values + [3]`) is also flagged, violating the task's "loop-variant list" negative requirement. Add the same loop-touch suppression for P6.

3. **P4 hoists sorts whose `key` changes with the loop variable.** `/tmp/rprobes/p4_keyvar.py`:
   ```python
   for k in range(2):
       print(sorted(rows, key=lambda row: row[k]))
       print(min(rows, key=lambda row: row[k]))
   ```
   Expected: no "hoist it out of the loop" hit (or a key-aware fix). Actual: two P4 hits. Hoisting changes output because `k` changes each iteration. P4 must inspect the `key`/`reverse` keywords for loop-variable dependencies, or stay silent.

**Pre-existing:** none found (the only base-vs-HEAD diff in `--debug-dir` output is temp paths).
**Unverified:** the worker's exact `/tmp/probes` cmp.sh runs (their files exist but I did not re-run both builds); `test_ail_rundiff`, `test_ail_files`, `test_ail_corpus_findings3` (outside reviewer scope).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1514451, "input": 91484, "output": 6440, "reasoning": 35791, "cache.write": 0, "cache.read": 1380736}]
    tool time: bash 2.8 min
        129s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         31s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 400 python3 lab/algo/measure.py --runs 1 2>&1 | tail -15
          2s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_
          2s bash   cd /tmp/rprobes && rm -rf /tmp/dbg_head /tmp/dbg_base && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 lab/algo/census.py 2>&1 | tail -40
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work >/tmp/wt.log 2>&1; echo wt=$?; tail -2 /
          0s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > alias_mut.py <<'PY' def main() -> None:     xs: list[int] = 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/*.py; do echo "=== $(basename $f)"; PYTHONPATH=pac

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three defects and committed as `4d6c5b1`.

- P3/P6: suppress hits when the name is reset in the loop or is the loop target, while sibling accumulating assignments still count.
- P4: inspect `key`/`reverse` for loop-dependent names and stay silent; constant keys still report.
- Updated `docs/CLI.md`, `lab/algo/RESULTS.md`, DEVLOG, manifest, and added regression tests (21 total).

Verification:
- Census: compare 10 = 0, required 50 = 0, all gdev = 1 (true P1 `g15_022`), lab/corpus 219 = 0, vibe 24 = 0.
- `measure.py`: all six before/after outputs identical, every fix removes its hit.
- Probes in `/tmp/probes`: all 17 matched CPython on both builds; `p4_reversevar` was refused by name (`reverse=` must be literal). Reviewer probes `p3_reset`, `p6_reset`, `p6_loopvar`, `p4_keyvar` now print nothing.
- Required modules on final commit: `test_ail_perflint`, `test_ail_cli_args`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed.
[cost $0.0000, opencode tokens {"total": 1926005, "input": 75057, "output": 10695, "reasoning": 12029, "cache.write": 0, "cache.read": 1828224}]
    tool time: bash 9.6 min, edit 0.0 min, read 0.0 min
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         54s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/*.py; do echo "=== $(basename "$f")"; bash ~/tools/
         28s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 400 python3 lab/algo/measure.py --runs 1 2>&1 | tail -12
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m py_compile packaging/ail_lang/perflint.py && python3 tools/up
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/algo/census.py 2>&1 | sed -n '1,60p'
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest -v test_ail_perflint 2>&1 | 
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest -v test_ail_perflint 2>&1 | 

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough. Final verification of the remaining claims is done; here is my review.

**What the change really does.** Adds a new AST linter `packaging/ail_lang/perflint.py` (six rules P1–P6 over loop bodies, text/JSON output, `--strict` exit 5), wires `ail check --perf` into `packaging/ail_lang/cli.py`, and adds docs, tests/registration, manifest rows, and `lab/algo/` census+measure scripts. No compiler or runtime code is touched: `program.c` from `--debug-dir` is byte-identical between `work` and HEAD (only transient temp/cwd paths in `native_report.json` differ), and `cmp.sh` on a plain program matches CPython on both builds.

**Claims.** Census re-ran and matches exactly (compare 0/10, required 50 0/50, gdev 1/510 at `g15_022.py:84`, lab/corpus 219→0, vibe 24→0). `measure.py --runs 1` reproduces the table (all six "output identical", every after-hit `-`). Targeted tests on HEAD: `test_ail_perflint`, `test_ail_cli_args`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass, 0 failed. P3/P6 reset and P4 key behaviour verified by probes (`p3_reset`, `p6_reset`, `p6_loopvar`, `p4_keyvar` silent; sibling `+=` and constant keys still report). Error path verified (syntax/NUL source → exit 2, no hits).

**Defects.**

1. **`.split()` types its receiver as a list — false P1 on a string, and the published fix changes output.** `_collect_call` does `elif func.attr in LIST_METHODS: self._hint(name, "list")`, but `split` is a *str* method; the receiver is a str. Probe `/tmp/rprobes/r_split.py`:
```python
def scan(text):
    for _ in range(3):
        fields = text.split(",")
        if "b,c" in text:
            print("yes", fields)
scan("a,b,c")
```
Actual: `r_split.py:4:12: perf P1: membership test on the list 'text' ... fix: build a set/dict once ...`. Expected: nothing (`text` is a str). Applying the JSON `fix` (`in set(text)`) changes the program from 3 `yes` lines to none (verified). This is the "value through an argument / types" boundary the docs say is handled.

2. **Aliasing is not treated as loop mutation; P1/P4 advice changes output.** `for i in range(3): data.append(i); total += sum(xs)` with `data = xs` reports P4 on `sum(xs)`; hoisting takes the result from 7 to 3 (`/tmp/rprobes/r_alias.py`). Likewise `view = items; view.append(probe); if probe in items` reports P1 and the set-before-loop fix takes output from `1 2` to nothing. Expected: silent, since the named list is mutated (docs: "a name that is rebound or mutated in the loop ... not reported").

3. **P3 misses the annotated/literal string target when the RHS type is unknown (dead branch).** In `_augment_kind`, `current = self.kinds.get(name)` is always `None` because `_classify` returns early when the name is in `self.kinds`; so `s: str` / `s = ""` + `s += <unknown>` is discarded as "other". Probe `/tmp/rprobes/r_p3shape.py`: `def f(items): s = ""; for x in items: s += x` and `def k(items): s = "start"; ...` produce **no hit**, while `def h(items: list[str])` reports at line 18. Expected: P3 (the target is provably a string, so any `+=` that runs is a string concat; docs promise annotation/literal evidence). This is a false negative, not wrong advice.

**Pre-existing.** None: `perflint.py` and the `--perf` branch are new in this change; no compile-time difference exists on the base.

**Unverified.** The worker's `/tmp/probes` claim (17 compile probes) — not rerun; immaterial since no compiler code changed and my own `--debug-dir` diff is identical. Wall-clock numbers in `RESULTS.md` are environment-dependent (I reran only `--runs 1`, output equality confirmed).

VERDICT: FIX

1. Probe /tmp/rprobes/r_split.py — expected: no hit (text is a str); actual: `4:12: perf P1: membership test on the list 'text'`; applying the fix changes output from three `yes` lines to none.
2. Probes /tmp/rprobes/r_alias.py (and r_alias_p1_orig/fixed) — expected: no P4/P1 hit when the list is mutated through an alias; actual: hits whose fixes change output (7→3, `1 2`→empty).
3. Probe /tmp/rprobes/r_p3shape.py — expected: P3 for `s = ""`/`s: str` + `s += unknown`; actual: no hit (only the `list[str]` case at line 18 reports).
[commandcode stop=end_turn turns=35 out_tokens=45550]

FINAL VERDICT: FIX  2026-11-07T07:09:18Z
