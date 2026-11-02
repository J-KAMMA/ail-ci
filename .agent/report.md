# job job-prog23-11021359  started 2026-11-02T05:07:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed on `job-prog23-11021359` (`8044266`, manifest pin `9ea3013`).

- **Hot functions:** profiled all 8; 4 were already fully typed. `t115` and `t143` now compile fully typed (`--strict` succeeds); `g15_004` and `g25_026` remain follow-ups with exact reasons in `lab/progfix/prog23.md`.
- **Compiler fixes:** tuple/list targets from matching tuple/list expressions; conditional numeric-list branches; int-keyed unannotated set operators. Str/bytes-keyed sets stay on the general path, avoiding an int-table codegen regression.
- **Verification:** 49 probes in `/tmp/probes23` + `/tmp/probes/prog23_*` all match CPython on both builds. All 10 `lab/compare` tasks have byte-identical generated C (`AIL_IR=0`).
- **Tests:** 58 tests across `test_ail_prog23`, `typedreach1/2`, `cpython_hybrid`, `safetynet`, `files`, `corpus_findings3` passed (1 skipped); `test_ail_manifest_compiler` passed; `update_manifest.py --check` passes.
[cost $0.0924, opencode tokens {"total": 8580729, "input": 262547, "output": 16560, "reasoning": 30390, "cache.write": 0, "cache.read": 8271232}]
    tool time: bash 28.9 min
        692s bash   python3 -m unittest -q test_ail_prog23 test_ail_typedreach1 test_ail_typedreach2 test_ail_cpython_hybrid test_
        387s bash   python3 -m unittest -q test_ail_prog23 test_ail_manifest test_ail_typedreach1 test_ail_typedreach2 test_ail_cp
        192s bash   : > /tmp/probes/all23_results.txt for f in /tmp/probes23/*.py /tmp/probes/prog23_*.py; do   echo "=== $(basena
        121s bash   rm -rf /tmp/ccmp23 && mkdir -p /tmp/ccmp23 fail=0 for src in lab/compare/src/*/main.ail; do   t=$(basename $(d
         70s bash   : > /tmp/probes/prog23_results.txt for f in /tmp/probes/prog23_*.py; do   echo "=== $(basename $f)" >> /tmp/pr
         62s bash   : > /tmp/probes23/cmp_results.txt for f in /tmp/probes23/*.py; do   echo "=== $(basename $f)" >> /tmp/probes23
         59s bash   for f in /tmp/probes/prog23_set_str.py /tmp/probes/prog23_set_bytes.py /tmp/probes/prog23_set_alias.py /tmp/pr
         45s bash   for f in /tmp/probes/prog23_set_str.py /tmp/probes/prog23_set_bytes.py /tmp/probes/prog23_ifexp_nonlist.py /tm

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** It extends typed-path inference in three places: tuple/list targets bound from same-shape tuple/list expressions (`iterlower.py`), conditional expressions whose branches are numeric lists (`_numeric_field_kind`), and unannotated int-keyed set operators (`& | - ^`), including a scan that keeps str/bytes-keyed sets on the general path.

**Probes.** I wrote and ran 144 probes in `/tmp/rprobes` on HEAD and, where they failed or exercised the new path, on a fresh `/tmp/rbase23` worktree at `work`. Coverage: empty/negative/int64/bool/float/tuple/mixed sets; all four operators; aliases, mutation, rebinding, iteration; conditionals with empty/mixed/list-var/field/float branches; tuple/list targets with slices, literals, comprehensions, calls, starred/nested/mismatched targets; values through arguments, list items, attributes and dict values. All matched CPython except one new defect below. One new failure was found; several failures were identical on base (listed under Pre-existing).

**Tests.** `test_ail_prog23` and `test_ail_safetynet` pass (41 s / 169 s); additionally `test_ail_sets_general` and `test_ail_tuples` pass. `tools/update_manifest.py --check` passes.

**Claim check.**
- t115/t143: base `--strict` refuses (with the reported messages), HEAD `--strict` succeeds — verified.
- g02_026, t102, t069, g18_030 already typed on base — verified.
- g15_004/g25_026 first reasons are exactly as reported — verified.
- All ten `lab/compare` generated `program.c` files byte-identical to base — verified.
- “Both changes affect only programs that previously were refused”: **false** — the probe below was accepted via the general fallback before and now fails to build.
- Worker’s 49 probes and profiling timings: **unverified** (not re-run; no exact copy checked).

**Pre-existing (identical on base).** Float-keyed unannotated sets print ints (`set_call_float`); bool-set repr/order differs; `set(map(str,...))`, `set()`+`.add(str)`, shadowed `set` cases fail in both builds; unsorted set printing/iteration order differs in both builds; mixed int/float conditional list fails C compilation in both builds.

**Unverified.** Instruction counts (`tools/icount.c`) — `perf_event_open` returned “Permission denied” on this runner. Profile percentages were not recomputed.

VERDICT: FIX
1. A name first bound to a str-keyed unannotated set and later rebound to an int set-operator result makes the default build emit invalid C (general build and CPython are correct; base succeeds). Probe `/tmp/rprobes/rebind_strset_to_intset_op.py`:
   ```python
   def run() -> None:
       c = set(["x", "y"])
       print(sorted(c))
       a = set([1, 2])
       b = set([2, 3])
       c = a & b
       print(sorted(c))
   run()
   ```
   Expected (CPython, and base default build): `['x', 'y']` then `[2]`. Actual (HEAD default build): compilation fails with `incompatible type for argument 2 of 'ail_tab_put'` (`expected 'int64_t' ... argument is of type 'ail_str'`); the forced typed set result does not account for the destination name’s existing `ail_stab` binding. Same failure with the str binding in a branch (`/tmp/rprobes/rebind_strset_branch_then_op.py`) and with `|`, `-`, `^`; the reverse order (int set then str set operator) is fine.
[cost $0.0804, opencode tokens {"total": 7224272, "input": 153594, "output": 21595, "reasoning": 39035, "cache.write": 0, "cache.read": 7010048}]
    tool time: bash 21.5 min, write 0.0 min
        209s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_sets_general 
        170s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_prog23 test_a
        126s bash   mkdir -p /tmp/rprobes/out; cd /home/runner/work/_temp/w2; ls /tmp/rprobes/*.py | grep -v gen.py | xargs -P2 -I
        125s bash   cd /tmp/rbase23; ls /tmp/rprobes/*.py | grep -v gen.py | xargs -P2 -I{} bash -c 'n=$(basename {} .py); bash ~/
         91s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmphead /tmp/cmpbase && mkdir -p /tmp/cmphead /tmp/cmpbase && for
         77s bash   python3 /tmp/rprobes/gen9.py; cd /home/runner/work/_temp/w2; for n in strset_split strset_literal_list strset_
         63s bash   python3 /tmp/rprobes/gen11.py; cd /home/runner/work/_temp/w2; for n in rebind_strset_to_intset_literal rebind_
         61s bash   python3 /tmp/rprobes/gen4.py; cd /home/runner/work/_temp/w2; for n in set_add_str set_add_bytes set_add_int se

## fix round skipped: only -29 minutes left

FINAL VERDICT: FIX  2026-11-02T10:31:36Z
