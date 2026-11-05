Lane: safeiter

# safeiter1: a probe suite for mutating containers while iterating them, classified as matching CPython, a loud stop, or silent (measurement only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the count of silent wrong results among programs that change a list, dict or set while
iterating it. CPython defines the result for lists (index-based) and raises `RuntimeError` for dicts and sets that
change size. A compiled backend that caches a length or a pointer can print something else, or read freed memory.
`gaps5.md` already noted that a dict view does not raise when the dict changes size. Today there is no suite. The
target is a table of at least 24 probes in four modes, silent cases listed first. No compiler file is edited.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/safety/itermut/*.py` (24 or more probes), `lab/safety/itermut/run.py`, `lab/safety/itermut/RESULTS.md`
- `AIL_CURRENT/test_ail_safety_itermut.py` and `AIL_CURRENT/tests.d/test_ail_safety_itermut.txt` (one line:
  `test_ail_safety_itermut`)
- the manifest files that `tools/update_manifest.py` writes

Models: `lab/safety/stops/run.py`, `lab/safety/stops/RESULTS.md` and `AIL_CURRENT/test_ail_safety_stops.py`: copy
their four modes (typed with `--strict`, default, general with `AIL_UNIFIED_FORCE=1`, hybrid) and their classes.

## Sub-steps

1. **Probes (25 min).** Write at least 24 probes, each 5-25 lines, each printing the visited items and the final
   container. Every probe that could loop forever in CPython stops itself after 50 steps with a counter. Cover:
   - lists in a `for` loop: `append` (bounded), `remove` of the current item (skips the next), `pop(0)`, `insert(0,
     x)`, `del xs[i]`, `xs.clear()`, `xs[:] = []`, `xs.sort()` and `xs.reverse()` mid-loop, `xs += xs` once;
   - lists through `enumerate`, `zip`, `reversed`, a saved `iter(xs)`, a list comprehension and a generator expression
     over a list that the loop body changes;
   - `sorted(xs, key=f)` and `xs.sort(key=f)` where `f` appends to `xs` (`ValueError: list modified during sort`);
   - dicts: adding a key in `for k in d` (`RuntimeError: dictionary changed size during iteration`), deleting a key,
     changing a value only (allowed), iterating `d.items()`/`d.keys()`/`d.values()` while adding, `d.pop` then
     re-adding the same key (size same: CPython 3.12 raises `RuntimeError: dictionary keys changed during iteration`);
   - sets: `s.add` and `s.discard` in `for x in s` (`RuntimeError: Set changed size during iteration`);
   - a list of 100000 ints mutated by `append` inside the loop with a bound, to catch a stale length or pointer after
     the buffer moves.
   The exception name and message must equal CPython's. Commit, push, and open the PR against `integ`.
2. **Runner and run (20 min).** Write `lab/safety/itermut/run.py` from `lab/safety/stops/run.py`, with the classes
   `match`, `loud-stop` (non-zero exit with a named error where CPython gives the same error with another text),
   `refused`, `crash` (signal or no error line) and `silent-wrong` (different stdout, or exit 0 where CPython raised).
   Run all probes in the four modes with `ulimit -v 1500000` and `timeout 20`. Write `RESULTS.md`: base commit and
   date, then **the silent-wrong and crash rows first**, each with the two outputs, then the rest. Commit and push.
3. **Test (15 min).** Write `AIL_CURRENT/test_ail_safety_itermut.py` like `test_ail_safety_stops.py`: a ratchet over
   the probes that match in the default and general modes. Register it (Appendix A rule 6). Commit, push, and wait
   for CI.

## Done-check

- At least 24 probes, each classified in four modes in `RESULTS.md`, silent rows first, with a count per class.
- `python3 AIL_CURRENT/test_ail_safety_itermut.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

This task measures wrong output; it does not fix it. Record every silent-wrong and crash case with a minimal repro and
go on. Do not edit a compiler file. Stop and report if a probe reads past a buffer in a way that changes another
probe's result, or if more than 5 probes exceed the memory cap. Stop when 60 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `packaging/ail_lang/cli.py`, or these files
   in `AIL_CURRENT/python/pkg-v12/`: `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
   `ir/*`, `parallel.py`, `typedpar.py`, `buildcache.py`, `stubcalls.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
