# job job-ctimes2-11051914  started 2026-11-05T10:15:09Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Stopped at the pricing gate; no compiler edit made.

- ctimes1's pick (`CTIME_FE.md` on `job-ctimes1-11051342`): `pyfunc` type/kind probes, 6.731 s pooled, 21.9% share, full bound 1.280x, halved 1.123x. Owner is `pyfunc.py`, a busy lane → recorded as follow-up.
- Best free row: `rangecheck.py`, 0.997 s, 3.2%, full 1.033x, halved 1.016x (max 1.079x on scar_life); also outside the permitted file list.
- Best in-list free row: `fastwalk.py:walk`, 0.860 s, 2.8%, full 1.029x, halved 1.014x (max 1.021x on tree_fold).
- No free row reaches 1.10x at the halved projection on any task, so the brief's stop rule fires.

Committed `lab/profile/CTIME_CUT.md` as `1ffcb3ce` with the full per-task price tables, the assumed 0.5 fraction of the bound, earlier-cut calibration, and the pyfunc-lane follow-up. Since there is no code change, `ccheck.py` and the tests were not run. Not pushed, per the runner instruction.
[cost $0.0000, opencode tokens {"total": 533304, "input": 43213, "output": 4910, "reasoning": 6461, "cache.write": 0, "cache.read": 478720}]
    tool time: bash 0.2 min, edit 0.0 min, write 0.0 min
          8s bash   git fetch origin job-ctimes1-11051342 2>&1 | tail -5 && git show effbc50:lab/profile/CTIME_FE.md | head -200
          1s bash   git fetch origin integ 2>&1 | tail -3; git log --oneline origin/integ -5; echo ---; git log --oneline origin/j
          0s bash   git log --oneline -20; echo ---; git show --stat HEAD | head -40; echo ---; git branch -r; echo ---; git rev-p
          0s bash   pwd && git status && git branch -a | head -50 && git log --oneline -5
          0s bash   git ls-remote origin | grep -i ctime
          0s bash   ls lab/compare/src/*/typed.py | wc -l; ls lab/compare/src/*/main.py | wc -l; ls lab/corpus/programs | head; ls
          0s bash   git add lab/profile/CTIME_CUT.md && git commit --amend -m "ctimes2: price the free front-end rows and stop bef
          0s bash   git add lab/profile/CTIME_CUT.md && git commit -m "ctimes2: price the free front-end rows and stop before edit

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `work..HEAD`.

**What the change really does:** adds only `lab/profile/CTIME_CUT.md` (91 lines). No compiler, runtime, test or manifest file changes (`git diff --name-status work..HEAD` = `A lab/profile/CTIME_CUT.md`). This matches the report.

**Claims checked against `CTIME_FE.md` and the tree**
- ctimes1 pick: pyfunc type/kind probes, 6.731 s pooled, 21.9 %, full 1.280x, halved 1.123x, `pyfunc.py` busy — verified.
- Best free row `rangecheck.py`: 0.997 s, 3.2 %, full 1.033x, halved 1.016x, max 1.079x on scar_life, not in the permitted list — verified (per-task table arithmetic rechecked; e.g. scar_life 0.239/1.641 → 1.079).
- Best in-list free row `fastwalk.py:walk`: 0.860 s, 2.8 %, full 1.029x, halved 1.014x, max 1.021x on tree_fold — verified; `fastwalk.py` is in the allowed list.
- "No free row reaches 1.10x at the halved projection on any task" — verified against CTIME_FE section 5 (only the busy pyfunc row clears 1.10x).
- Stop decision under the brief's stop rule — verified consistent with CTIME_FE section 6.
- Commit `1ffcb3ce` exists, branch is one commit ahead of origin, nothing pushed — verified.

**Probes / byte identity:** no changed behaviour exists, so no probes were applicable. As a spot check I built `berth_sim/typed.py` on HEAD and on a `work` worktree under `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`: `program.c` and the executable both have identical SHA-256 hashes. No C can change from this commit.

**Tests:** `test_ail_safetynet` passes on HEAD (177.7 s, 0 failed). My first run under `ulimit -v 1500000` failed `S4_generators_gc` (output truncated after the first line); the unconstrained rerun passed, so that is my memory cap, not the change. The change adds no test module.

**Unverified / not applicable:** `lab/profile/ccheck.py` and `test_ail_ctime_cut.py` were not created, and no instruction-count/wall measurement was done; with no compiler edit these are moot under the stop rule. The other named regression modules were not rerun because no source changed.

No defect found; the report is accurate and the stop decision follows the brief.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 660271, "input": 69580, "output": 2877, "reasoning": 12710, "cache.write": 0, "cache.read": 575104}]
    tool time: bash 5.5 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_safe
        128s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 ../tools/par_check.py
         23s bash   set -e rm -rf /tmp/rout/A /tmp/rout/B /tmp/rcache_A /tmp/rcache_B; mkdir -p /tmp/rout /tmp/rcache_A /tmp/rcach
          0s bash   cd /home/runner/work/ail-ci/ail-ci; git worktree add /tmp/base work 2>&1 | tail -3; mkdir -p /tmp/rprobes /tmp
          0s bash   cd /home/runner/work/ail-ci/ail-ci; git show --stat 0e253de8 | head -40; echo ---; git diff --stat origin/inte
          0s bash   set -e for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do   tag=$(basename "$wt")   rm -rf /tmp/rout/$tag
          0s bash   date; pwd; git status; echo ---; git log --oneline -15; echo ---; git log --oneline work..HEAD 2>&1 | head -50
          0s bash   cd /home/runner/work/ail-ci/ail-ci; git diff --name-status work..HEAD; echo ---; git diff --name-only work..HE

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T11:40:09Z
