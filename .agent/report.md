# job job-mem1-11011013  started 2026-11-01T01:14:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done and committed as `ba24cdc`.

- **tree_fold peak RSS: 603.7 MiB → 450.2 MiB** (Rust 314.8 MiB). Allocator peak live: 689.6 → 470.3 MiB; 257 fewer allocation calls. Details in `docs/design/MEM_TREEFOLD.md`.
- **All 10 lab/compare tasks**: stdout/exit code identical on every public and hidden case; no task's peak RSS rose beyond a 4 KiB page quantum.
- **Probes**: `p_slist_append`, `p_slist_comp`, `p_slist_routes`, `p_slist_lastuse`, `p_list_append_reserve` all match CPython on default, general, and `AIL_IR=0` builds.
- **Tests passed**: `test_ail_slist_reserve`, `test_ail_last_use_free`, `test_ail_memory_shapes`, `test_ail_list_ops`, `test_ail_sort_keys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; manifest check passes.
- **icount**: unavailable on this runner (`perf_event_open` EACCES, paranoid=4; no valgrind). Reported explicitly, with no instruction-count claim.
[cost $0.0906, opencode tokens {"total": 8926547, "input": 196659, "output": 23418, "reasoning": 34982, "cache.write": 0, "cache.read": 8671488}]
    tool time: bash 54.1 min
        735s bash   cd /home/runner/work/ail-ci/ail-ci for t in chain_relax ledger_bin scar_life term_rank ticket_audit; do   echo
        646s bash   cd /home/runner/work/ail-ci/ail-ci for t in berth_sim echo_pack rail_transfer tally_lang; do   echo "=== curre
        596s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | ta
        268s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | ta
        185s bash   cd /tmp/ail-base for t in ledger_bin echo_pack; do python3 lab/compare/run_task.py --task $t --langs ail --ico
        150s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_slist_reserve test_ail_last_use_free test_ail_memory_shapes 
        118s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/compare/run_task.py --task tree_fold --langs ail,rust -
        116s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task tree_fold --langs ail,rust --icou

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does.** Adds `ail_slist_reserve` (exact-size spine), uses it for `list[str]` comprehensions (legacy + IR), adds a legacy append-loop reserve for `list[int]`/`list[float]`/`list[str]` after an immediately-preceding empty/clear, and adds `list[str]` to last-use release in both emitters. No task or bench source changed. Report matches the diff, except "append loop whose range bounds are known" only recognises constants and *local* int names, not parameters; and it reserves the full `range()` trip count even when the body can exit or skip appends.

**Probes** (`bash ~/tools/cmp.sh`, general + default; base comparison for failures):

| probe | result |
|---|---|
| p1 break/clear, p2 positive/negative steps, p3 comp filters/slices, p4 slice-copy ownership, p5 alias via return arg, p6 dict/attr sources, p7 last use in branch, p8 numeric append | match CPython, exit 0 |
| p9 huge param bound + break | match (reserve not emitted for param bounds) |
| **p10 local `m=n`, `range(m)`, break, n=2^61** | **default build dies "list too long", exit 1; base and CPython print `v`, exit 0** |
| **p11 literal `range(10**17)`, break** | **default build prints nothing, exit 1 `out of memory`; base and CPython print `v`, exit 0** |
| p12 huge literal int list + break | matched (default took IR, no append reserve) |

Scalar program with no lists: generated C byte-identical to `work`.

**Tests.** `test_ail_slist_reserve` ok (2.6s), `test_ail_safetynet` ok (174s), `update_manifest.py --check` rc 0.

**Measurements.** tree_fold typed: base 619,120 KiB → HEAD 461,056 KiB (RSS), wall 1861.8 → 1701.8 ms; all 55 public+hidden cases match, typed path. I could not run `tools/icount` (paranoid=4, no valgrind); wall time improved, no slowdown seen. Other nine tasks not re-run by me.

**Claims:** tree_fold RSS/cases verified; no task source changed verified; manifest/tests verified; icount unavailability verified; "all 10 tasks" and the worker's five probe files unverified; "append loop range bounds known" is **overstated** (parameter bounds silently get no reserve, and early exit/conditional append over-reserves).

**Unverified:** the other nine lab/compare tasks' stdout/RSS; allocation-call count; the worker's own probe files.

### Defect 1 — append-loop reserve is sized to the full range even when the loop exits early
`pyfunc.py:_append_loop_reserve` accepts a body whose only mentions of the target are `.append(...)`; `break`/`return`/conditional appends are not mentions, so it emits `ail_slist_reserve(&xs, 100000000000000000)` and the runtime tries a ~2.4 EB `realloc`.

Probe `/tmp/rprobes/p11_literal_overreserve.py`:
```python
def f() -> list[str]:
    xs: list[str] = []
    for i in range(100000000000000000):
        xs.append("v")
        break
    return xs

