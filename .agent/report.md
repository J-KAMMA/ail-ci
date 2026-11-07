# job job-ctpred1_rr1-11071000  started 2026-11-07T01:00:38Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed as `ab6e1eb`.

- **Defect 1:** Regenerated `byte_identity` with the final `ccheck.py`: t131 refusal is now `998da936…`; `ccheck.py --check` prints `all 220 inputs identical` (exit 0).
- **Defect 2:** Corrected `CTIME_PRED.md` §5 to 0.262 s eligible cacheable, 0.146 s net, 0.474% of wall; also fixed the all-predicate total to 2.619 s and §7's 0.262 s / 0.9%.
- **Defect 3:** §2 now states measured inflation 0.8–12.9 µs/call (`Ctx.type_of` to `_etype`).

Verification:
- `pred_probe.py --tasks echo_pack`: calls/repeats/changed match the JSON exactly for all 8 predicates.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 3 modules, 0 failed (339 s, `-j 2`).
- `tools/update_manifest.py --check`: rc 0.
- Only `lab/profile/CTIME_PRED.json` and `.md` changed; not pushed.
[cost $0.0000, opencode tokens {"total": 904896, "input": 48958, "output": 3679, "reasoning": 6307, "cache.write": 0, "cache.read": 845952}]
    tool time: bash 44.7 min, edit 0.0 min
        593s bash   python3 lab/profile/ccheck.py --check 2>&1 | tail -10
        588s bash   python3 lab/profile/ccheck.py --base 2>&1 | tail -10
        581s bash   python3 lab/profile/ccheck.py --check 2>&1 | tail -30
        569s bash   python3 lab/profile/ccheck.py --check 2>&1 | tail -5 && python3 tools/update_manifest.py --check; echo "manife
        341s bash   ls AIL_CURRENT/test_ail_files.py AIL_CURRENT/test_ail_corpus_findings3.py 2>&1; python3 tools/par_check.py -j 
          8s bash   rm -rf /tmp/predcheck && python3 lab/profile/pred_probe.py --tasks echo_pack --out-dir /tmp/predcheck 2>&1 | t
          1s bash   git status && git log --oneline -10 && git branch --show-current
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "rc=$?"; git status --short

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change actually does:** regenerates the `byte_identity` record in `CTIME_PRED.json` with the final `ccheck.py` and corrects three number/prose statements in `CTIME_PRED.md`; no compiler, runtime, emitter, or test file is touched (diff is exactly `lab/profile/CTIME_PRED.json` and `.md`).

**Verified**
- Defect 1 fixed: `python3 lab/profile/ccheck.py --check` on HEAD prints `inputs: 220 (alias_study/trans absent)` / `all 220 inputs identical`, rc 0. The t131 row now records refusal `998da936…`.
- The regenerated record differs from the base only in `byte_identity`; `c`, `exe`, `returncode` differ in 0 rows, and the only changed refusal is `glm-5.3-flash-free/t131.py` (the stale row from the review). The rest of the large JSON diff is `source` path metadata rewritten to this worktree plus 300-char trimming of `reason`; `--check` ignores both.
- Defect 2 fixed and arithmetically consistent: per-task eligible cacheable = 0.2620 s, listed calls = 928,175, lookup = 0.1160 s, net = 0.1460 s = 0.4739% of the 30.795 s wall; all-predicate per-task cacheable = 2.6188 s. §5 now says 0.262/0.146/0.474% and 2.619 s, §7 says 0.262 s / 0.9%. Matches the table-derived values.
- Defect 3 fixed and consistent with the JSON: inflation `(probe_own - fe_own)/calls` = 0.79 µs for `Ctx.type_of`, 12.89 µs for `_etype`, i.e. 0.8–12.9 µs.
- `pred_probe.py --tasks echo_pack`: calls/repeats/changed match the committed JSON for all 8 predicates.
- `tools/update_manifest.py --check`: rc 0.
- Tests on HEAD: `test_ail_safetynet` 177 s, `test_ail_files` 104 s, `test_ail_corpus_findings3` 235 s, 0 failed (`-j 2`).

**Defects**
- None remaining.

**Notes:** The regeneration rewrote every `source` absolute path to `/home/runner/work/ail-ci/ail-ci/...` and trimmed some `reason` strings; cosmetic only, since `--check` compares only `c`/`exe`/`refusal`/`returncode`, and `c`/`exe` are byte-identical to the base record. No speed claim to check (no hot code edited).

**Pre-existing:** none identified.

**Unverified:** push/PR and CI shard results (worker states not pushed); not relevant to the data/doc change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 785256, "input": 62222, "output": 4093, "reasoning": 9053, "cache.write": 0, "cache.read": 709888}]
    tool time: bash 16.5 min
        569s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 lab/profile/ccheck.py --check 2>&1 | tail -8; echo "rc=${P
        236s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        178s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/predcheck2 && python3 lab/profile/pred_probe.py --tasks echo
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -n "0\.222\|0\.34%\|0\.106\|2\.544\|2\.619\|0\.262\|0\.474\|0\.9%\|
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show work:lab/profile/CTIME_PRED.json > /tmp/old.json && python3 - <
          0s bash   date; pwd; git log --oneline -10; echo ---; git status --short; echo ---; git branch --show-current
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import json o=json.load(open('/tmp/old.json')); n=json

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T03:25:00Z
