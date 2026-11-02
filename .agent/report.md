# job job-prog22-11021439  started 2026-11-02T05:41:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `3c9f2aa`.

- Blocking defect: module-level class lists appended/extended in a function are now refused by name and fall back to the general path; `global_maxkey`, append-only, int-key and min-key probes match CPython on both builds.
- Added module-level regression cases to `test_ail_prog22`; corrected `lab/progfix/prog22.md` for g21_002’s actual first reason and the wide-row/general-path claims.
- Tests on final commit: `test_ail_prog22`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (4/4). All 10 `lab/compare` C outputs remain byte-identical; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 7259815, "input": 144673, "output": 13144, "reasoning": 15278, "cache.write": 0, "cache.read": 7086720}]
    tool time: bash 13.4 min
        345s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_prog22 test_ail_sa
        281s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && timeout 2400 python3 tools/p
         82s bash   rm -rf /tmp/p22base /tmp/p22cstab && mkdir -p /tmp/p22base /tmp/p22cstab && git archive HEAD | tar -x -C /tmp/
         15s bash   cat > /tmp/rprobes/global_maxkey_int.py <<'EOF' from dataclasses import dataclass @dataclass class It:     x: 
         13s bash   cat > /tmp/probes/p22_five_param.py <<'EOF' def show(rows: list[tuple[str, str, str, str, str]]) -> None:     
         12s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 2400 python3 test_ail_prog22.py 2>&1 
          8s bash   cat > /tmp/probes/p22_five_future.py <<'EOF' from __future__ import annotations def main() -> None:     rows: 
          7s bash   cat > /tmp/probes/p22_five_str.py <<'EOF' def main() -> None:     rows: list[tuple[str, str, str, str, str]] =

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review 2

**What the change really does:** adds one guard in `_bind_object_types.bind` that refuses a name the function neither binds itself, receives as a parameter, nor finds in `ctx.modconsts` (i.e. a module-level mutable container), so the whole program takes the general path; plus two module-level regression tests, doc corrections and manifest hashes. No program/benchmark edited.

**Claims**
- Module-level class lists appended/extended in a function are refused by name and match CPython on both builds — **verified**: `global_maxkey`, `global_append_only`, `global_maxkey_int`, `global_min_each` all same on `g` and `d`; base default fails on the extend case with `v_gxs undeclared`.
- Same now for `insert`, `return`, nested def and closure mutation of a module-level class list — **verified** (these also failed on base default or fell back identically; HEAD matches CPython on both builds).
- Regression cases added to `test_ail_prog22` — **verified** in the diff and by running it.
- `test_ail_prog22`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass — **verified** (15.8s, 170.6s, 106.7s, 230.2s; 0 failed with `-j 2`).
- g21_002 first reason is `json.dumps of data` — **verified** by compile note.
- Wide all-str annotations (5/6 fields, local/param/literal) refused by name — **verified** on HEAD and on base; note the previous review's "compiles typed as olist" claim does not reproduce on either tree.
- 10 `lab/compare` C outputs byte-identical — **verified** for `main.ail` (all 10 `program.c` `cmp -s`); for `main.py` all buildable ones are identical, and `scar_life`/`tally_lang`/`tree_fold` fail with byte-identical reasons on base and HEAD.
- `update_manifest.py --check` — **verified** OK.

**Pre-existing (not blocking):** `gxs` read-before-assigned fallback for a global read through a parameter helper (same on base); `g_readonly` float/int annotation mismatch (same on base); the three `lab/compare` `.py` builds above.

**Unverified:** NaN sort refusal and the nonexistent programs' typed/general status in `prog22.md` were not re-probed (untouched by this commit); wider suite not run, as instructed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2688318, "input": 230522, "output": 9451, "reasoning": 15705, "cache.write": 0, "cache.read": 2432640}]
    tool time: bash 18.6 min
        448s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cstabpy && mkdir -p /tmp/cstabpy && fails=0; for t in $(ls l
        231s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_fil
        172s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pro
         83s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cstab2 && mkdir -p /tmp/cstab2 && fails=0; for t in $(ls lab
         26s bash   cd /tmp/rprobes2 && for p in g_readonly g_extend g_local_shadow g_strlist g_intlist g_ret g_dict g_globalstmt;
         24s bash   cd /tmp/rprobes2 && for p in g_readonly g_extend g_local_shadow g_strlist g_intlist g_ret g_dict g_globalstmt;
         19s bash   cd /tmp/rprobes2 && for p in g_insert g_passparam g_passparam_read g_const_append g_strconst_append g_read_glo
         18s bash   cd /tmp/rprobes2 && for p in g_insert g_passparam g_passparam_read g_const_append g_strconst_append g_read_glo

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T07:46:59Z
