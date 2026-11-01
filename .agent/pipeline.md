# job job-beatc1-11011753  started 2026-11-01T08:53:59Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Committed on `job-beatc1-11011753` as `e4b0541`.

**Findings**
- Baseline, 10 tasks, median of 5: AIL wins only `term_rank` (1.30×); C wins the other nine, from 1.22× (`chain_relax`) to 10.15× (`rail_transfer`).
- Largest memory gap: `tree_fold`, 603 MiB AIL vs 194 MiB C.
- Gprof profiles and per-task Amdahl pricing are in `docs/design/BEAT_C.md`; only A/scar_life, B/berth_sim and C/echo_pack have bounds above their required gap.
- Step 4, byte-identical output both times:
  - A scar_life OpenMP: **1.395× all-core** (paired 1.449×, best 2.33×), but median still slower than C.
  - B berth_sim `restrict`: **1.00–1.03×**, a tie.
- Instruction counts unavailable: `perf_event_open` denied (`perf_event_paranoid=4`), no valgrind. `tools/roofcheck_v1.py` is absent from this tree.
- No compiler code changed; no probes were needed.

**Verification**
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **3 modules, 0 failed** on the final commit.
- `python3 tools/update_manifest.py --check`: **pass**.
[cost $0.0752, opencode tokens {"total": 5026232, "input": 254269, "output": 15249, "reasoning": 22890, "cache.write": 0, "cache.read": 4733824}]
    tool time: bash 29.0 min
        708s bash   python3 lab/beatc/step4.py --out /tmp/step4.json --runs 5 > /tmp/step4.log 2>&1; rc=$?; echo rc=$rc; tail -30 
        661s bash   python3 lab/beatc/step4.py --out /tmp/step4.json --runs 5 > /tmp/step4.log 2>&1; rc=$?; echo rc=$rc; cat /tmp/
        363s bash   ls AIL_CURRENT/test_ail_safetynet.py AIL_CURRENT/test_ail_files.py AIL_CURRENT/test_ail_corpus_findings3.py &&
          3s bash   rm -rf /tmp/echo_build && mkdir -p /tmp/echo_build/cache /tmp/echo_build/tmp && AIL_CACHE=/tmp/echo_build/cach
          2s bash   find /usr /opt -maxdepth 4 -name 'valgrind*' -o -name 'callgrind*' 2>/dev/null | head; ls /usr/bin | grep -E '
          0s bash   git add DEVLOG.md DIFFERENCES.md docs/design/BEAT_C.md lab/beatc/measure.py lab/beatc/profile.py lab/beatc/ste
          0s bash   git status --short; python3 tools/update_manifest.py --check; echo manifest_rc=$?; git log --oneline -1; git s
          0s bash   mkdir -p /tmp/echo_dbg /tmp/echo_cache /tmp/echo_tmp && AIL_CACHE=/tmp/echo_cache TMPDIR=/tmp/echo_tmp AIL_NO_

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review — job-beatc1-11011753 (`e4b0541`)

**What the change really does.** Adds `docs/design/BEAT_C.md`, `lab/beatc/{measure,profile,step4}.py`, three raw JSON result files, a DEVLOG entry and one DIFFERENCES row. No compiler, runtime, test, or benchmark source changed (`git diff --name-only work..HEAD` is only docs/lab), so default C output is untouched.

**Verified**
- Baseline table, ratios, RSS, `term_rank` win and `tree_fold` memory gap match `baseline-5.json`. Spot re-ran `measure.py` on `chain_relax`: AIL 1118.4 ms, C 918.2 ms, correct output — matches the committed run.
- Section 2 profiles match `profile.json`; section 4 numbers match `step4.json`. Re-ran `step4.py --tasks berth_sim --runs 1`: edited build byte-identical, gain 0.924× one-core / 1.044× all-core — consistent with the reported tie.
- `perf_event_paranoid=4`, no valgrind, and no `roofcheck_v1.py` in the tree: all confirmed.
- Tests on HEAD: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **3 modules, 0 failed**. `tools/update_manifest.py --check` — pass.
- No behaviour probes apply: no source/compiler change.

