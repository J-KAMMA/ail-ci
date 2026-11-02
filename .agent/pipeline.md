# job job-mem1-11020654  started 2026-11-01T21:55:07Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect.

- Capped comprehension reserves at 2^22 in both emitters (`pyfunc.py`, `ir/lower.py`), sharing `_LIST_RESERVE_LIMIT` with the append-loop path.
- Added `comp_early` / `comp_early_arg` early-exception regression cases to `test_ail_slist_reserve`.
- Probes p7, p7b, p7c, p7d match CPython on default/general builds and typed `AIL_IR=0/1`; huge bounds now print `caught` instead of dying with `list too long` / `out of memory`.
- Tests passed: `test_ail_slist_reserve`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- Ran `tools/update_manifest.py` and `--check` (rc 0). Updated DEVLOG and `docs/design/MEM_TREEFOLD.md`.
- Committed as `1f1c78f`.
[cost $0.0000, opencode tokens {"total": 1538489, "input": 55520, "output": 7562, "reasoning": 6991, "cache.write": 0, "cache.read": 1468416}]
    tool time: bash 9.3 min
        533s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for m in test_ail_safetynet test_ail_files test_ail_corpus_f
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p7_comp_huge_raise2 p7b_comp_huge_raise3 p7c_intcomp_huge_raise
          5s bash   cat > /tmp/probes/p7d_comp_normal.py <<'EOF' def f(n: int) -> list[str]:     xs: list[str] = ["v" + str(i) for
          5s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p7_comp_huge_raise2 p7b_comp_huge_raise3 p7c_intcomp_huge_raise
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_slist_reserve
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.re
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/p
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -8 && ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: mem1 (cap comprehension reserve)

**What the diff really does:** caps the one-shot comprehension reserve at 2^22 in both emitters (`pyfunc.py`, `ir/lower.py`), sharing `_LIST_RESERVE_LIMIT` with the append-loop path, and adds two SLIST early-exception test cases. It applies the cap to `list[int]`/`list[float]` as well as `list[str]`, which is not what the defect required and is where it breaks.

**Defect 1 (new, caused by this change): the legacy emitter's indexed `list[int]`/`list[float]` comprehension writes past a capped buffer.**
In `pyfunc.py`, an unfiltered counted comprehension with a safe element expression (`indexed`) deliberately skips the push capacity check and does `c.p[c.n++] = val`, relying on the reserve being exactly the trip count. Capping that reserve to 2^22 breaks the invariant: the loop still runs to the real bound, so a comprehension of more than 2^22 elements overflows the heap.

Probe `/tmp/rprobes/p7_bigcomp.py`:
```python
def main() -> int:
    xs: list[int] = [i for i in range(32000000)]
    print(len(xs))
    print(xs[31999999])
    return 0
main()
```
- CPython: exit 0, stdout `32000000` / `31999999`.
- Base typed IR=0 (`AIL_NO_GENERAL=1 AIL_IR=0`): exit 0, same stdout.
- HEAD typed IR=0: exit 139 (SIGSEGV), stdout empty.
- HEAD typed IR=1 and default/general builds: correct.
- Generated HEAD IR=0 C: `ail_list_reserve(&v__t1, ((v__t2) - (0)) < 4194304 ? ((v__t2) - (0)) : 4194304); for (...) { ... v__t1.p[v__t1.n++] = _comp_element3; }` — 32M direct stores into a 4M buffer.
- This also hits `lab/compare/src/echo_pack/main.ail` (`let prev = [-1 for _ in range(n)]`, perf `n = 32,000,000`) on the typed IR=0 build. `p6_over_cap.py` (4,194,305) “passes” only because the overflow is one element; it is still UB.

**Defect 2 (same root cause): cap on `list[int]`/`list[float]` comprehensions raises peak RSS for legitimate large comprehensions.**
`echo_pack` perf, typed default (IR=1), interleaved `/usr/bin/time -v`: HEAD 355,168–355,964 KiB vs base 354,172–354,340 KiB (~+1 MiB). A 32M-element comprehension alone (`/tmp/rprobes/p7_bigcomp.py`, IR=1) is 263,248 KiB on HEAD vs 251,228 KiB on base (+12,020 KiB), because the cap forces doubling reallocs instead of the exact reserve. The original acceptance says peak RSS must not rise on any task. Capping only the push-based paths (SLIST / non-indexed) avoids both defects; the pre-existing `list[int]` huge-bound case is not the review's defect and does not block.

**Verified**
- Review defect fixed for `list[str]`: `/tmp/rprobes/p1_comp_huge_raise2.py` (literal 10^18), `p2_comp_huge_arg.py` (arg 10^12) print `caught` on HEAD default/general and typed IR=0/1; base default dies `list too long`/`out of memory`.
- `p3_intcomp_huge_raise.py`, `p4_range2_empty.py` (2-arg range, empty/negative trip), `p5_dict_list_item.py` (dict value, list item) all match CPython on HEAD default/general and typed IR=0/1.
- No-feature program `/tmp/rprobes/p0_no_feature.py`: `--debug-dir` `program.c` byte-identical to base for IR=0 and IR=1.
- `test_ail_slist_reserve` (3.9 s) and `test_ail_safetynet` (167 s) pass; `tools/update_manifest.py --check` rc 0.
- Report's claims about both emitters sharing `_LIST_RESERVE_LIMIT`, the added `comp_early`/`comp_early_arg` cases, DEVLOG/MEM_TREEFOLD edits, and commit `1f1c78f` are all true. The added tests only exercise SLIST and small sizes, so they do not catch Defect 1.

**Pre-existing:** `list[int]` huge-bound early exception also fails on base (`p3`), and the review already noted it; it is now fixed on HEAD, not a defect.

**Unverified:** icount (`perf_event_paranoid=4`, `perf_event_open: Permission denied`, no valgrind); the full 10-task RSS sweep (I checked only `tree_fold` and `echo_pack`; `tree_fold` n=3,000,000 is below the cap so its C/RSS is unaffected).

VERDICT: FIX
1. **Capped reserve breaks the indexed legacy comprehension's exact-capacity invariant.** Probe `/tmp/rprobes/p7_bigcomp.py`: expected exit 0 with stdout `32000000\n31999999` (CPython and base IR=0 do this); actual HEAD typed IR=0 exits 139 with empty stdout. Do not cap the `indexed` direct-store path (or fall back to `push` when the trip exceeds the cap); keep exact reserve there.
2. **Cap on `list[int]`/`list[float]` comprehensions raises peak RSS.** `echo_pack` perf typed IR=1: HEAD ~355.5 MiB vs base ~354.3 MiB; 32M synthetic IR=1: 263,248 KiB vs 251,228 KiB. The task requires no RSS rise. Capping only SLIST (the feature this job added) fixes this and Defect 1; the pre-existing `list[int]` huge-bound case may remain pre-existing.
[cost $0.0000, opencode tokens {"total": 2305715, "input": 42421, "output": 10205, "reasoning": 25761, "cache.write": 0, "cache.read": 2227328}]
    tool time: bash 6.9 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         84s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 600 python3 lab/compare/run_task.py --task echo_pack --o
         79s bash   cd /tmp/base && date && timeout 600 python3 lab/compare/run_task.py --task echo_pack --out /tmp/echo_base.json
         14s bash   cd /home/runner/work/ail-ci/ail-ci && date && echo "=== HEAD cmp p7_bigcomp"; timeout 400 bash ~/tools/cmp.sh 
         12s bash   cat > /tmp/rprobes/p0_no_feature.py <<'EOF' def main() -> int:     xs: list[str] = ["a", "b", "c"]     ys: lis
         11s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p1_comp_huge_raise2 p2_comp_huge_arg p3_intcomp_huge_ra
         10s bash   cd /tmp && echo "=== interleaved echo_pack"; for i in 1 2 3 4; do for tag in head base; do /usr/bin/time -v /t
          7s bash   for tag in head base; do echo "-- $tag"; for i in 1 2 3; do /usr/bin/time -v /tmp/ep_$tag pack < /tmp/ep_input

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both defects and committed `e56e3e7`.

- Capped only the push-based `list[str]` comprehension reserve in both emitters; `list[int]`/`list[float]` keep the exact reserve, so the legacy indexed direct-store path no longer overflows and large numeric comprehensions keep base RSS.
- Added a 5,000,000-element `list[int]` comprehension regression to `test_ail_slist_reserve`; updated DEVLOG and `MEM_TREEFOLD.md`.
- Probes: p1/p2 huge `list[str]` bound, p4/p5 empty range + dict/list item, p6/p7 (4,194,305 and 32M `list[int]`) match CPython on default, general, and typed IR=0/1. p0 `program.c` byte-identical to base for IR=0/1. p3 remains the known pre-existing `list[int]` huge-bound failure (also fails on base).
- Tests: `test_ail_slist_reserve` 4.2 s, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 839315, "input": 43423, "output": 5522, "reasoning": 3810, "cache.write": 0, "cache.read": 786560}]
    tool time: bash 6.9 min, edit 0.0 min, read 0.0 min
        370s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_saf
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_comp_huge_raise2 p2_comp_huge_arg p3_intcomp_huge_raise p4_r
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_comp_huge_raise2 p2_comp_huge_arg p3_intcomp_huge_raise p4_r
          5s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_slis
          4s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p0_no_feature p7d_comp_normal; do echo "=== cmp $p"; timeout 40
          2s bash   ls -d /tmp/base 2>/dev/null && cd /tmp && for ir in 0 1; do d1=$(mktemp -d /tmp/hcXXXX); d2=$(mktemp -d /tmp/b
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_slis

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: mem1 fix (cap only the `list[str]` comprehension reserve)

**What the diff really does:** caps the one-shot `list[str]` comprehension reserve at 2^22 elements in both emitters (`pyfunc.py` legacy ternary, `ir/lower.py` `select`), while `list[int]`/`list[float]` keep the exact reserve so the legacy indexed `.p[n++]` path cannot overflow; shares `_LIST_RESERVE_LIMIT` with the append-loop cap, adds early-exception + 5M `list[int]` regressions, updates docs/manifest. Report matches the diff.

**Last review's defect:** fixed. `pA_comp_huge_raise2.py` and `pB_comp_huge_raise3.py` now match CPython (`caught`, exit 0) on default, general, and typed `AIL_IR=0/1`. Generated C shows `min((n)-(0), 4194304)` before the loop in both emitters.

**Probes (HEAD):**
- `pA/pB` huge literal/argument `list[str]` bound + early raise: CPython 0 / g 0 / d 0 / IR0 0 / IR1 0, same stdout.
- `pC` 5,000,000-element `list[str]` comprehension (over cap): same stdout all four builds; len/first/last correct.
- `pD` empty/negative bounds, `pE` bound via list item/dict value/attribute: same stdout all builds.
- `p1/p2/p4/p5` worker probes: same stdout all builds.
- `p6` 4,194,305 and `p7` 32M `list[int]`: same stdout default/general/IR0/IR1, no overflow.
- `p0`/`pF` no-feature program: `program.c` byte-identical to base for IR=0 and IR=1.

**Pre-existing (not caused by this change):** `p3_intcomp_huge_raise.py` (`list[int]`, huge bound, early raise) exits 1 `out of memory` on HEAD and base alike in default and typed builds; general build passes on both. Class was already noted in review 1.

**Verified report claims:** list[str]-only cap in both emitters; exact numeric reserve preserved (p6/p7); added 5M `list[int]` test; `update_manifest.py --check` rc 0; probes match; p3 pre-existing on base. “Fixed both defects” is ambiguous (only one numbered defect existed, plus the overstated-cap claim); the pre-existing `list[int]` case remains, as the report itself states.

**Speed/memory:** tree_fold typed `ail`: HEAD RSS 475,768 KiB vs base 477,556 KiB, 55/55 cases, exit 0 — no rise. icount unavailable (`perf_event_paranoid=4`, no valgrind), so instruction counts unverified. Only list[str] comprehensions are affected; no lab/compare `main.ail` comprehension is list[str], so task RSS should be unchanged.

**Tests:** `test_ail_slist_reserve` 4.2 s, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` rc 0.

**Minor note (non-blocking):** the older DEVLOG entry from `1f1c78f` still says the cap “fixes the pre-existing `list[int]` instance”; the newer entry correctly records that this was reverted. Documentation only.

**Unverified:** instruction-count comparison; full 10-task RSS/stdout sweep (I ran tree_fold only); mutation-during-iteration / I/O ownership probes (diff only changes preallocation size; no file/buffer ownership code touched).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1967171, "input": 40232, "output": 7203, "reasoning": 18936, "cache.write": 0, "cache.read": 1900800}]
    tool time: bash 12.1 min
        259s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
        167s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         82s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/compare/run_task.py --task tree_fold --l
         78s bash   cd /tmp/base && date && timeout 900 python3 lab/compare/run_task.py --task tree_fold --langs ail --icount none
         77s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/compare/run_task.py --task tree_fold --l
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p6_over_cap p7_bigcomp; do for wt in $PWD /tmp/base; do
         14s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in pA_comp_huge_raise2 pB_comp_huge_raise3 pC_comp_over_ca
          9s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p1_comp_huge_raise2 p2_comp_huge_arg p4_range2_empty p5

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T00:02:48Z