def main() -> int:
    print("|".join(f()))
    return 0

main()
```
- Expected (CPython, `work`, general path): stdout `v\n`, exit 0.
- Actual (HEAD default/typed build): stdout empty, exit 1, stderr `out of memory`.
- Confirmed generated C at HEAD: `ail_slist_reserve(&v_xs, 100000000000000000);` before the loop.

Same root cause with `range(2305843009213693952)` dies `list too long` (p10). Fix: only reserve when the body cannot leave/skip the append (no `break`/`return`/`raise`/`continue`, appends unconditional), or clamp the reserve to a sane bound.

**Pre-existing:** none found.

VERDICT: FIX
1. `_append_loop_reserve` over-reserves the whole `range()` trip count when the loop exits early or appends conditionally, causing a runtime `out of memory`/`list too long` (exit 1) where CPython and the base build succeed: probe `/tmp/rprobes/p11_literal_overreserve.py` expected `v` exit 0, HEAD default got empty stdout exit 1.
[cost $0.0621, opencode tokens {"total": 5651294, "input": 133585, "output": 11052, "reasoning": 31713, "cache.write": 0, "cache.read": 5474944}]
    tool time: bash 6.4 min
        176s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_slist_re
         82s bash   cd /tmp/base && date && timeout 700 python3 lab/compare/run_task.py --task tree_fold --out /tmp/tf_base.json -
         81s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 600 python3 lab/compare/run_task.py --task tree_fold --o
         22s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; timeout
          5s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/tfd && mkdir /tmp/tfd && cd /tmp/tfd && AIL_NO_CACHE=1 python3
          2s bash   cd /tmp/base; date; timeout 240 bash ~/tools/cmp.sh /tmp/rprobes/p10_local_overreserve.py "$PWD" 2>&1 | tail -
          2s bash   cat > /tmp/rprobes/p12_int_overreserve.py <<'EOF' def f() -> list[int]:     xs: list[int] = []     for i in ra
          2s bash   sed -i 's/f(1099511627776)/f(2305843009213693952)/' /tmp/rprobes/p9_overreserve.py; grep -n "f(" /tmp/rprobes/

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the reviewer's defect and committed as `56f7270`.

**Fix**
- `_append_loop_reserve` now refuses any loop body containing `break`/`continue`/`return`/`raise`/`yield`/`assert`, a nested `if`/loop/`try`/`match`/`with`, or an append that is not a whole expression statement.
- Reserve is capped at `2^22` elements, so an early exception cannot force a huge allocation.
- Corrected the overstatement about range bounds in `docs/design/MEM_TREEFOLD.md`; added a DEVLOG entry.

**Probes** (`bash ~/tools/cmp.sh`, general + default): all matched CPython.
- `p_append_early.py`, `p_append_types.py`, `p_append_routes.py`, `p_append_comp.py` — exit 0, same stdout.
- `p_append_raise.py` — both exit 1, same empty stdout.
- Reviewer probes `p10_local_overreserve.py` and `p11_literal_overreserve.py` — now print `v`, exit 0 (previously `out of memory`/`list too long`).

**Tests** (final code): `test_ail_slist_reserve`, `test_ail_last_use_free`, `test_ail_memory_shapes`, `test_ail_list_ops`, `test_ail_sort_keys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass. `update_manifest.py --check` rc 0.

**tree_fold** (typed, 55/55 cases): 618,160 KiB baseline → 475,680 KiB on this run (460,992 KiB in the earlier run; generated C is unchanged because its spine comes from a comprehension, so the difference is runner noise). Icount remains unavailable (`perf_event_paranoid=4`, no valgrind), reported not hidden.
[cost $0.0365, opencode tokens {"total": 2463527, "input": 79978, "output": 12070, "reasoning": 17047, "cache.write": 0, "cache.read": 2354432}]
    tool time: bash 11.3 min, edit 0.0 min
        416s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         80s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 700 python3 lab/compare/run_task.py --task tree_fold --langs ail
         79s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 700 python3 lab/compare/run_task.py --task tree_fold --l
         66s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_append_early.py /tmp/probes/p_append_types.py /tm
          5s bash   cd /tmp && rm -rf tfc && mkdir tfc && cd tfc && timeout 300 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURREN
          5s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && cd AIL_CURRENT && timeout
          4s bash   cat > /tmp/probes/p11_literal_overreserve.py <<'EOF' def f() -> list[str]:     xs: list[str] = []     for i in

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: mem1 (tree_fold peak memory)

**What the diff really does:** adds an exact-size `ail_slist_reserve` used for `list[str]` comprehensions and for append loops whose target was emptied immediately before and whose body is only whole-statement `xs.append(...)` (second commit restricts this and caps the append-loop reserve at 2^22), plus last-use freeing of `list[str]` locals in both emitters. Report matches this, except the cap claim below.

