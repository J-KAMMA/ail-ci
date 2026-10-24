# job job-cov8-10240949  started 2026-10-24T00:49:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed on `job-cov8-10240949`.

**Census** (510 gdev programs, `fallback_census.py --jobs 2`, compile-only):
- Before: **145 typed / 311 general / 47 refused by both / 7 error**
- After: **149 typed / 307 general / 47 / 7**
- `Random.randrange must take plain positional arguments...` refusals: **10 → 0**. The larger classes are the deliberate `yield` (12) and scalar-`None` (10) gaps.

**Change**
- Added `prelude_random_typed.py` with `randrange1` / `randrange3`; `randlib.py` rewrites calls on a proven `Random` and drops the hidden generator when only `random.seed` is used.
- Added the same method names to the boxed prelude.
- `pyfunc.py` now refuses an unavailable method signature by name instead of raising `KeyError`.
- Added `test_ail_cov8.py`; adjusted `test_ail_stdlib5.py` to force the general path for its boxed-Random C check.

**Verification**
- All 10 target corpus programs: both builds exit 0 and match CPython (`cmp.sh`).
- Probes all match CPython on both builds: `rand_bounds`, `rand_attr`, `rand_dict`, `rand_field`, `rand_forms`, `rand_list`, `rand_mixed`, `rand_module`, `rand_seed_only`.
- Required tests on final commit: `test_ail_cov8`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_stdlib5`, `test_ail_refusal_messages`, `test_ail_genlib` — **7 modules, 0 failed**.
- `python3 tools/update_manifest.py --check` passes.

**Commits:** `3bcb897` (feature), `6068df8` (test fix). Working tree clean except the untracked `.agent/pipeline.md`.
[cost $0.0669, opencode tokens {"total": 5447151, "input": 209553, "output": 12638, "reasoning": 20480, "cache.write": 0, "cache.read": 5204480}]
    tool time: bash 23.1 min
        329s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov8 test_ail_sa
        324s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov8 test_ail_sa
        282s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/census/after2.jsonl && python3 /tmp/census/tool/fallback_cens
        184s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_stdlib5 > /tmp/census/stdlib
        120s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/census/after2.jsonl /tmp/census/after2.log && nohup python3 /
         64s bash   cd /home/runner/work/ail-ci/ail-ci && for n in g13_028 g12_012 g12_014 g12_018 g11_036 g24_012; do d=$(mktemp 
         45s bash   mkdir -p /tmp/census/cmp_after; cd /home/runner/work/ail-ci/ail-ci; for n in g03_004 g11_036 g12_012 g12_014 g
         27s bash   cd /home/runner/work/ail-ci/ail-ci && ls /tmp/probes/*.py | sed 's#.*/##;s#\.py$##' | xargs -P2 -I{} bash -c '

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change does (one line):** Adds `prelude_random_typed.py`, rewrites `r.randrange(...)` to `randrange1`/`randrange3` for names the analysis treats as Random, drops the hidden `_ail_rng` when only `random.seed` is used, and changes a typed-field-initializer `KeyError` into a named refusal.

The report overstates the proof: the rewrite's "proven Random" set ignores `for` / `with` / `except` / import bindings, and the seed-drop assumes `random.seed` appears only as a bare expression statement. Both assumptions are false and produce the defects below.

**Claims**
- Census typed 145 -> 149 and `randrange must take plain positional` 10 -> 0: **verified** from `/tmp/census`.
- 10 target gdev programs match on both builds: **verified** (ran all 10; all `same stdout`).
- 9 worker probes match CPython: **verified** (all 9 `same stdout` on g and d).
- 7 named test modules, 0 failed: **verified**. `update_manifest.py --check`: **verified**. DEVLOG/DIFFERENCES/clean tree: **verified**.
- General split 311 -> 307: not independently reproduced (my classification of the same jsonl differs); typed count is verified.
- No-feature C unchanged: **verified** (`g00_000` debug-dir C byte-identical to base).

**Defects (all caused by this change; base matches CPython)**

1. Unsound Random proof. A `for` target rebinds the name but the analysis only records `Assign` values, so it still calls it Random:
```python
import random
class Fake:
    def randrange(self, n: int) -> int:
        return 999
def main() -> None:
    r = random.Random(1)
    for r in [Fake()]:
        print(r.randrange(10))
