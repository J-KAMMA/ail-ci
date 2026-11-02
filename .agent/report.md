# job job-prog16-11020904  started 2026-11-02T00:04:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

**Result**
- Profiled all 8 programs; wrote `lab/progfix/prog16.md` with hot functions (80% own time), typed status, first reason.
- Fixed 2 compiler gaps (no program edits):
  - `pyfunc`: pair-name comprehension targets over `enumerate` (unblocks `t268`).
  - `modtables`: unary `-`/`+` float literals, including `-0.0`, in module tuple tables (unblocks `g25_038`).
- Typed now: `t268`, `t068`, `t003`, `g09_028`, `g25_038` (5/8). Follow-ups with exact messages recorded for `g21_034`, `g20_038`, `g14_040`.
- Added `AIL_CURRENT/test_ail_prog16.py`, registered via `tests.d/test_ail_prog16.txt`.

**Verification**
- `lab/compare` generated C vs `HEAD`: all 10 `main.ail` **SAME**; all 5 `main.py` builds that build at all **SAME**; the other 5 fail identically on both trees.
- 7 probes (`/tmp/probes/prog16_*.py`) all match CPython on general and default builds; typed refusals for `enumerate(start=...)` and `list[float]` checked by the test module.
- Tests: `test_ail_prog16`, `test_ail_modconst`, `test_ail_str_comprehension_move`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **9 modules, 0 failed**.
- `update_manifest.py --check` clean.

**Commit:** `9f965d0` (not pushed).
[cost $0.0164, opencode tokens {"total": 1016057, "input": 47114, "output": 5426, "reasoning": 5309, "cache.write": 0, "cache.read": 958208}]
    tool time: bash 26.4 min
        558s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog16 test_ail_modconst test_a
        332s bash   cat > /tmp/ccompare.sh <<'EOF' #!/bin/bash set -u CUR=/home/runner/work/ail-ci/ail-ci HEAD=/tmp/headprog16 TAS
        323s bash   cat > /tmp/ccompare.sh <<'EOF' #!/bin/bash set -u CUR=/home/runner/work/ail-ci/ail-ci HEAD=/tmp/headprog16 TAS
        320s bash   cd /tmp && cat /tmp/ctasks.txt | xargs -P 2 -n 2 /tmp/ccompare.sh 2>&1 | tee /tmp/ccompresult.txt | sort
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/prog16_*.py; do echo "######## $(basename $p)"; bas
         20s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 1 test_ail_prog16 2>&1 | tail -60
          4s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/headprog16 && mkdir -p /tmp/headprog16 && git archive HEAD |
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_prog16.py AIL_CURRENT/tests.d/test_ail_prog

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does.** `pyfunc._listcomp_kind`/`_listcomp_into_temp` now accept a two-name target over `enumerate(...)` and lower it through the existing `_pair_plan`; `modtables._scalar` now accepts unary `-`/`+` on float literals. No program files or runtime code changed.

**Claims checked**
- `prog16.md` exists with the 8-program table; target programs `t268`/`g25_038` were refused on base and compile typed on HEAD; `t068`/`t003`/`g09_028` were typed on base and stay typed. Verified.
- `g21_034`, `g20_038`, `g14_040` still refused typed, on the same feature gaps. Verified (exact first-message wording not re-derived).
- New test module registered via `tests.d`; `update_manifest.py --check` clean. Verified.
- `test_ail_prog16`, `test_ail_modcount`, `test_ail_safetynet` pass on HEAD (`3 modules, 0 failed`).
- Pair/negative-float behaviour matches CPython on both builds through arguments, list items, attributes, slices (negative bounds), `range` with non-zero start, `sorted`, nested comprehensions, `-0.0` sign, and dict/table values. Verified with own probes.
- Non-feature program's `program.c` is identical to base; no compare-task source contains either new construct, so the 10-task C claim is consistent (I did not recompile all ten).

**Probes run** (`/tmp/rprobes/`): `pair_basic`, `pair_forms`, `pair_edge`, `pair_slice_mut`, `pair_subscript`, `pair_negslices`, `pair_sorted`, `pair_nestedcomp`, `pair_contexts`, `pair_float`, `pair_str`, `pair_struct`, `pair_blist`, `pair_dictkeys`, `pair_dictvalue`, `pair_listitem`, `pair_reverse`, `pair_reversed`, `pair_set*`, `negtable`, `negtable_edge`, `table_dict_negfloat`, `table_negfloat`, `pair_enumerate_empty`, `nonfeature`. All matched CPython or were refused by name, except the defect below.

**Pre-existing (does not block)**
- Pair comprehension over a local `set[int]` uses insertion order in the typed build: `[v for i,v in enumerate({8,1,9,16,17,2,24,25})]` differs from CPython. Base general/default show the identical wrong order (documented set-order difference); base typed refused.
- `enumerate((4,5,6))` is refused with a different message than base but still a named refusal.

**Unverified**
- Full 10-task `lab/compare` byte comparison and the worker's other 6 test modules (not re-run; targeted modules only).
- Speed: change is compile-time only, no runtime hot-code probe run.

**Defect**

VERDICT: FIX
1. Zero-argument `enumerate()` in a pair-target comprehension crashes the compiler instead of refusing by name, on both general and default builds. `_listcomp_kind` does `g.iter.args[0]` without checking arity (`AIL_CURRENT/python/pkg-v12/pyfunc.py:19122`).
   Probe:
   ```python
   def f() -> list[int]:
       return [i for i, v in enumerate()]

   def main() -> None:
       print(f())
   main()
   ```
   Expected: named compile-time refusal `enumerate() with other than (iterable[, start])`, rc=3 (this is what base does). Actual: `Traceback ... IndexError: list index out of range`, rc=1, on both builds. A guard on `len(g.iter.args) == 1` (letting `_pair_plan` produce the named refusal) fixes it.
[cost $0.0561, opencode tokens {"total": 4497518, "input": 106370, "output": 19071, "reasoning": 26093, "cache.write": 0, "cache.read": 4345984}]
    tool time: bash 6.7 min
        178s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog16 tes
         26s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "######## $(basename $p)"; bash ~/to
         17s bash   cat > /tmp/rprobes/pair_blist.py <<'EOF' def f(bs: list[bytes]) -> list[bytes]:     return [v for i, v in enum
         17s bash   cat > /tmp/rprobes/pair_blist2.py <<'EOF' def g(bs: list[bytes]) -> list[int]:     return [i for i, v in enume
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in lab/census/programs/dev/t268.py lab/census/programs/gdev/g25_03
         13s bash   cat > /tmp/typedcheck.sh <<'EOF' #!/bin/bash # typedcheck.sh SRC WORKTREE src=$1; wt=$2; d=$(mktemp -d /tmp/tc
         11s bash   cat > /tmp/rprobes/pair_reverse.py <<'EOF' def f(xs: list[int]) -> list[int]:     return [v for i, v in enumer
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in lab/census/programs/dev/t268.py lab/census/programs/dev/t068.py

## fix round skipped: only 44 minutes left

FINAL VERDICT: FIX  2026-11-02T04:14:52Z