**False claim / defect**
1. `docs/design/BEAT_C.md:97-99,163-164,181` — the "only three cells" result and the conclusion built on it are wrong on the report's own table. `tally_lang` has a 1.49× gap, C share `s=0.65`, removal bound `1/(1-0.65)=2.86×`, and at the report's assumed 40% reach gives `1 + 0.40*(2.86-1) = 1.74×`, which exceeds the 1.49× needed.
   Probe (arithmetic over the committed table):
   ```
   gap = 1269.5/854.3          # 1.49
   bound = 1/(1-0.65)          # 2.86
   realistic = 1 + 0.40*(bound-1)
   print(round(gap,2), round(bound,2), round(realistic,2))
   ```
   Expected: `1.49 2.86 1.74` → a fourth cell above its gap, and C/tally_lang is the only realistic single-mechanism win.
   Actual: the doc says only A/scar, B/berth, C/echo qualify, omits tally_lang, concludes "No single mechanism closes the measured AIL→C gap" (line 181), and quotes C's ceiling as 1.82× (echo) rather than 2.86× (tally).
   Fix: add C/tally_lang to section 3, the realistic-gain discussion and the ranked list (ahead of echo_pack), or state explicitly that its 0.65 share is not a valid known roof and remove it from the bound table. Step 4's "two most promising" choice should then be re-checked: C/tally_lang is the highest-bound pair and was not tested.

**Minor**
- `BEAT_C.md` does not end with the ranked list; section 6 follows it, while Step 5 says the file ends with the ranked list.

**Pre-existing:** none (no code changed).

**Unverified:** full 10-task 5-run baseline/profile and the 5-run scar_life OpenMP result were not re-run; only the committed JSON plus the two spot checks above were used.

