**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds a general-path `key=` lowering for `bisect_left/right/bisect/insort*` (`BISECTKEY_C` in `AIL_CURRENT/python/pkg-v12/pyboxed2.py`), plus 12 lab programs, a CPython-comparing test, DEVLOG/RESULTS. The length is a manual list/tuple/str switch, not generic: other CPython sequences are not handled.

**Verification.**
- `test_ail_std_bisect` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` passes.
- Non-key codegen unchanged: `lab/compare/src/berth_sim` and `echo_pack` `program.c` byte-identical to `/tmp/rbase` (only spot-checked 2 of the claimed 17).
- Worker probes `p1_review`, `p2_str_paths`, `p3_tuple_paths`, `p5_list_key`, `p_bisect_key_tuples`: match CPython on both builds.
- My probes matching CPython on both builds: list/tuple/str keys, lo/hi (`-1`, `-2`, `>n`), `hi=None`, negative lo, empty, raising key, `insort` on str/tuple (`AttributeError`), mutation during key, key through argument/dict/attribute, NaN, reversed/non-monotonic keys, GC pressure, deque.
- Report claims mostly verified: list/tuple/str handling, insort `AttributeError`, 12/12 lab programs, DEVLOG/test registration. Exact `p4_insort_str` and the full 17-pair/five-module claims were not rerun.

**Pre-existing (identical on `/tmp/rbase`, not blocking).**
- General build, non-key `bisect_left("abc","b")`: segfault on both base and HEAD.
- Default build, `insort_left([1,2,3],0,5)`: `list assignment index out of range` on both.
- Non-BMP string literals / `chr(0x1F600)`: named compile refusal on both.

**Defects.**

VERDICT: FIX
1. `key=` on a `range` is accepted but aborts at run time (both default and general builds). Probe `/tmp/rprobes/v_range.py`:
```python
import bisect
def main():
    print(bisect.bisect_left(range(10), "5", key=str))
    print(bisect.bisect_right(range(10), "5", key=str))
    print(bisect.bisect_left(range(0), "5", key=str))
main()
```
Expected: `5\n6\n0\n`, exit 0. Actual: no stdout, exit 1, `TypeError: object of type 'range' has no len()`. Base refused by name, so the change introduced the wrong result. Fix `ail__bisect_len` to use generic length (range indexing already works via `ail_op_getitem`), or refuse by name.
2. `key=` on `bytes`/`bytearray` works in the default build but fails in the general build. Probe `/tmp/rprobes/v_bytes.py`:
```python
import bisect
def main():
    print(bisect.bisect_left(b"aceg", 100, key=int))
    print(bisect.bisect_right(bytearray(b"aceg"), 101, key=int))
    print(bisect.bisect_left(b"", 1, key=int))
main()
```
Expected: `2\n3\n0\n`, exit 0. Actual general build: no stdout, exit 1, `TypeError: object of type 'bytes' has no len()`; default build matches CPython. Base general refused by name. Same root cause as defect 1.
[cost $0.0535, opencode tokens {"total": 4052540, "input": 110645, "output": 11032, "reasoning": 30959, "cache.write": 0, "cache.read": 3899904}]
    tool time: bash 8.7 min
        241s bash   cd /home/runner/work/_temp/w2 && date && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetyne
        120s bash   cd /tmp && rm -rf cg && mkdir cg && for task in berth_sim echo_pack ticket_audit rail_transfer grade_report; d
         41s bash   cd /tmp/probes && for f in p1_review p2_str_paths p3_tuple_paths p5_list_key p_bisect_key_tuples; do echo "===
         14s bash   cd /tmp/rprobes && cat > v_bounds.py <<'EOF' import bisect  def main():     a = [1, 2, 2, 4]     for lo, hi in
         14s bash   cd /tmp/rprobes && cat > v_range.py <<'EOF' import bisect  def main():     print(bisect.bisect_left(range(10),
          9s bash   cd /tmp/rprobes && cat > v_gc.py <<'EOF' import bisect  def main():     junk = []     def key(v):         junk
          7s bash   cd /tmp/rprobes && cat > v_deque.py <<'EOF' import bisect from collections import deque  def main():     d = d
          7s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > v_seq.py <<'EOF' import bisect  def main():     print(bisect


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `bisect` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `bisect` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/bisect/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/bisect/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_bisect.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
