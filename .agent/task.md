**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds `copy.copy`/`copy.deepcopy` to the general path (`genlib.py` names/keywords, `prelude_genlib.py` signatures, a new `COPY` runtime fragment with memo/keep-alive), refuses class-body `__copy__`/`__deepcopy__`/`__reduce__`/`__reduce_ex__` when copy is used, rebuilds typed `_AilD_`/`_AilS_` copies as plain `dict`/`set`, and adds 12 lab programs plus `test_ail_std_copy`.

**Claims checked**
- Generator raises `TypeError: cannot pickle 'generator' object`, direct and nested: **verified** (`rv_gen.py`, both builds).
- Class-body copy-hook methods refused by name: **verified** (`rv_proto.py`); the report's broad claim is **false** for runtime assignment (defect 2).
- `_AilD_`/`_AilS_` copies are plain `dict`/`set`: **verified** (`rv_typed.py`, `rv_paths.py`).
- 15/20 lab/compare C identical, 5 same refusals: **verified** (my `--debug-dir` builds: 15 `program.c` SAME; `scar_life/tally_lang/tree_fold` `main.py` refuse identically on base/head).
- `test_ail_std_copy` + `test_ail_safetynet`: **verified** (168s, 0 failed). The other 3 reported modules: **unverified**.
- `update_manifest.py --check`: **verified** rc 0.
- Worker's individual probe files and the "pre-existing set order / table `type()` names": **unverified** (not rerun).
- Non-copy programs: general-path C byte-identical to base (`rv_nocopy.py`).

**Other probes** (`rv_shallow`, `rv_deep`, `rv_memo`, `rv_args`, `rv_exc2`, `rv_coll`) match CPython on both builds; except the memo-size case below.

VERDICT: FIX

1. **`__getstate__`/`__setstate__` are silently ignored instead of refused or honoured.** Probe `/tmp/rprobes/rv_state.py`: a class whose `__getstate__`/`__setstate__` change the copied state. CPython and expected output `99 2 99 2`; actual on general and default builds `1 None 1 None`. These hooks are part of the copy protocol and easy to add to `_COPY_PROTOCOL`; otherwise a built program prints wrong output.

2. **Runtime-assigned copy hooks are not detected.** Probe `/tmp/rprobes/rv_dynamic.py`: `C.__copy__ = alt` then `print(copy.copy(C()))`. Expected `special`; actual `<C object>` on both builds. The class-body scan misses `Assign`/`AnnAssign` targets whose attribute is a protocol name, so the report's claim that a class defining `__copy__` is refused is false in this case.

3. **`len(memo)` after `deepcopy(frozenset)` differs.** Probe `/tmp/rprobes/rv_frozen.py`: `m={}; copy.deepcopy(frozenset({1,2}), m); print(len(m), ...)`. CPython/expected `3 False True`; actual `2 False True` on both builds. Low severity, but the documented `memo` argument is observable and this is not one of CPython's optimisations: CPython reconstructs the frozenset through a temporary list that is also memoised.

Non-blocking note: any class defining one of the four protocol names anywhere makes every copy-using program refuse (`rv_proto_unrelated.py`), even when only an unrelated container is copied. That is a named refusal (allowed), but it narrows coverage more than necessary.

No pre-existing output differences were observed in the probes I ran.
[cost $0.0424, opencode tokens {"total": 2504751, "input": 71232, "output": 11540, "reasoning": 29275, "cache.write": 0, "cache.read": 2392704}]
    tool time: bash 21.4 min
        524s bash   cd /tmp && rm -rf ccmp && mkdir -p ccmp && for d in /home/runner/work/_temp/w2/lab/compare/src/*/; do t=$(base
        445s bash   cd /tmp && rm -rf ccmp && mkdir -p ccmp && for d in /home/runner/work/_temp/w2/lab/compare/src/*/; do t=$(base
        169s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_
         39s bash   cd /tmp/rprobes && for f in rv_memo rv_args rv_gen rv_typed rv_paths rv_exc; do echo "######## $f"; timeout 30
         35s bash   cd /tmp/rprobes && for f in rv_shallow rv_deep rv_memo rv_gen rv_proto rv_proto_unrelated; do echo "######## $
         29s bash   cd /tmp/rprobes && cat > rv_memo2.py <<'PY' import copy  def main() -> None:     for v in ((1, 2), (1, "a"), f
         17s bash   cd /tmp/rprobes && cat > rv_nocopy.py <<'PY' def main() -> None:     values = [3, 1, 2]     table = {"a": valu
         10s bash   cd /tmp/rprobes && cat > rv_state.py <<'PY' import copy  class WithState:     def __init__(self):         self


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `copy` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `copy` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/copy/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/copy/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_copy.py registered in tests.d), and compare them with CPython in the test.
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
