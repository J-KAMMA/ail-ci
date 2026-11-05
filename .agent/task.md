Lane: exmdtable

# mdtable1: an example app, `mdtable` (a Markdown pipe-table formatter), built by AIL and checked against CPython

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** inputs on which the AIL-built `mdtable` prints the same bytes and exits with the same status as
`python3 examples/mdtable/mdtable.py`. Today there is no such example. The target is at least 10 of 12 inputs, in the
default build and with `AIL_UNIFIED_FORCE=1`. It is a filter that a user would really run on a README, with column
width arithmetic and per-column alignment.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `examples/mdtable/mdtable.py`, `examples/mdtable/README.md`, `examples/mdtable/RESULTS.md`
- `examples/mdtable/data/*.md` (12 inputs)
- `AIL_CURRENT/test_ail_examples_mdtable.py` and `AIL_CURRENT/tests.d/test_ail_examples_mdtable.txt` (one line:
  `test_ail_examples_mdtable`)
- the manifest files that `tools/update_manifest.py` writes

Models: `examples/textcli/` and `AIL_CURRENT/test_ail_examples_textcli.py`. Do not touch `examples/mdlite/`.

## The program (write this into README.md)

`mdtable.py [--check] [--sum COL] < input.md`, 150-250 lines of plain Python 3.12. Lines that are not part of a pipe
table pass through unchanged. A table is a header row, a delimiter row (`---`, `:---`, `---:`, `:---:`), and body rows.
The program:
- splits cells on unescaped `|` (`\|` stays in the cell), strips cell spaces, and allows rows with or without the
  outer pipes;
- pads rows with fewer cells, and keeps extra cells as extra columns;
- writes each table again with every column as wide as its widest cell (`len()` of the text; at least 3), aligned as
  its delimiter says, `| a | b |` style;
- leaves fenced code blocks (```` ``` ````) alone;
- `--check`: prints `tables T rows R cols C` per table and exits 1 if any input table was not already formatted;
- `--sum COL`: appends a body row with the sum of column COL (1-based) where every cell is an int, and `n/a` if any
  is not. The sum uses Python ints; a sum beyond int64 must print the exact value or stop loudly.

## Sub-steps

1. **Program and inputs (25 min).** Write `mdtable.py` and 12 inputs: a plain table, every alignment, escaped pipes,
   no outer pipes, ragged rows, two tables with text between, a table inside a code fence, a non-table line with a
   pipe, an empty file, an already formatted table (`--check` exits 0), non-ASCII cells, and a `--sum` column whose
   total is `9223372036854775808`. Run each with `python3`. Commit, push, and open the PR against `integ`.
2. **Build and compare (15 min).** Build with AIL in the default mode and with `AIL_UNIFIED_FORCE=1`, and compare
   stdout and the exit status with `python3` for every input and option set (default, `--check`, `--sum 2`). The big
   sum passes only if AIL prints the exact value or exits non-zero with an `OverflowError` line. Write `RESULTS.md`:
   typed or general, with the first note line, one row per input. Commit and push.
3. **Test (20 min).** Write `AIL_CURRENT/test_ail_examples_mdtable.py` like `test_ail_examples_textcli.py`: build once
   per mode, run every passing input, compare with `python3`; skip without a C compiler. Register it (Appendix A rule
   6), run it, commit, push, and wait for CI.

## Done-check

- At least 10 of 12 inputs match CPython (or stop loudly beyond int64) in both builds.
- `python3 AIL_CURRENT/test_ail_examples_mdtable.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if any build prints output different from CPython (silent wrong output, such as a wrapped
sum): commit the input and both outputs in `RESULTS.md` first. Do not change the program's behaviour to dodge a
refusal; change only the spelling, and write each change in `RESULTS.md`. Stop when 60 minutes pass. Push what is done
first.

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
