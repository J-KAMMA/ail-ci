# job job-rbstd_copy-11020210  started 2026-11-01T17:21:49Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-std_copy-11012212` onto the current tree and committed as `71e924c`.

- Conflicts resolved keeping both sides: pprint keyword sets/identity fragment + `copy.copy`/`copy.deepcopy` names, protocol refusal, `COPY` runtime, tests.
- `tools/diff_ids.py` does not exist on this tree (as prior DEVLOG entries note); `tools/update_manifest.py` ran and `--check` passes.
- Tests on final tree: `test_ail_std_copy`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass. Also `test_ail_std_pprint`, `test_ail_genlib` — 2/2 pass.
- Probes in `/tmp/probes/`: `copy_types`, `copy_alias`, `copy_channels`, `copy_errors` match CPython on both builds; `copy_badkw` and `copy_protocol` are refused by name on both builds. (An earlier `copy_types` used `is` on ints and hit pre-existing DIFFERENCES C114; rewritten to compare ints with `==`.)
- Not pushed.
[cost $0.0000, opencode tokens {"total": 1103414, "input": 31856, "output": 6363, "reasoning": 6123, "cache.write": 0, "cache.read": 1059072}]
    tool time: bash 12.4 min, edit 0.0 min
        414s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_copy test_ail_safetynet tes
        259s bash   cd /home/runner/work/ail-ci/ail-ci && ls AIL_CURRENT/test_ail_genlib.py 2>/dev/null; python3 tools/par_check.p
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/copy_*.py; do echo "===== $p"; bash ~/tools/cmp.sh 
         20s bash   cat > /tmp/probes/copy_types.py <<'PY' import copy  def main() -> None:     for v in [5, -7, 0]:         a = c
          7s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-std_copy-11012212 2>&1 | tail -20
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rln '^<<<<<<<\|^=======$\|^>>>>>>>' AIL_CURRENT lab/stdlib/copy ||
          0s bash   pwd && git status && git log --oneline -5 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rln '^<<<<<<<\|^>>>>>>>' AIL_CURRENT/manifest.d | head; python3 to

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review report — job rbstd_copy (`71e924c`)

**What the change really does:** re-applies the accepted `std_copy` diff: adds `copy.copy` / `copy.deepcopy` names + keyword sets in `genlib.py`, the call wrappers in `prelude_genlib.py`, the `COPY` runtime fragment in `safetyrt.py` (shallow/deep copier, memo, keep-alive, tuple/set/dict/instance/bytearray/table handling), the copy-protocol refusal and `_bound_names` class-body fix, plus `test_ail_std_copy`, `tests.d` registration, 12 lab programs and DEVLOG. Matches the report.

**Re-application check:** diff of `HEAD` against the original job `FETCH_HEAD` shows the copy code, test file, `tests.d` entry, lab programs and `RESULTS.md` are byte-identical; the only extra content is the current tree's own pprint/heapq/random work. Both sides' fixes are present (`ppid`/`_ail_pp_identity` and copy `FRAGMENTS`/`ORDER`; pprint keyword sets and copy names). No lost hunks.

**Probes** (`bash ~/tools/cmp.sh`, both general + default builds; all stdout equal to CPython 3.12, exit 0):
- `p1_shallow` list/dict/set/bytearray/tuple/frozenset/instance aliasing — pass
- `p2_deep` nested, shared refs, tuple/list cycles, tuple keys, set of tuples — pass
- `p3_memo` reused and explicit memo, set/frozenset memo counts, keyword `x`/`memo` — pass
- `p4_errors` missing/extra/duplicate args, non-dict memo, 3rd positional — pass
- `p5_gen` generator direct/list/dict/tuple, shallow list does not raise — pass
- `p6_types` ints (incl. 2^40), floats, str, bytes, bool, None, empty containers, bytearray — pass
- `p7_unrelated` json + pprint + heapq + class methods named `json`/`copy` — pass
- `p9_source`/`p10_table`/`p11_cycles` source mutation, tuple tables, dict/instance self-cycles — pass
- `p8_badkw` `copy.copy(1, y=2)` refused by name on both builds (acceptable).

My first `p3`/`p6` drafts were refused for unrelated unsupported constructs (`_nil` dead branch, `is` on `2**40` → DIFFERENCES C114); rewritten without them.

**Unrelated C unchanged:** `lab/compare/src/ticket_audit/main.py` builds on HEAD and `/tmp/base`; `program.c` byte-identical (only `native_report.json` temp paths/cwd differ). `tree_fold` fails identically on both (exit 3), pre-existing.

**Tests (HEAD):** `test_ail_std_copy`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass. Also `test_ail_std_pprint`, `test_ail_genlib` — 2/2 pass. `tools/diff_ids.py` absent (verified); `update_manifest.py --check` passes.

**Report claims:** all verified (commit, conflict resolution, missing `diff_ids.py`, manifest check, 4+2 test results).

**Pre-existing:** `is` between large equal ints (C114) and `tree_fold` failure appear on base too.

**Unverified:** worker's own `/tmp/probes/copy_*` not re-run (my probes cover the same ground); full suite and speed not run (copy code is not on any hot path; C for non-copy programs is unchanged).

VERDICT: ACCEPT
[cost $0.0303, opencode tokens {"total": 2123977, "input": 72617, "output": 10106, "reasoning": 12070, "cache.write": 0, "cache.read": 2029184}]
    tool time: bash 15.3 min
        249s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_pprint test_ail_genlib 2>&1 | tail -10
        195s bash   for t in ticket_audit tree_fold; do rm -rf /tmp/ddh_$t /tmp/ddb_$t; python3 AIL_CURRENT/ail_chatgpt.py compile
        120s bash   cd AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_std_copy test_ail_safetynet test_ail_files test
        120s bash   cd AIL_CURRENT && nohup setsid bash -c 'python3 ../tools/par_check.py -j 2 test_ail_std_copy test_ail_safetyne
        116s bash   for p in p1_shallow p2_deep p3_memo p4_errors p5_gen p6_types p7_unrelated p8_badkw; do echo "===== $p"; bash 
         71s bash   python3 - <<'PY' import re, pathlib p = pathlib.Path('/tmp/rprobes/p6_types.py') s = p.read_text() s = s.repla
         39s bash   cat > /tmp/rprobes/p3_memo.py <<'PY' import copy  def main() -> None:     a = [1]     m = {}     x = copy.deep
          6s bash   cat > /tmp/rprobes/p11_cycles.py <<'PY' import copy  class Node:     def __init__(self) -> None:         self.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T19:21:10Z
