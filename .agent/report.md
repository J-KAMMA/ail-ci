# job job-rc3-11061458  started 2026-11-06T06:03:02Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `db51b53`.

Defects addressed:
- Cursor locals were added to `borrowed_aliases` after body emission, so loop binds still retained while exit/cleanup releases were elided: fixed by threading a separate `cursor_locals` set through binding, element reads, loop-point releases and exit cleanup.
- List cursors in `borrowed_aliases` made the IR reject `field_alias_local` / grid functions: cursor locals are now kept out of that legacy set, so the IR path is restored.
- Added a conservative refusal when an element cursor’s owner list is passed to a non-read-only call, preserving the expected owning reference in `test_ail_borrowed_owner`.

Verification:
- `test_ail_ir_cover`, `test_ail_ir_s3b`, `test_ail_obj_refs`, `test_ail_typed_inherit`: 0 failed.
- `test_ail_rc_cursor`, `test_ail_borrowed_owner`, `test_ail_rc_borrow`, `test_ail_borrowed_element_fields`, `test_ail_callable_owned_results`, `test_ail_exception_resources`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 0 failed.
- 6 probes matched CPython in both `g`/`d` builds and the `AIL_RC_BORROW=0` builds; `p_list_elem_write` matches CPython’s expected exit 1.
- `tools/update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 8406387, "input": 177094, "output": 15291, "reasoning": 36082, "cache.write": 0, "cache.read": 8177920}]
    tool time: bash 23.0 min, write 0.0 min
        218s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_rc_
        200s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_rc_
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_ir_
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_rc_
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_rc_
        166s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_RC_BORROW=0 timeout 1600 python3 ../tools/par_check.py -
        136s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_rc_
         84s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 1 test_ail_typ

## review 0
[model opencode/deepseek-v4.1-flash-free]
## What the change really does

Separates rc3's cursor set from rc2's `borrowed_aliases` (so the IR no longer refuses a list whose local is a cursor), threads `cursor_locals` through the same emit sites (loop bind, element read, loop-point and exit release, `object_refs`), and adds a conservative refusal when an element cursor's owner list is passed to a non-read-only call. Adds one test, refreshes `RESULTS_CURSOR.md` and the manifest. Matches the report.

## Probes (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, g + d)

| probe | shape | result |
|---|---|---|
| p1_elem_walk | `for item in items`, `len(items)` in loop | equal both builds; stderr/build clean |
| p2_elem_owner_readcall | owner list passed to user `count(items)` | equal both builds; HEAD now owning (store+release), base elided |
| p3_elem_owner_mutate | callee clears owner list | equal both builds; owning in both |
| p4/p5/p6 | field cursor, nested-loop cursor, `p = item` alias | equal both builds |
| p8_finally | cursor bound in try, finally writes field | equal both builds |
| p9/p10/p11 | owner local/param rebound while cursor live | equal both builds (see Pre-existing) |
| p12_elem_index | `p = items[i]` cursor | equal; C identical HEAD/base |
| p13/p14 | list-field alias then mutate/clear | equal both builds |
| p7_no_feature, g00_000, g00_002 | no feature | `program.c` byte-identical HEAD vs base |
| p1/p3/p12 with `AIL_RC_BORROW=0` | escape hatch | equal both builds |

No wrong output, crash or exit-status difference was caused by the change.

## Tests / speed

- `par_check -j 2 test_ail_rc_cursor test_ail_safetynet test_ail_ir_cover test_ail_ir_s3b test_ail_obj_refs test_ail_typed_inherit`: 6 modules, 0 failed.
- `test_ail_borrowed_owner test_ail_rc_borrow test_ail_borrowed_element_fields test_ail_files test_ail_corpus_findings3`: 5 modules, 0 failed.
- Base `work` fails `test_ail_ir_cover` (`'legacy' != 'ir'`, reason “list 'bs' is a borrowed_aliases list”) and `test_ail_obj_refs`; HEAD passes — the fix is real, not a test relaxation.
- `update_manifest.py --check` rc 0.
- linkedlist / binarytrees / rbtree `program.c` identical HEAD vs base (same retain/release/obj-store counts), so no hot-code regression from this commit. `icount` not run (needs a PMU this runner lacks).

## Claim check

- Separate cursor set, threaded through bind/read/loop release/exit cleanup: **verified** in the diff and by identical C on accepted walks; the report's “loop binds retained while exit releases elided” symptom did not reproduce on my probes (base C was already identical there), so that specific pre-fix bug is **unverified**.
- IR path restored for list cursors: **verified** (base test_ail_ir_cover failure gone).
- Owner-list non-read-only-call refusal preserves owning reference: **verified** (p2 store+release on HEAD vs elision on base; `test_ail_borrowed_owner` passes).
- All listed modules 0 failed: **verified** (11 modules re-run here).
- 6 worker probes + `p_list_elem_write`, `update_manifest --check`: **partially verified** — manifest verified; probes not available, but 14 equivalent probes of mine all equal.

## Pre-existing

- Cursor root rebinding is not refused: for `n = x.next; x = Node(...)` the emitted C keeps `n` as a plain pointer while the old `x` is released (same C/behavior on base). My probes still printed the CPython value, so this latent use-after-free is pre-existing and not demonstrated to produce wrong output.
- A list alias/field (`bs = ru.b`) is classified as a cursor; HEAD no longer excludes it from `object_refs`. p13/p14 match CPython in both builds; leak-check not run.

## Unverified

- Valgrind/leak cleanliness, `icount`, 20 CI shards, full 200-corpus run, and the worker's own six probes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1407909, "input": 72374, "output": 8705, "reasoning": 18926, "cache.write": 0, "cache.read": 1307904}]
    tool time: bash 7.2 min
        229s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_rc_
        142s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_borr
         17s bash   cd /tmp/base/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_ir_cover test_ail_obj_refs
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" 
          7s bash   cat > /tmp/rprobes/p13_list_alias.py <<'EOF' from __future__ import annotations  class Holder:     def __init_
          5s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1_elem_walk.py /tmp/rprobes/p3_elem_owner_mutate.
          3s bash   cd /tmp && rm -rf cdiff && mkdir cdiff && cd cdiff for w in head base; do   wt=/home/runner/work/ail-ci/ail-ci
          3s bash   cd /tmp/cdiff for b in linkedlist binarytrees rbtree; do   for w in head base; do wt=/home/runner/work/ail-ci/

## full suite
test_ail_borrowed_elements

## suite fix skipped: only 144 minutes left

FINAL VERDICT: FIX  2026-11-06T08:38:23Z
