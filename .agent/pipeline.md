# job job-pyreachs1-11031557  started 2026-11-03T06:57:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both remaining review defects on `job-pyreachs1-11031557`, committed as `60cf446`.

- Nested dict-of-lists: `lower_dict_of_lists` now leaves `d = {}` as written when any nested function/class references `d`; `r_dl_nested_read` prints CPython's `inner 7` / `outer 7` on both builds.
- Bytearray alias: a bytearray is passed to a `bytes` parameter only when the callee is a proven read-only consumer; otherwise a named refusal keeps the general path. `r_ba_store` and `r_ba_alias` now match CPython, including post-mutation output.

Probes `r_ba_store`, `r_ba_alias`, `r_ba_slice2`, `r_ba_int`, `r_ba_lenonly`, `r_ba_bytes`, `r_dl_nested_read`, `r_dl_nested_unrelated`, `r_dl_nested_both` all match CPython on default and unified builds. `echo_pack` remains typed with all 57 cases correct. `test_ail_pytyped_reach`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed. Manifest check exits 0; codegen pins and all ten `lab/compare/src/*/main.ail` hashes are unchanged.
[cost $0.0000, opencode tokens {"total": 3397140, "input": 106930, "output": 8481, "reasoning": 14529, "cache.write": 0, "cache.read": 3267200}]
    tool time: bash 8.3 min, edit 0.0 min, read 0.0 min
        241s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pytyped_re
        145s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/compare/run_task.py --task echo_pack --l
         41s bash   cd /tmp/probes && cat > r_ba_slice2.py <<'EOF' import sys  def keep(data: bytes) -> bytes:     return data  de
         31s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/codegen_diff.py --pins 2>&1 | tail -30 && args=(); for f i
         21s bash   for p in r_dl_nested_read r_ba_store r_ba_alias; do echo "######## $p"; timeout 180 bash ~/tools/cmp.sh /tmp/p
         14s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > r_dl_nested_read.py <<'EOF' def main():     d = {}     def sho
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/codegen_diff.py 2>&1 | tail -30
          1s bash   cd /tmp && rm -rf strictprobe && mkdir strictprobe && cd strictprobe && for p in r_ba_store r_dl_nested_read; 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change really does.** Adds a nested-scope dependency guard to `lower_dict_of_lists` (`ail_syntax.py:4420`): if any nested `def`/`async def`/`class` mentions the dict name, that `d = {}` is left as written. Adds a named refusal in `_call_user_func` (`pyfunc.py:16582`): a bytearray argument to a `bytes` parameter is accepted only when the callee is a proven read-only scalar consumer; otherwise the general path is kept (and `--strict` reports the refusal). Matches the report.

**Checks run.** `date` 07:10. Exact review probes: `r_dl_nested_read`, `r_ba_store`, `r_ba_alias` match CPython on both builds on HEAD; all three fail on `/tmp/base` exactly as the review said. Ran the worker's six other probes plus ~25 of my own covering nested def/class/lambda/comprehension/shadowing/argument/attribute/dict shapes and bytearray through arguments, list items, dict values, slices, keywords, callbacks, aliases, redefinition, constructor fields, mutation-during-call, and explicit `bytes(a)`. All match CPython or are named refusals. `test_ail_pytyped_reach`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` exits 0. Five codegen pins and all ten `lab/compare/src/*/main.ail` `to_c` hashes equal `work`; `program.c` for no-feature `.py` probes is byte-identical to base.

**Report claims.** Verified: nested dict-of-lists fix; bytearray alias fix (default general-path note names the copy, strict refuses); all named probes pass on both builds; echo_pack stays typed with 57/57 cases; four test modules pass; manifest check 0; pins and ten `.ail` hashes unchanged. `tools/codegen_diff.py --pins` itself errors in this tree (argparse has no `--pins`), a pre-existing tool issue; the default invocation verifies the pins.

**Notes (non-blocking).** A nested scope that merely *shadows* the dict name (e.g. `def f(d): ...`) now also disables lowering, so a program typed on base becomes a named strict refusal / general path on HEAD (`p_dl_nested_shadow`: base strict exit 0, HEAD strict exit 3). Output is still CPython-identical; this is the conservative refusal the task permits. icount is unverified: `perf_event_open` is permission-denied here; the change is compile-time only and echo_pack is typed 57/57 (wall 3185 ms vs 688 ms for `.ail`).

**Pre-existing.** Duplicate module-level `def` names and nested classes are named refusals on both HEAD and base.

**Unverified.** Instruction-count ratio (perf unavailable); non-paren dict shapes beyond the probes above; lab `.py` tasks other than echo_pack.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3529721, "input": 46199, "output": 11472, "reasoning": 28466, "cache.write": 0, "cache.read": 3443584}]
    tool time: bash 14.7 min
        159s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --la
        141s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
        135s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         75s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in p_ba_return_slice p_ba_list_item p_ba_dict_value p_ba_ali
         40s bash   cd /tmp/rprobes && cat > p_ba_cond.py <<'EOF' def keep(data: bytes) -> bytes:     return data  def main():    
         39s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r_ba_slice2 r_ba_int r_ba_lenonly r_ba_bytes r_dl_nested_
         35s bash   cd /tmp/rprobes && cat > p_ba_slice_nonconsumer.py <<'EOF' def keep(data: bytes) -> bytes:     return data  de
         31s bash   date; cd /home/runner/work/ail-ci/ail-ci && args=(); for f in lab/compare/src/*/main.ail; do args+=(--source "

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T08:47:13Z
