**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
**Cut peak memory on lab/compare tree_fold: AIL 605 MiB against Rust 315 MiB.**
- Step 1, measure. Use the typed build of tree_fold. Find where the peak RSS goes (allocation counts and sizes by site, with LD_PRELOAD malloc stats or massif if present, or a counting build), and per-node object size against Rust's node size. Write the result in docs/design/MEM_TREEFOLD.md with the numbers.
- Step 2, fix the largest cause in the compiler or runtime, not in the task source. Candidates: per-object header or refcount size, list over-allocation, boxed ints in nodes, freed memory not reused.
- Acceptance:
  - stdout and exit code are identical on every case of all 10 lab/compare tasks.
  - Peak RSS (`/usr/bin/time -v`) does not rise on any task.
  - Run icount (tools/icount) does not rise on any task. Any rise blocks; report it, do not hide it.
  - Report tree_fold RSS before and after.
- Run the touched test modules plus test_ail_safetynet and `python3 tools/update_manifest.py`, then commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
