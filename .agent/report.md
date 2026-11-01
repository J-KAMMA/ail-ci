# job job-rbfailfast-11011235  started 2026-11-01T03:38:19Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied PR #299 (`py-failfast`) on the current tree, keeping #284 (int64 default) and #307 (module system).

- Commit: `3e00117`
- Added `walkmemo.py` (marks, mix report, refusal memo); split `pyboxed2.build()` into memo wrapper + `_build_once`; unified marks now use the table. Dropped the PR's accidental CRLF conversion.
- Acceptance: 10/10 lab/compare tasks identical (5 builds had byte-identical `program.c`; 5 refusals had identical messages).
- Corpus: scanned all 219 programs plus 56 finding copies; only **17** are currently refused, not 30. All 17 give identical refusal messages. I checked 30 from the historical refused set: 17 refused identically, 13 now build with identical C; 0 mismatches.
- Probes: `p_rb_ints`, `p_rb_containers`, `p_rb_empty`, `p_rb_alias`, `p_rb_negative` matched CPython on both builds; `p_rb_refuse_genexp` and `p_rb_refuse_sys` were refused by name on both. `p_rb_memo` verified repeated refusal equality and unchanged C.
- Tests on final commit: `test_ail_walkmemo`, `test_ail_int64_default`, `test_ail_modsys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6/6 pass, 468 s.
- `tools/diff_ids.py` is absent from this tree; `tools/update_manifest.py` ran and `--check` passes.
[cost $0.0000, opencode tokens {"total": 8197665, "input": 189733, "output": 16565, "reasoning": 17223, "cache.write": 0, "cache.read": 7974144}]
    tool time: bash 36.4 min, edit 0.0 min, write 0.0 min
        469s bash   python3 tools/par_check.py -j 2 test_ail_walkmemo test_ail_int64_default test_ail_modsys test_ail_safetynet te
        298s bash   find lab/corpus/programs -name '*.py' | sort > /tmp/accept/allprogs.txt; wc -l /tmp/accept/allprogs.txt mkdir 
        294s bash   python3 tools/par_check.py -j 2 test_ail_walkmemo test_ail_int64_default test_ail_modsys test_ail_safetynet te
        285s bash   mkdir -p /tmp/accept/allscan_ir runone() { wt=$1; out=$2; src=$3; n=$(basename $(dirname $src))_$(basename $sr
        147s bash   mkdir -p /tmp/accept/refbase /tmp/accept/refcur runone() { wt=$1; out=$2; src=$3; n=$(basename $src .py); d=$o
        147s bash   python3 - <<'PY' import json from pathlib import Path rows=[json.loads(l) for l in Path('lab/corpus/results/re
        114s bash   mkdir -p /tmp/accept/cur; for t in $(ls lab/compare/tasks); do d=/tmp/accept/cur/$t; mkdir -p $d; ( cd /tmp/ac
        109s bash   rm -rf /tmp/accept/base /tmp/accept/basewt; git worktree add --detach /tmp/accept/basewt HEAD >/tmp/accept/wt.

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review report — PR #299 re-application (`3e00117`)

**What the change really does:** adds `walkmemo.py` memo tables (marks keyed by AST-content fingerprint + `AIL_*` env, `pymix.analyze` per source/env, repeated `pyboxed2.build` refusals per source/allow_mix/env) and routes the three mark sites + `_setup_mix` through them; `build()` is split into a memo wrapper and `_build_once` keeping #284's int64 routing. Matches the report.

**Claims**
- Commit `3e00117`, files/CRLF (pyboxed2 stays LF): verified.
- 10/10 lab/compare identical: verified, but with the runner's real modes (`--exact-int` for rail_transfer/chain_relax): 7 builds → byte-identical `program.c`; 3 refusals → identical stderr (scar_life, tally_lang, tree_fold). Worker's "5 builds/5 refusals" came from omitting `--exact-int`; same conclusion either way.
- 17 corpus refusals, 30-program historical check: unverified (time box).
- Probes listed below: verified independently (worker's own probe names not re-run verbatim).
- Tests: `test_ail_walkmemo` 1.7 s and `test_ail_safetynet` 210.8 s pass on HEAD; the other four modules were not re-run (outside the reviewer's touched+safetynet scope).
- `tools/diff_ids.py` absent; `update_manifest.py --check` exit 0: verified.
- Speed 46→18 s / 56→30 s: unverified; 3 timed lab refusals showed no clear win (tree_fold 27.2 s memo vs 25.0 s off; scar_life 18.7 vs 20.3; tally_lang 16.9 vs 16.4). No correctness impact, generated C identical.

**Probes** (`bash ~/tools/cmp.sh`, both g/d builds)
- exact mode: `rp_big_arg`, `rp_big_empty`, `rp_big_attr`, `rp_iter_mutate` — CPython-identical stdout/exit.
- default: `rp_no_feature`, `rp_refuse_match` — identical; `rp_refuse_async/exec/genexp/view` — refused by name, identical to base and to `AIL_NO_WALKMEMO=1`.
- default `rp_big_arg` — refused by name (int64 literal), identical to base.
- C identity HEAD vs `work` (`--debug-dir`): 5/5 probe builds identical; 7/7 lab/compare builds identical; `rp_unified_mix` with `AIL_UNIFIED_FORCE=1 AIL_EXACT_INT=1` identical and CPython-matching; strict-mode refusals for berth_sim/tree_fold/chain_relax identical.
- Aliasing/mutation: edited tree key (`test_w1`), list/bytearray slice-then-mutate and list mutation-during-iteration probes match CPython; `mix_report` result is not mutated by `_setup_mix`.

**Pre-existing:** none observed.

**Unverified:** 17-refusal corpus count / historical 30-set; the four extra test modules; exact fail-fast timings; gdev instruction counts (generated C is byte-identical, so not applicable).

VERDICT: ACCEPT
[cost $0.0575, opencode tokens {"total": 5221222, "input": 118504, "output": 10982, "reasoning": 29848, "cache.write": 0, "cache.read": 5061888}]
    tool time: bash 19.9 min
        521s bash   cd /tmp/rprobes && rm -rf labs && mkdir labs && for t in $(ls /home/runner/work/_temp/w2/lab/compare/src); do 
        212s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet 2>&1 | tail
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_walkmemo test_a
        101s bash   cd /tmp/rprobes && rm -rf strict && mkdir strict && for t in berth_sim tree_fold chain_relax; do extra=""; cas
         72s bash   cd /tmp/rprobes && for t in scar_life tally_lang; do for mode in memo nomemo; do e=""; [ $mode = nomemo ] && e
         52s bash   cd /tmp/rprobes && for mode in memo nomemo; do e=""; [ $mode = nomemo ] && e="AIL_NO_WALKMEMO=1"; /usr/bin/tim
         48s bash   cd /tmp/rprobes && : > out.txt; for p in rp_big_arg rp_big_empty rp_big_attr rp_iter_mutate; do echo "=== $p e
         24s bash   cd /tmp/rprobes && rm -rf cbase chead && mkdir cbase chead && for p in rp_no_feature rp_big_arg rp_big_empty r

## full suite
test_ail_packaging

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed.

- Cause: `walkmemo.py` was pinned in `manifest.d/e0.txt` without the SDK flag, so `test_ail_packaging` found a pinned compiler file missing from `sdk_files`.
- Fix: changed its flags from `-` to `fs`, keeping the existing pin and the memoization change intact.
- Verified: `test_ail_packaging` (17 tests) and `test_ail_walkmemo` (7 tests) pass; `tools/update_manifest.py --check` passes.
- Commit: `0fa5abc packaging: select walkmemo.py in the SDK`
[cost $0.0141, opencode tokens {"total": 742094, "input": 67308, "output": 2049, "reasoning": 1249, "cache.write": 0, "cache.read": 671488}]
    tool time: bash 0.4 min, edit 0.0 min, read 0.0 min
         11s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_packaging 2>&1 | tail -100
         11s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_packaging 2>&1 | tail -40
          1s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_walkmemo 2>&1 | tail -40
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check; echo exit=$?
          0s bash   cd AIL_CURRENT && python3 - <<'PY' import hashlib, ail_manifest m=ail_manifest.load('.') for n in ['python/pkg
          0s bash   cd AIL_CURRENT && python3 - <<'PY' import json m=json.load(open('MANIFEST.json')) print(m.keys()) print(len(m[
          0s bash   pwd && ls -la && git status && git log --oneline -10
          0s bash   cd /home/runner/work/_temp/w2 && git add AIL_CURRENT/manifest.d/e0.txt && git commit -m "packaging: select wal

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T07:20:01Z
