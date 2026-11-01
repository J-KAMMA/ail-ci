**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds Python-front-end lowerings (argv element typing, inferred helper return kinds, local dict-of-lists `setdefault`/`get`, owned unannotated `bytes()` helpers, bytearray-to-bytes views, loop-body nested defs, `m.groups()` loops, entry recovery) so `echo_pack` builds typed; broader than just the "top reason".

**Defects**
1. Dict-of-lists lowering silently changes `d.get(k)` semantics when the result is used in a comparison rather than a truth test.
   Probe `/tmp/rprobes/p_dict_eq.py`:
   ```python
   def main():
       d = {}
       d.setdefault("k", []).append(1)
       y = d.get("miss")
       if y == []: print("empty")
       else: print("notempty")
   main()
   ```
   Expected CPython/base: `notempty`; HEAD default and strict: `empty`.
   Same root cause: `if y is None:` yields expected `none`, HEAD default `notnone` (strict refuses: `` `is None` on something that is never None ``). `truth_tested` accepts any `If` test containing the name, not only truth tests.

2. Manifest stale. `python3 tools/update_manifest.py --check` exits 1 listing `ail_syntax.py`, `python/pkg-v12/{collib,pyfunc,relib}.py`, `test_ail_pytyped_reach.py`; `tools/par_check.py` preflight fails with `ValueError: hash mismatch: ail_syntax.py`. The DEVLOG claim that `update_manifest.py --check` passed is false. Direct `unittest` of `test_ail_pytyped_reach` + `test_ail_safetynet` does pass (14 tests, 201 s).

**Verified claims**
- `echo_pack` builds with `--syntax python --strict` (exit 0); `run_task.py` reports `path: typed`, public 3/3, hidden 54/54, correct.
- All ten lab `.ail` builds: emitted `program.c` byte-identical base vs HEAD; all ten still strict-typed.
- Only `echo_pack` is newly typed among the ten `.py` tasks.
- icount is unavailable here as reported (`perf_event_paranoid=4`, no valgrind).

**Unverified**
- The 10 % instruction-count acceptance for the new typed task; wall is 1.05 s (`.ail`) vs 4.81 s (`.ail-py`), though the two sources use different algorithms.
- Other claimed test modules (`test_ail_files`, `test_ail_corpus_findings3`, etc.) were not run, per reviewer scope.

**Pre-existing**
- `sys.argv[0]` differs between CPython and compiled builds; identical on base, not caused by this change.

VERDICT: FIX
[cost $0.0399, opencode tokens {"total": 2286144, "input": 84835, "output": 8372, "reasoning": 26153, "cache.write": 0, "cache.read": 2166784}]
    tool time: bash 22.3 min
        460s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t
        218s bash   cd /home/runner/work/_temp/w2 && date && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --langs
        201s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && AIL_NO_CACHE=1 PIPE_CC=$(command -v gcc) AIL_EXTRA_CFLAGS
        118s bash   cd /home/runner/work/_temp/w2 && date && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --langs
         80s bash   cd /tmp/rprobes && cat > p_entry_multi.py <<'EOF' import re import sys  def main(s):     if re.fullmatch(r"[0-
         75s bash   diff -q /tmp/dg/dbg/program.c /tmp/db/dbg/program.c && echo same; wc -l /tmp/dg/dbg/program.c; cd /home/runner
         64s bash   cd /home/runner/work/_temp/w2 && date && for p in p_dict_none p_dict_param p_dict_key p_dict_attr p_ba_alias p
         41s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t


--- ORIGINAL TASK ---
**`.py` sources should take the typed (fast) path like their `.ail` twins.** lab/compare has both a `.py` and a typed `.ail` source for each task; the `.py` builds are refused or fall to the general path (about 20x slower).
- Step 1: for each of the 10 tasks, build the `.py` (`--syntax python`) with `--strict` and list every reason it leaves the typed path. Rank the reasons by how many tasks they block, and write the list to docs/design/PY_TYPED_REACH.md.
- Step 2: fix the top reason in the front end so that at least one more task builds typed from `.py`.
- Acceptance:
  - stdout and exit code are identical to CPython on every case.
  - The generated C for `.ail` sources is byte-identical to before.
  - Run icount for the newly typed task is within 10% of its `.ail` twin.
  - No task that was typed before becomes general.
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
