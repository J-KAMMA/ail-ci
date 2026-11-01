**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of `44c847b..HEAD` (b9b1cbc + 0ac1f32)**

The change really does: add a bundled `AIL_CURRENT/stdlib/shlex.py` (split/quote/join plus the lexer, with POSIX `None` EOF, `__next__`, and `infile`/`error_leader` sentinels), 12 lab programs, RESULTS, and `test_ail_std_shlex`. The report describes this accurately.

**Verified**
- 12/12 `lab/stdlib/shlex` programs match CPython stdout/exit on both builds.
- Worker probes (`/tmp/probes/shlex_fix_*`, 4) all match on both builds.
- My probes `p1b_infile`, `p2_iter`, `p4b_punct`, unicode/`wordchars` in `p7` match on both builds.
- `test_ail_std_shlex` + `test_ail_safetynet` pass; `test_ail_files` + `test_ail_corpus_findings3` pass (4/4).
- `tools/update_manifest.py --check` exits 0.
- Generated `program.c` for all 10 `lab/compare/src/*/main.ail` is byte-identical to base.
- No compiler/runtime changes, so speed is not affected.
- Report claim "removed DIFFERENCES row" is verified (row added then removed).
- Pre-existing: `iter(user_obj) is user_obj` is `False` on both HEAD and base; lab iteration still matches.

**Defects found (all caused by the new module; base refuses the import)**

1. `shlex.split(None)` — `AIL_CURRENT/stdlib/shlex.py:343` passes `None` into the lexer.
   ```python
   import shlex
   try: print(shlex.split(None))
   except ValueError as e: print("value", e)
   except TypeError as e: print("type", e)
   ```
   Expected CPython: `value s argument must not be None`
   Actual: `type object of type 'NoneType' has no len()`
   (Realistic: `shlex.split(config.get("cmd"))` with a missing key.)

2. `shlex.quote(None)` — line 40 tests `s == ""`, not truthiness.
   ```python
   import shlex
   print(repr(shlex.quote(None)))
   ```
   Expected: `"''"`; actual: `TypeError ... NoneType has no len()`. Same for `shlex.join([None])`.

3. `lex.source` is `""`, not CPython's `None` — line 118.
   ```python
   import shlex
   lex = shlex.shlex("x", "f.sh", True)
   print("none" if lex.source is None else "not-none", repr(lex.source))
   ```
   Expected: `none None`; actual: `not-none ''`.

Minor, not counted: `debug` mode omits CPython's `push_source`/`pop_source` lines and prints `raw token=''` where CPython prints `raw token=EOF` (`p9_debug`); the `pop_source` line contains a CPython stream address, so exact parity may not be practical.

**Unverified:** no full-suite run (by instruction); `lex.instream` is a string rather than a file object (documented limitation, not probed as a defect).

VERDICT: FIX
[cost $0.0315, opencode tokens {"total": 1352798, "input": 58103, "output": 7637, "reasoning": 24082, "cache.write": 0, "cache.read": 1262976}]
    tool time: bash 12.2 min
        233s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_files te
        172s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_std_shlex
        109s bash   cd /home/runner/work/_temp/w2 && for f in lab/stdlib/shlex/*.py; do printf '%s ' "$(basename $f)"; bash ~/tool
         61s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/ccmp && mkdir -p /tmp/ccmp && ok=0; bad=0; for t in $(ls lab/comp
         39s bash   cd /tmp/probes && for p in shlex_fix_eof_posix shlex_fix_eof_nonposix shlex_fix_next shlex_fix_leader; do echo
         32s bash   cd /tmp/rprobes && for p in p1_infile p2_iter p3_quote p4_punct p5_misc; do echo "===== $p"; bash ~/tools/cmp.
         24s bash   cd /tmp/rprobes && cat > p1b_infile.py <<'PY' import shlex  def show(tag, lex):     print(tag, repr(lex.infile
         17s bash   cd /tmp/rprobes && cat > p9_debug.py <<'PY' import shlex  def main():     lex = shlex.shlex("a b", "f.sh", Tru


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `shlex` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `shlex` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/shlex/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/shlex/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_shlex.py registered in tests.d), and compare them with CPython in the test.
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