main()
```
Expected `999`; actual both builds exit 1, `AttributeError: 'Fake' object has no attribute 'randrange1'`.

2. Starred argument counted as one positional:
```python
import random
r = random.Random(1)
print(r.randrange(*[1, 10]))
```
Expected `3`; actual both builds exit 1, `TypeError: Random.randrange1() takes 2 positional arguments but 3 were given`.

3. Width boundary on the new typed path (`getrandbits` caps at 62 bits):
```python
import random
r = random.Random(1)
print(r.randrange(2 ** 62))
```
Expected `582057716445789124`; actual default build exits 1, `RuntimeError: getrandbits: more than 62 bits needs integers beyond 64 bits` (general build still matches, base matches).

4. Seed-drop breaks non-statement uses of `random.seed`:
```python
import random
def main() -> None:
    r = random.Random(7)
    x = random.seed(7)
    print(x)
    print(r.randrange(10))
main()
```
Expected `None` / `5`; actual both builds fail to compile, `name '_ail_rng' is not defined`. Same with `if random.seed(7) is None:`.

**Pre-existing:** `gauss(mu)` / `expovariate()` without defaults fail on base as well (both builds refuse); not caused by this change.

**Unverified:** instruction-count comparison — `icount` cannot open a perf event in this container (`perf_event_open` fails); no runtime speed check.

VERDICT: FIX
[cost $0.0297, opencode tokens {"total": 1395822, "input": 81982, "output": 7537, "reasoning": 15039, "cache.write": 0, "cache.read": 1291264}]
    tool time: bash 8.6 min
        327s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov8 test_ail_sa
         45s bash   cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/rout_gdev; for n in g03_004 g11_036 g12_012 g12_016 g12_014 
         30s bash   cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/rout_head; ls /tmp/rprobes/*.py | sed 's#.*/##;s#\.py$##' | 
         25s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p13_loopshadow p14_seedassign p15_seedexpr; do bash ~/tools/cmp.s
         23s bash   cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/rout_workerprobes; ls /tmp/probes/rand_*.py | sed 's#.*/##;s
         22s bash   cat > /tmp/rprobes/p16_seedassign_r.py <<'EOF' import random   def main() -> None:     r = random.Random(7)   
         22s bash   cat > /tmp/rprobes/p18_star.py <<'EOF' import random   def main() -> None:     r = random.Random(1)     two = 
         14s bash   cd /tmp; cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/tools/ic

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `6cab728`.

**Fixes**
- Random proof now rejects names bound by `for` / `with` / `except` / import / comprehension / nested def-class / augmented assignment / walrus / `del` / global-nonlocal, and propagates enclosing scopes correctly.
- Starred `randrange(...)` calls are no longer renamed by source arity.
- 63-bit draws now work, so `randrange(2**62)` matches CPython; updated typed prelude, Python prelude and boxed C helper.
- Hidden generator is dropped only when every `random.seed` use is a bare statement; assignment/`if`/argument uses keep it.

**Verification**
- Census rerun: 510 programs, **149 typed / 307 general / 47 refused by both / 7 error**. Before this job: 145 / 311 / 47 / 7.
- Final export: 24 probes under `/tmp/probes/r*.py`, **48/48 build outputs matched CPython stdout** on both `g` and `d` (for/with/except shadows, star arities, seed expressions, 62/63-bit widths, arity/alias/list/attribute/dict/argument paths, empty/negative/keyword cases).
- Required tests on final commit: `test_ail_cov8`, `test_ail_stdlib5`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **6 modules, 0 failed**.
- `update_manifest.py --check`: passed. Import-binding proof is covered by the new `test_ail_cov8.Analysis` unit test (a program-level local-import probe is not modelled by the compiler).
[cost $0.0597, opencode tokens {"total": 5091600, "input": 120391, "output": 14432, "reasoning": 30313, "cache.write": 0, "cache.read": 4926464}]
    tool time: bash 23.3 min, read 0.0 min
        341s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_cov8 test_ail_stdlib5 test_ail_
        329s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_cov8 test_ail_stdlib5 test_ail_
        282s bash   diff -q /tmp/census/tool/fallback_census.py /home/runner/work/ail-ci/ail-ci/lab/census/fallback_census.py; cd 
        118s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r*.py; do n=$(basename $p .py); echo "=== $n"; bash
        118s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r*.py; do n=$(basename $p .py); echo "=== $n"; bash
        102s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r*.py; do n=$(basename $p .py); echo "=== $n"; bash
         44s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_cov8 -v 2>&1 | tail -n 80
         24s bash   cd /tmp/probes && cat > r05a_star2.py <<'EOF' import random   def main() -> None:     r = random.Random(1)    

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does.** It adds a typed-path `Random` prelude (`prelude_random_typed.py`), rewrites one-/three-argument `randrange` calls on names proven to hold a `Random`, drops the hidden module RNG when only bare `random.seed(...)` uses it, widens `getrandbits` to 63 bits, and guards two `pyfunc.py` name lookups.

**Verified**
- Census: base 510 = 145 typed / 311 general / 47 both-refused / 7 error; HEAD = 149 / 307 / 47 / 7. Matches the report.
- Targeted gdev programs using `Random` (g12_030, g11_036, g24_012, g03_038, g13_028) match CPython on both builds.
- Starred calls, 63-bit widths, 62-bit `randrange`, seed assignment/`if`/argument forms: probes match CPython.
- Non-feature programs (g00_000, g03_000, g07_010): `program.c` byte-identical to the base.
- Tests on HEAD: `test_ail_cov8`, `test_ail_stdlib5`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed. `update_manifest.py --check` passed.

**Defects**

1. **`random.seed(<expression>)` is dropped together with the expression's side effects.** The new `_SeedDrop` removes the whole bare statement, not just the seed call, so a user-visible side effect in the argument disappears. Both `g` and `d` are wrong; base matches CPython.
```python
import random
def val() -> int:
    print("side")
    return 7