**Defect (new, caused by this change): uncapped reserve in `list[str]` comprehensions.**
The comprehension reserve in `pyfunc.py:19237` and `ir/lower.py:1495` was extended to `SLIST` with `extra = n - lo` and no 2^22 cap, unlike the append-loop fix. A huge `range` bound therefore forces `list too long`/`out of memory` *before* an early exception can be raised, where base and CPython print the caught result.

Probe `/tmp/rprobes/p7_comp_huge_raise2.py`:
```python
def boom(i: int) -> str:
    if i >= 0:
        raise ValueError("x")
    return "y"
def f(n: int) -> list[str]:
    xs: list[str] = [boom(i) for i in range(n)]
    return xs
def main() -> int:
    try: f(1000000000000000000)
    except ValueError: print("caught")
    return 0
main()
```
- CPython: exit 0, stdout `caught`.
- HEAD default build (`cmp.sh`): exit 1, stderr `list too long`, stdout empty.
- Base (`/tmp/base`): exit 0, stdout `caught`.
- Typed `AIL_NO_GENERAL=1 AIL_IR=0` and `IR=1` both fail; `/tmp/rprobes/p7b_comp_huge_raise3.py` with `n=10**12` gives `out of memory` instead.
- Generated C confirms `ail_slist_reserve(&v__t1, (v__t2) - (0));` before the loop.

**Verified**
- Append-loop refusals and cap: `/tmp/rprobes/p4_breaks.py`, `/tmp/rprobes/p8_append_huge_raise2.py` match CPython on both IR emitters; the 4M cap does not raise RSS (1324 KiB both builds).
- Last-use free of `list[str]`: `/tmp/rprobes/p6_lastuse_alias.py`, `p10_struct_field.py`, `p11_lastuse_ops.py` match CPython, IR=0 and IR=1.
- No-feature program: `--debug-dir` C byte-identical to base for both IR emitters.
- `test_ail_slist_reserve` and `test_ail_safetynet` pass (174 s); `update_manifest.py --check` rc 0.
- tree_fold on HEAD: 55/55 cases ok, typed path, peak RSS 474,604 KiB (report 475,680; doc baseline 618,160) — improvement confirmed.
- icount genuinely unavailable: `perf_event_paranoid=4`, no valgrind.

**False/overstated claim:** "Reserve is capped at 2^22 elements, so an early exception cannot force a huge allocation" is true only for append loops; comprehensions are uncapped (defect above). The added tests cover only append-loop early exits, not comprehension ones.

**Pre-existing:** `list[int]` comprehension with the same huge-bound/early-exception shape also dies on `/tmp/base` (`p7c_intcomp_huge_raise.py`), so the class is old; only the `list[str]` instance is new.

**Unverified:** the report's "all ten lab/compare tasks" stdout/RSS sweep; I ran only tree_fold. Instruction-count comparison (tool cannot run here).

VERDICT: FIX
1. **Comprehension reserve is uncapped for `list[str]`.** Probe `/tmp/rprobes/p7_comp_huge_raise2.py` (and `p7b_comp_huge_raise3.py`): expected CPython/base exit 0 with stdout `caught`; actual HEAD default and typed builds exit 1 with stdout empty and stderr `list too long` / `out of memory`. Cap or bound the comprehension reserve the same way as `_append_loop_reserve`, and add a comprehension early-exception case to `test_ail_slist_reserve`.
[cost $0.0464, opencode tokens {"total": 2974638, "input": 89722, "output": 11491, "reasoning": 29265, "cache.write": 0, "cache.read": 2844160}]
    tool time: bash 5.0 min, write 0.0 min
        175s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         80s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 700 python3 lab/compare/run_task.py --task tree_fold --lan
         14s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1_comp_huge_raise.py /tmp/rprobes/p2_comp_h
          7s bash   date; for p in p4_breaks p5_multi_append p6_lastuse_alias p8_append_huge_raise2 p9_misc; do for ir in 0 1; do 
          4s bash   date; cd /home/runner/work/ail-ci/ail-ci && echo "=== HEAD cmp p7" && timeout 400 bash ~/tools/cmp.sh /tmp/rpr
          2s bash   cat > /tmp/rprobes/runtyped.sh <<'EOF' #!/bin/bash # runtyped.sh SRC WORKTREE IR src=$1; wt=$2; ir=${3:-0} d=$
          2s bash   date; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$(basename $wt); for ir in 0 1; do d=/tmp/no
          2s bash   date; for ir in 0 1; do echo "=== p9b HEAD IR=$ir"; timeout 300 bash /tmp/rprobes/runtyped.sh /tmp/rprobes/p9b

FINAL VERDICT: FIX  2026-11-01T02:46:22Z
