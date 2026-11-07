# job job-fe1-11071637  started 2026-11-07T07:46:25Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all six review defects; no compiler/runtime/corpus changes, so no behaviour probes apply.

- `FE-SPEED-A0`: warm target corrected to ≤2.2 s (25.505−23.329=2.176), `scar_life` cold to ≤86.5 s (86.443), `ticket_audit` cold ≤70.7 s.
- Per-function cache: cold bound is 0; 50.4% is now labelled an edit-only ceiling, and the ranking no longer places it first on cold share.
- Top-20/hot-function 23.5% is labelled a cProfile-derived estimate, not a timed share.
- `parse` is now a timed phase: `ast.parse` wrapped in both processes, `prof.py --parse-only` re-measured it; 3.890 s = 1.1% of the timed cold wall. cProfile comparison corrected to 5.92 s = 0.6% of the profiled wall.
- Server option uses fast-27 medians: 0.257 s of 0.468 s = 55%, 2.2x.
- Both commits omit the `Co-Authored-By` trailer; `k=2.5` is now labelled an assumption.

Verification: `report.py` re-renders `RESULTS.md` byte-identically; `update_manifest.py --check` rc 0. On the final commit, `test_ail_frontend_speed` and `test_ail_safetynet` pass (2/2); the full required set (`+ test_ail_files`, `test_ail_corpus_findings3`) passed 4/4 in 344 s.

Commits: `63018e6`, `91d1537`.
[cost $0.0000, opencode tokens {"total": 5321002, "input": 143661, "output": 14903, "reasoning": 26950, "cache.write": 0, "cache.read": 5135488}]
    tool time: bash 19.4 min
        383s bash   python3 lab/fe/prof.py --parse-only --out lab/fe/results.json
        347s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_frontend_speed test_ail_safetynet test_ail_files
        300s bash   cp lab/fe/results.json /tmp/fe-test.json && timeout 300 python3 lab/fe/prof.py --parse-only --out /tmp/fe-test
        129s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_frontend_speed test_ail_safetynet
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo rc=$?; git status --short
          0s bash   python3 - <<'PY' import json, statistics, pathlib d=json.load(open('lab/fe/results.json')) b=[p for p in d['pr
          0s bash   git show --stat HEAD; git log --format='%h %s%n%b' -3
          0s bash   cat .agent/BASE_REV; echo ---; git rev-parse HEAD; git show --stat --oneline HEAD | head -30; echo ---; git br

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — fe1 review-1 fix

**What the change really does.** Corrects the measurement/ranking text in `lab/fe` + `docs/design/FRONTEND_SPEED.md`, adds timed `ast.parse` to the wrappers (`timed_outer.py`, `timed_inner.py`) with a `prof.py --parse-only` overlay, and regenerates `results.json`/`RESULTS.md`. `git diff work..HEAD -- AIL_CURRENT tools bench corpus` is empty, so the compiler is untouched and no C can change. Matches the worker report.

**Checks run (start 08:17, end ~08:30)**
- `par_check.py -j 2 test_ail_frontend_speed test_ail_safetynet`: 2/2, 0 failed, 128 s.
- `report.py` re-renders `RESULTS.md` byte-identically; `update_manifest.py --check` rc 0.
- Recomputed from `results.json`: warm `ticket_audit` 25.5054−23.329=**2.176**; `scar_life` cold 97.3809−10.9384=**86.443**; parse 3.8901=**1.07%** of timed cold wall; cProfile 5.9173=**0.63%** of profiled wall; fast-27 medians 0.0263/0.1758/0.0549 = 0.2572/0.4676 = **55.0%**, **2.22x**; emitter 50.4%, front end 54.4%, top-20 46.6%→23.5%, other 12.8%. Table cells all consistent.
- Harness probe: normal vs `timed_outer.py` build of `corpus/gdev/g18_008.py` with `--debug-dir` → `program.c` **sha256 identical**, stdout identical (only temp paths differ in `native_report.json`). Wrapping `ast.parse` does not alter generated C.
- No `icount`: no compiler/runtime hot code touched.

**Report claims.** All verified except the “full required set 4/4 in 344 s” (not re-run, per instructions). The one-line diff description matches.

**Fixed review defects.** 1/2 targets now use the correct warm/cold `other`; 3 cache cold bound 0 and 50.4% labelled edit-only; 4 parse now timed (3.89 s, 1.1%) and cProfile corrected to 0.6%; 5 server uses fast-27 medians (55%, 2.2x); 6 new commits carry no `Co-Authored-By`.

**Pre-existing (do not block).** Phase rows come from a single `timed_build`, not the median-of-3 the table header implies (true on base; parse inherits it). `test_ail_frontend_speed` is registered in the `ail_check.py` tuple instead of `tests.d/` despite `tests.d/` existing — from base commit `84ecb29`, not this change. `84ecb29` still carries a Claude trailer, but history cannot be rewritten without a forbidden rebase.

**Unverified.** The claimed 4/4 full required set; machine-dependent absolute seconds.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1713022, "input": 78687, "output": 6100, "reasoning": 20299, "cache.write": 0, "cache.read": 1607936}]
    tool time: bash 2.2 min
        129s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
          2s bash   cd /tmp && rm -rf tdcheck && mkdir -p tdcheck/{norm,time,cache_n,cache_t,tmp_n,tmp_t} && cd tdcheck && \ AIL_N
          0s bash   cd /home/runner/work/ail-ci/ail-ci && ls AIL_CURRENT/tests.d/ | wc -l; grep -rn "test_ail_frontend_speed" AIL_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/fe/report.py --out /tmp/RESULTS.rendered.md && diff -q /tmp/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rln "frontend_speed" . --include=*.py --include=*.txt --include=*.
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import json,statistics d=json.load(open('lab/fe/results
          0s bash   date; pwd; git status --short; git log --oneline -10; echo ---; git worktree list; echo ---; ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short; echo ---; git diff --stat; echo ---; git status --po

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T09:42:46Z