def main() -> None:
    random.seed(val())
    r = random.Random(3)
    print(r.randrange(10))
main()
```
Expected: `side` then the draw (`side\n3`). Actual: `3` on both builds.

2. **The `Random` proof is not lambda-aware.** `_scope_nodes` walks lambda bodies as part of the enclosing scope, and `_scope_bindings` never marks lambda parameters as bound, so a lambda parameter shadowing a proven `Random` is still rewritten to `randrange1`.
```python
import random
class Fake:
    def randrange(self, n: int) -> int:
        return 999
def main() -> None:
    r = random.Random(1)
    f = lambda r: r.randrange(10)
    print(f(Fake()))
    print(r.randrange(10))
main()
```
Expected: `999\n2`. Actual: `AttributeError: 'Fake' object has no attribute 'randrange1'`, exit 1, on both builds. Base matches. (The report's "propagates enclosing scopes correctly" claim is therefore false for lambdas; the unit test covers only for/with/except/import.)

**Pre-existing:** none found for these probes.

**Unverified:** runtime/instruction-count impact (only AST/compile-time code changed; no hot runtime path), and the wider suite (not run by design).

VERDICT: FIX
[cost $0.0246, opencode tokens {"total": 1889716, "input": 43322, "output": 6245, "reasoning": 14869, "cache.write": 0, "cache.read": 1825280}]
    tool time: bash 17.3 min
        303s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov8 test_ail_st
        283s bash   cd /home/runner/work/ail-ci/ail-ci; PYTHONPATH=$PWD/AIL_CURRENT:$PWD/AIL_CURRENT/python/pkg-v12 python3 lab/ce
        282s bash   cd /tmp/base; PYTHONPATH=$PWD/AIL_CURRENT:$PWD/AIL_CURRENT/python/pkg-v12 python3 lab/census/fallback_census.p
         47s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/pstar1.py /tmp/rprobes/pstar3.py /tmp/rprobes/pattr.
         36s bash   cd /home/runner/work/ail-ci/ail-ci; for f in g12_030 g11_036 g24_012 g03_038 g13_028; do echo "##### $f"; bash
         36s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_genlib 2>&1 | ta
         10s bash   cd /home/runner/work/ail-ci/ail-ci; echo "=== HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/pside.py $PWD 2>&1 | tai
          9s bash   cd /tmp/rprobes cat > pside.py <<'EOF' import random  def val() -> int:     print("side")     return 7  def ma

FINAL VERDICT: FIX  2026-10-24T03:46:00Z