VERDICT: FIX
[cost $0.0307, opencode tokens {"total": 1286421, "input": 82782, "output": 4125, "reasoning": 20378, "cache.write": 0, "cache.read": 1179136}]
    tool time: bash 5.9 min
        270s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_f
         62s bash   date; python3 lab/beatc/step4.py --tasks berth_sim --runs 1 --out /tmp/recheck-step4.json 2>&1 | tail -20; pyt
         18s bash   date; python3 lab/beatc/measure.py --tasks chain_relax --runs 1 --out /tmp/recheck-chain.json 2>&1 | tail -20;
          0s bash   python3 tools/update_manifest.py --check; echo rc=$?; grep -n "LAB/beatc\|lab/beatc" MANIFEST.json | head; gre
          0s bash   date; pwd; git log --oneline -8; echo ---; git log --oneline work..HEAD; echo ---; git status --short
          0s bash   python3 - <<'EOF' import json d=json.load(open('lab/beatc/results/profile.json')) print(d.get('started'), d.ge
          0s bash   python3 - <<'EOF' import json for fn in ['baseline-5','profile','step4']:     d=json.load(open(f'lab/beatc/res
          0s bash   git log -1 --format=%B HEAD; echo ---; git diff work..HEAD | grep -nE '^\+.*[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+' 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `f475f17`.

- Corrected the main defect: `C / tally_lang` (gap 1.49×, bound 2.86×, 40%-reach gain 1.74×) is now the fourth cell above its gap, the only priced single-mechanism win, and appears ahead of `echo_pack` in the ranked list.
- Re-checked Step 4 with the highest-bound pair: specialized tally's `popcnt` helper to `__builtin_popcountll`; output byte-identical, paired gain **1.029× one-core / 1.090× all-core**. The 1.74× remains an upper bound, not evidence.
- Moved the ranked list to the end of `BEAT_C.md` (now section 6).
- Updated `lab/beatc/step4.py`, `results/step4.json`, `DEVLOG.md`, and `DIFFERENCES.md`.

Verification on final commit: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **3 modules, 0 failed**; `update_manifest.py --check` passes. No compiler/runtime/test source changed, so no behaviour probes apply; the edited Step-4 build was byte-identical on every run.
[cost $0.0481, opencode tokens {"total": 2226784, "input": 188896, "output": 11237, "reasoning": 11547, "cache.write": 0, "cache.read": 2015104}]
    tool time: bash 6.7 min, edit 0.0 min
        317s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_a
         50s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/step4.py --tasks tally_lang --runs 5 --out /tmp/step4-
         31s bash   cat > /tmp/try_tally.py <<'PY' import sys, tempfile, subprocess, time, statistics, hashlib from pathlib import
          4s bash   mkdir -p /tmp/tallydbg/cache /tmp/tallydbg/tmp && cd /tmp/tallydbg && AIL_CACHE=/tmp/tallydbg/cache TMPDIR=/tm
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 tools/update_manifest.py && python3 tools/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo manifest_rc=$?; git statu
          0s bash   git log --oneline -8; echo ---; git status --short; echo ---; ls; echo ---; ls lab/beatc docs/design 2>/dev/nu
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add DEVLOG.md DIFFERENCES.md docs/design/BEAT_C.md lab/beatc/step4.p

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Documentation/measurement only: adds `docs/design/BEAT_C.md`, `lab/beatc/{measure,profile,step4}.py`, raw JSON, and DEVLOG/DIFFERENCES entries. `git diff --name-status work..HEAD` shows no `AIL_CURRENT/` or `tools/` file changed; the revision adds C/tally_lang to the pricing and Step 4 and moves the ranked list to §6.

**Claims checked**
- Fixed and committed as `f475f17` — verified.
- C/tally_lang is now the fourth cell above its gap, the only priced single-mechanism win at the assumed 40% reach, and ahead of `echo_pack` in the ranking — verified in §3, the realistic-gains paragraph, and §6.
- Tally `popcnt` Step-4 edit byte-identical, paired gain 1.029× / 1.090× — verified against `lab/beatc/results/step4.json`.
- Ranked list moved to end (section 6) — verified.
- `step4.py`, `results/step4.json`, `DEVLOG.md`, `DIFFERENCES.md` updated — verified.
- 3 required modules, 0 failed; manifest check passes — independently reproduced: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all ok; `update_manifest.py --check` rc=0.
- No compiler/runtime/test source changed — verified.
- Instruction counts unavailable — verified: `perf_event_paranoid=4`, `perf_event_open: Permission denied`, `perf record` rc=255, no valgrind.

**Numbers.** The baseline table matches `results/baseline-5.json` (e.g. tally 1269.5/854.3 = 1.486, term_rank 1843/2393 = 0.77); the Step-4 table matches `step4.json`; profile shares are a subset of `profile.json`.

**Probes.** Three probes in `/tmp/rprobes` (dataclass/list/dict/slice/bytearray/formatting, tuple/list mutation, linked list/dict) match CPython on both general and default builds. Generated C for `lab/compare/src/tally_lang/main.ail` is byte-identical on HEAD vs `/tmp/base_beatc` (sha256 `742df34d…`). No behaviour changed, so no further probes apply.

**Unverified.** Did not rerun the full 10-task timing/profile campaigns or the hand-edited Step-4 builds; those numbers come from the committed raw JSON, which is internally consistent.

**Pre-existing.** None observed; no generated C differs from the base.

VERDICT: ACCEPT
[cost $0.0312, opencode tokens {"total": 1963636, "input": 83501, "output": 4870, "reasoning": 16961, "cache.write": 0, "cache.read": 1858304}]
    tool time: bash 6.8 min
        322s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_saf
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1.py /tmp/rprobes/p2.py /tmp/rprobes/p3.py; do ec
         36s bash   sed -i 's/(\[0\], {/(\[0,1\], {/' /tmp/rprobes/p1.py && cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rp
          9s bash   set -e for wt in /home/runner/work/ail-ci/ail-ci /tmp/base_beatc; do   d=$(mktemp -d /tmp/dbgXXXX)   AIL_NO_CA
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base_beatc work 2>&1 | tail -2 && cd /tmp/base_bea
          0s bash   cd /home/runner/work/ail-ci/ail-ci && ls AIL_CURRENT/tests.d/ 2>/dev/null | head; echo ---; ls tools | head -4
          0s bash   cd /tmp/rprobes && python3 p1.py; echo rc=$?
          0s bash   cd /tmp/base && git rev-parse --short HEAD 2>/dev/null; git status --short 2>/dev/null | head; cd /home/runner

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T11:56:40Z
