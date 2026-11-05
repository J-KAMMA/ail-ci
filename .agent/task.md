Lane: typeshed

# typeshed3: report every stub that disagrees with a hand-written rule, and measure the typeshed gain on the whole corpus

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap). Runs after `typeshed2` is merged.

**Numbers this moves:**
- `conflicts`: entries where the stub table and a hand-written type rule of the compiler give different result types
  for the same callee. Today nobody counts them. The target is a complete list (every hand-written table below is
  checked), each conflict with a verdict from CPython 3.12. The compiler keeps the hand-written rule in every case; this
  job changes no rule.
- The whole-corpus gain of `typeshed2`: `unboxed_vars` summed over all of `lab/census/programs/` and `lab/stdlib/`,
  the count of programs whose generated C changed, and the count of CPython output differences, with
  `stubcalls` on and off. Target: differences on = differences off.
- `follow-ups`: the stdlib call sites that still stay boxed or refuse, ranked by count, each with the file and function
  where a rule would go. This is the input for later jobs, including the typed path (`pyfunc.py`, pyreach lane).

Base: `origin/integ` with `typeshed2` merged. Files you may create or edit, and no others:
- `tools/typeshed_conflicts.py` (new)
- `AIL_CURRENT/python/pkg-v12/stubcalls.py` (only: an environment switch `AIL_STUBCALLS=0` that turns the hook off, if
  `typeshed2` did not add one; default stays on)
- `lab/typeshed/CONFLICTS.md` (new), `lab/typeshed/RESULTS.md`
- `AIL_CURRENT/test_ail_typeshed_conflicts.py` (new) and `AIL_CURRENT/tests.d/test_ail_typeshed_conflicts.txt` (new,
  one line: `test_ail_typeshed_conflicts`)
- the manifest files that `tools/update_manifest.py` writes

No other compiler file changes. A conflict is reported, never fixed here.

## Sub-steps

1. **Conflict tool (30 min).** `tools/typeshed_conflicts.py` imports these read-only and compares each entry's result
   type with `stubsigs.lookup`:
   - `unified._etype`'s builtin rules (`len`, `ord`, `int`, `float`, `bool`, `isinstance`, `callable`, `round`, `abs`,
     `min`, `max`) against `builtins.pyi` (write them as a small table in the tool, with the `unified.py` line);
   - `unified._DRAWS` against `random.pyi`;
   - `pyfunc._AIL_SYSINFO`, `pyfunc._AIL_RAND`, `pyfunc._AIL_CLOCK`, `filelib.PRIMS` (each maps a name to a result
     kind; map the kind names `INT FLT STR BYTES` to `int float str bytes`);
   - the prelude functions of `genlib.TABLE`: the return annotation of each target function in `prelude_genlib.py` /
     `prelude_random.py`, where it has one.
   Print one line per pair `qualname rule_type stub_type source` and a summary `checked N agree A conflict C
   stub_obj O`. For each conflict, run the call under CPython 3.12 with typical arguments and record which side is
   right. A conflict where the stub is right means the compiler's rule may be wrong: list it in `CONFLICTS.md` under
   "rule may be wrong" with the exact source line and a probe program; do not change the rule. Commit, push, open the
   PR against `integ`.
2. **Whole-corpus measure (35 min).** Build every program of `lab/census/programs/` and `lab/stdlib/` twice on the
   general path (`AIL_UNIFIED_FORCE=1`), once with `AIL_STUBCALLS=0` and once without, each with
   `AIL_UNIFIED_STATS=<file>` and `--debug-dir` (`ulimit -v 1500000`, `-j 2` at most; if the full run would pass 40
   minutes, measure the programs `tools/typeshed_reach.py` marks as affected plus a random 100 of the rest, seed 1, and
   say so). Run each built program beside `python3`. Report in `RESULTS.md`: the `unboxed_vars` sums, programs with
   changed `program.c`, CPython differences in each run (the two lists must be equal), and the default-build typed /
   general / refused split, which this lane does not change (say so if it moved, and why). Rank the stdlib call sites
   that are still `obj` by count, with the reason (`not vendored`, `generic`, `overload`, `str/bytes result`, `method of
   a returned object`, `denied`), and name the file and function where support would go. Commit and push.
3. **Test (15 min).** `test_ail_typeshed_conflicts.py` runs the tool and checks that its summary line parses, that
   `conflict` equals the number of rows in `CONFLICTS.md`, and that every conflict row has a verdict. It needs no C
   compiler. Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_typeshed_conflicts.py` passes.
- `CONFLICTS.md` lists `checked`, `agree`, `conflict`, `stub_obj`, with a CPython verdict on every conflict.
- `RESULTS.md` gives the whole-corpus `unboxed_vars` on/off, the changed-C count, and equal CPython-difference lists
  for on and off.
- The follow-up ranking has at least the 20 most frequent boxed stdlib call sites.
- `git diff --stat origin/integ` shows only the files listed above.
- The 20 shards pass.

## Stop rule

Stop and report if a CPython difference appears only with stubcalls on: give the program, the call and both outputs,
and add nothing else until it is understood (it means `typeshed2` let a wrong type through). Stop when 80 minutes pass.
Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes (pyreach, frontend) own them;
   importing them read-only is fine. Do not edit `DEVLOG.md` either: put your notes in the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. `AIL_UNIFIED_FORCE=1` forces the general path.
- `typeshed1` vendored `third_party/typeshed/` and generated `stubsigs_table.py` (`stubsigs.lookup`); `typeshed2` added
  `stubcalls.py` and two hooks in `unified.py` (`_etype`, `nexpr`), with a checked unbox and `stubsigs.DENY`.
- A stub `int` is AIL's checked int64 (the int64 default); in exact-int mode stub ints stay boxed.
- CPython 3.12 is the oracle.

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
