# job job-rbccsplit2-11011010  started 2026-11-01T01:11:22Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `726721db` on `job-rbccsplit2-11011010` (working tree clean apart from untracked `.agent/pipeline.md`).

**Applied**
- Re-applied PR #305’s cc-split change: `ccsplit.py`, `pyfunc` clone dedupe/exit merge, `pyc` split build.
- Fix 1: added `AIL_EXIT_MERGE_MIN` to `ail_server.IMPORT_ENV`.
- Fix 2/3: `python/pkg-v12/ccsplit.py` now has the `s` SDK/wheel flag.
- Ran `update_manifest.py`; `--check` passes. `tools/diff_ids.py` does not exist in this tree, so it could not be run.

**Tests (final tree)**
- `test_ail_cc_split` 9 OK
- `test_ail_server` 19 OK
- `test_ail_packaging` 17 OK
- `test_ail_sdk` 29 OK
- `test_ail_safetynet` 5 OK
- `test_ail_files` 18 OK (1 skipped)
- `test_ail_corpus_findings3` 2 OK

**Generated C (HEAD base vs working tree)**
All 10 `lab/compare` `main.ail` builds are byte-identical except `chain_relax`, whose only diff is the expected `fmt__t0`/`fmt__t1` deduped alias bodies (one hunk). All `main.py` builds are identical where both sides build; `scar_life`, `tally_lang`, and `tree_fold` fail identically on both base and tree.

**Probes (all matched CPython on both general and typed builds)**
- `ccsplit_matrix.py` — float clone formatting via argument, list item, attribute, dict value, aliasing, empty/negative/large values.
- `ccsplit_returns.py` — early returns inside/outside loops, lists, default and `AIL_EXIT_MERGE=1 AIL_EXIT_MERGE_MIN=1`.
- `ccsplit_split.py` — default one-unit, `AIL_CC_SPLIT=2 AIL_CC_SPLIT_MIN=1`, and `AIL_CC_JOBS=2 AIL_CC_SPLIT_MIN=1`.
- `ccsplit_matrix.py` with `AIL_NO_CLONE_DEDUPE=1` — also matched.
[cost $0.0330, opencode tokens {"total": 2353969, "input": 100696, "output": 8014, "reasoning": 10635, "cache.write": 0, "cache.read": 2234624}]
    tool time: bash 19.9 min
        530s bash   sed -i "s|WRAP='/tmp/cmpc/save.sh'|WRAP=Path('/tmp/cmpc/save.sh')|" /tmp/cmpc/run.py && python3 /tmp/cmpc/run.
        187s bash   python3 AIL_CURRENT/test_ail_server.py 2>&1 | tail -30
        187s bash   python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -40
        163s bash   python3 AIL_CURRENT/test_ail_sdk.py 2>&1 | tail -40
         43s bash   python3 AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -40
         25s bash   set -o pipefail for p in /tmp/probes/ccsplit_matrix.py /tmp/probes/ccsplit_returns.py /tmp/probes/ccsplit_spli
         22s bash   python3 AIL_CURRENT/test_ail_packaging.py 2>&1 | tail -40
         20s bash   python3 AIL_CURRENT/test_ail_files.py 2>&1 | tail -40

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** Re-applies PR #305 verbatim (`ccsplit.py` and its test are byte-identical to `FETCH_HEAD`; the `pyc.py`/`pyfunc.py` hunks differ from the PR only in context/blank lines): opt-in parallel translation-unit split, opt-in shared exit cleanup, default-on clone dedupe. Adds the three CI registrations (`AIL_EXIT_MERGE_MIN` in `IMPORT_ENV`, `s` flag for `ccsplit.py`, tests.d entry) and regenerates the manifest.

**Probes (all on HEAD, `bash ~/tools/cmp.sh ... $PWD`, general + default builds):**
- `clone_dedupe.py`, `clone_empty.py` (float format via arg/list item/attr/dict, negative/zero/large, slice aliasing/mutation): both builds same as CPython. Note: these programs produced no `__t` clones, so they do not exercise dedupe.
- `chain_relax` executable (dedupe on): 4 hand inputs + all 32 public/hidden cases match reference; base and HEAD agree. Base/HEAD C differs only in the `fmt__t0`/`fmt__t1` alias hunk.
- `exit_merge.py` with `AIL_EXIT_MERGE=1` and default: both match CPython.
- `AIL_EXIT_MERGE=1` on the five tasks that actually contain `_r` returns (`rail_transfer`, `tally_lang`, `term_rank`, `ticket_audit`, `tree_fold`): 24/75/43/91/55 cases, 0 mismatches; 4 of 5 show `ail_exit_ret` in C.
- `split_typed.py` with `AIL_CC_SPLIT=3` (3 units) and `AIL_CC_JOBS=2` (2 units): both match CPython.
- `tally_lang/main.ail` forced split (`AIL_CC_SPLIT=3 AIL_CC_SPLIT_MIN=1`, 3 units): all 75 cases pass.
- `split_state.py` and `split_obj.py` fell back to the general path (type refusal), so they are not evidence for split.

**Generated C vs base (`git worktree add /tmp/base work`, `--debug-dir`):**
- 10 `main.ail`: 9 byte-identical; `chain_relax` differs only by the deduped fmt clones.
- `main.py`: the 5 that build (berth_sim, echo_pack, ledger_bin, term_rank, ticket_audit) are byte-identical; chain_relax, rail_transfer, scar_life, tally_lang, tree_fold fail identically on base and HEAD.

**Tests:** `test_ail_cc_split`, `test_ail_server`, `test_ail_packaging`, `test_ail_sdk`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`, 7/7). `update_manifest.py --check` exits 0.

**Claim check:**
- PR re-applied / defaults (dedupe on, split/exit-merge opt-in): verified.
- Fix 1 (`IMPORT_ENV`): verified by code and `test_ail_server`.
- Fix 2/3 (`s` SDK/wheel flag): verified by manifest and packaging/SDK tests.
- `tools/diff_ids.py` absent: verified.
- Test list: verified.
- Generated-C claim: verified, but the report's list of failing `main.py` tasks is incomplete (chain_relax and rail_transfer also fail identically; it says only three). Report inaccuracy, not a code defect.
- Worker's own probes: not verifiable (files not present); my independent probes above stand in.

**Pre-existing:** chain_relax/rail_transfer/scar_life/tally_lang/tree_fold `main.py` refusals are identical on the base.

**Unverified:** instruction-count comparison (perf_event_open is denied in this runner; no before/after numbers). Worker's `/tmp/probes` contents.

VERDICT: ACCEPT
[cost $0.0585, opencode tokens {"total": 5539361, "input": 70989, "output": 14048, "reasoning": 38644, "cache.write": 0, "cache.read": 5415680}]
    tool time: bash 19.8 min
        404s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
        301s bash   cd /tmp && rm -rf cgenpy && mkdir -p cgenpy && for t in $(ls /home/runner/work/ail-ci/ail-ci/lab/compare/src);
        296s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         57s bash   cd /tmp && rm -rf cgen && mkdir -p cgen && cat > /tmp/cgen/one.sh <<'EOF' #!/bin/bash wt=$1; task=$2; src=$3; 
         35s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/emtasks/check.py <<'EOF' import sys, tempfile, subprocess fro
         16s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/split_a.log /tmp/split_b.log; echo "=== split_state AIL_CC_SP
         12s bash   cd /tmp && rm -rf emtasks && mkdir emtasks && cd emtasks && for t in rail_transfer tally_lang term_rank ticket
         10s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/split_c.log /tmp/split_d.log; echo "=== split AIL_CC_SPLIT=3 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T03:43:43Z
