# job job-prog12-11020843  started 2026-11-01T23:44:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `2c28c6a` on `job-prog12-11020843`.

**Result:** `t338` now builds whole-program typed via a guarded `tuple[int, ...]` local → `list[int]` rewrite, plus itertools alias following. The other four hot functions already built typed (`g15_002`, `t378`, `t018`, and `t338` after the fix); the remaining four need recorded big features (`g10_020`, `t168`, `g17_038`, `t328`).

**Verification**
- Final-commit tests: 9 modules, 0 failed (`test_ail_prog12`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_pre168/101/137`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `test_ail_prog12`: 5 tests, typed `t338` matches CPython on all 3 inputs.
- Probes: 14 `cmp.sh` programs match CPython on both builds; unsafe tuple uses and float tuple locals refuse by name; `t338` stdin and hybrid builds match on all 3 inputs.
- All 10 `lab/compare` tasks keep identical generated C (or identical refusals).
- `lab/progfix/prog12.md` has the profile, per-function reasons, and exact follow-up messages.
[cost $0.1758, opencode tokens {"total": 14711662, "input": 657379, "output": 30571, "reasoning": 28064, "cache.write": 0, "cache.read": 13995648}]
    tool time: bash 32.2 min
        627s bash   cd /home/runner/work/ail-ci/ail-ci && cat >/tmp/prog12/cmpc.py <<'PY' import hashlib, os, shutil, subprocess, 
        563s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -B ../tools/par_check.py -j 2 test_ail_
        413s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -B ../tools/par_check.py -j 2 test_ail_
         53s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/prog12/cmp_probes.log && for p in /tmp/probes/prog12_safe_per
         47s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/prog12/hyb && for f in lab/census/programs/gdev/g10_020.py
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for wt in /tmp/base12 "$PWD"; do d=$(mktemp -d /tmp/tpXXXX); cp lab/corp
         19s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import subprocess,tempfile,os,textwrap,pathlib,sys R=os
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/prog12_float_min.py /tmp/probes/prog12_safe_perm3.p

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Review of `2c28c6a` (prog12)**

**What the change really does:** adds `_rewrite_bare_tuple_locals` (an empty `x: tuple[int, ...]` local becomes `list[int]` when every use passes a whitelist) and makes `itlib.check_nonescaping` follow plain `alias = name` assignments. The report describes this accurately, except its claim that every unsafe use still refuses by name is false: subscript stores/deletes are treated as safe reads.

**Defects**

1. `AIL_CURRENT/python/pkg-v12/pyfunc.py:32657` and `itlib.py:1433` accept a `Subscript` whose context is `Store`/`Del` as a safe read. The guard must also require `isinstance(parent.ctx, ast.Load)`.
2. Alias following at `itlib.py:1448` makes the same hole reachable through an alias.

These are regressions: on the base (`/tmp/rbase`, commit `350d9c1`) all three probes below are refused by name on the typed path (`tuple[int, ...]` / `itertools ... holds a tuple`) and the default build falls back to the general path and matches CPython.

**Probes** (`bash ~/tools/cmp.sh`, head vs base; typed check with `AIL_NO_GENERAL=1`)

| probe | base | head |
| --- | --- | --- |
| p4 alias chain `a=perm; b=a; print(b[0],len(b),...)` | typed refused | typed MATCH |
| p5 `a=perm; print(a)` | typed refused | typed refused by name |
| p6 `a=perm; a[0]=9; print(a[0])` (perm loop) | default MATCH | **default exit 0, 6 × `9`** |
| p11 `last:tuple[int,...]=(); … last[0]=9; print(last[0])` | default MATCH | **typed exit 0, `9`** |
| p18 `last…; del last[0]; print(len(last))` | default MATCH | **typed exit 0, `1`** |
| p13 direct `perm[0]=9` | default already wrong | same (pre-existing) |
| p1,p2,p3,p7,p8,p9,p10,p14,p15,p16,p17 | match or refuse | same |
| t338, 3 task inputs | refused typed | typed, 3/3 MATCH |

**Pre-existing:** direct mutation of a loop target `perm[0]=9` is wrong on the base default build too (p13), so it is not counted against this change.

**Claims checked:** `t338` typed and matching 3 inputs — verified; `g15_002`/`t378`/`t018` typed and `g10_020`/`t168`/`g17_038`/`t328` refused — verified; C unchanged for non-feature programs `g07_020`, `g18_008`, `g10_020`, `t168` — identical; `berth_sim`/`ticket_audit` general C identical, `tree_fold`/`chain_relax` refusals identical; manifest `--check` clean. "Unsafe uses refuse by name" — false (p6/p11/p18). The claimed 14 probes exist in `/tmp/probes` but contain no store/delete cases. Profile table exists; numbers not independently re-derived.

**Tests:** `par_check.py -j 2 test_ail_prog12 test_ail_tuples test_ail_safetynet` → 3 modules, 0 failed.

**Unverified:** profile percentages, the other 6 of the 9 claimed modules, all ten compare tasks individually, instruction-count speed (no gdev program uses the rewritten pattern).

VERDICT: FIX
1. `pyfunc.py:32657` / `itlib.py:1433`: A subscript store or delete is accepted as a safe read. Probe: `last: tuple[int,...] = ()` then `for perm in itertools.permutations(range(1,4)): last = perm`, then `last[0] = 9; print(last[0])` → CPython exit 1, empty stdout (TypeError); AIL typed exit 0, stdout `9`. With `del last[0]; print(len(last))` → CPython exit 1; AIL exit 0, stdout `1`.
2. `itlib.py:1448` alias following exposes the same hole: `for perm in itertools.permutations(range(1,4)): a = perm; a[0] = 9; print(a[0])` → CPython exit 1, empty stdout; AIL typed exit 0, stdout `9` six times. Require the subscript use itself to be in `Load` context (and likewise reject `Del`/`Store`) in both checks.
[cost $0.0365, opencode tokens {"total": 1776692, "input": 71672, "output": 10928, "reasoning": 23692, "cache.write": 0, "cache.read": 1670400}]
    tool time: bash 12.1 min, write 0.0 min
        267s bash   cd /tmp/rprobes && for t in berth_sim chain_relax tree_fold ticket_audit; do d=$(mktemp -d /tmp/cgXXXX); cp /h
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 2400 python3 -B ../tools/par_check.py -j 2 tes
         88s bash   set -e; cd /tmp/rprobes; for t in tree_fold tally_lang; do d=$(mktemp -d /tmp/ccXXXX); cp /home/runner/work/ai
         71s bash   cd /tmp/rprobes && for t in $(ls /home/runner/work/ail-ci/ail-ci/lab/compare/src); do d=$(mktemp -d /tmp/cxXXX
         45s bash   cd /tmp/rprobes && for f in g07_020 g18_008 g10_020 t168; do src=$(ls /home/runner/work/ail-ci/ail-ci/lab/cens
         31s bash   cd /tmp/rprobes && for p in p1_tupleliteral p2_listliteral p3_print_refuse p4_alias_chain p5_alias_print p6_al
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for f in lab/census/programs/gdev/g10_020.py lab/corpus/programs/deepsee
         16s bash   cd /tmp/rprobes && for p in p15_global_alias p16_nested_alias; do for wt in /home/runner/work/ail-ci/ail-ci /t

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `6ffbec4`.

**Changes**
- `pyfunc.py:32657` and `itlib.py:1433`: a subscript use now requires `Load` context, so `Store`/`Del` (`last[0] = 9`, `del last[0]`, augmented stores) no longer count as safe reads, including through an alias.
- Added `test_ail_prog12` T5 covering local and alias store/delete.
- Updated `lab/progfix/prog12.md`, both DEVLOGs, and manifest pins.

**Probes** (`bash ~/tools/cmp.sh`, head build)

| probe | default | typed-only |
| --- | --- | --- |
| store local / delete local / store alias / delete alias / augmented store | match CPython (exit 1, same stdout) | refused exit 3 |
| store through arg / dict value / list item / attribute | match CPython (exit 1) | refused exit 3 |
| safe alias reads (index/len/sum/index/count) | match | typed exit 0, match |

**Verification on final commit**
- Tests: `test_ail_prog12 test_ail_tuples test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 5 modules, 0 failed.
- `tools/update_manifest.py --check` clean.
- 10 `lab/compare` tasks: generated C byte-identical for the 7 that build; the other 3 (`scar_life`, `tally_lang`, `tree_fold`) refuse identically after normalizing the worktree path (no C produced on either side).
[cost $0.0217, opencode tokens {"total": 1169362, "input": 73139, "output": 7182, "reasoning": 5265, "cache.write": 0, "cache.read": 1083776}]
    tool time: bash 21.9 min, edit 0.0 min
        482s bash   cd /tmp && rm -rf cdiff && mkdir cdiff && cd cdiff && for t in $(ls /home/runner/work/ail-ci/ail-ci/lab/compar
        429s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -B ../tools/par_check.py -j 2 test_ail_
        353s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -B ../tools/par_check.py -j 2 test_ail_
         32s bash   cd /tmp/probes && : > cmp_fix.log && for p in fix_store_local fix_delete_local fix_store_alias fix_delete_alia
          7s bash   cd /tmp/cchk && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile /hom
          4s bash   cd /tmp/probes && for p in fix_store_local fix_delete_local fix_store_alias fix_delete_alias fix_aug_store_loc
          1s bash   cd /tmp/probes && d=$(mktemp -d /tmp/tpsXXXX) && cp fix_safe_alias_read.py $d/p.py && cd $d && AIL_NO_CACHE=1 
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1 skipped: only 12 minutes left

FINAL VERDICT: FIX  2026-11-02T04:27:05Z
