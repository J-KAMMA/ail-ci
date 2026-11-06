Lane: fd-dbg
Agent: opus

> Re-run of fddbg1 (previous run: FINAL VERDICT: REJECT  2026-11-05T23:50:57Z). Its follow-up jobs are blocked until this lands; do the real change the task asks for — a run that changes nothing or reshapes the measurement is not acceptable.

# fddbg1: debugger story, part 1: a gdb test matrix and full DWARF line coverage

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** (a) executable statement lines that appear in the DWARF line table of `--debug` builds, over 10
programs, typed and general path; (b) passing checks of a 30-check gdb matrix. Today `test_ail_debug.py` checks one
`break prog.py:3` + `bt 1` and a few lines of the line table. Target: (a) 100% on the typed path, recorded on the
general path; (b) at least 26/30, every failure named in `RESULTS.md`.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/ir/emit_c.py` and `AIL_CURRENT/python/pkg-v12/cruntime.py` (only for `--debug` output; a release
  build's C must stay byte-identical)
- `lab/debug/progs/*.py` (10 new), `lab/debug/linecov.py` (new) and `lab/debug/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_debug_gdb.py` (new) and `AIL_CURRENT/tests.d/test_ail_debug_gdb.txt` (new, one line:
  `test_ail_debug_gdb`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Measure (20 min).** Write 10 programs (loops, nested calls, a method, a comprehension, try/except, an import of
   a helper module, one general-path program). `linecov.py` lists the executable statement lines with `ast` and
   compares them with `readelf --debug-dump=decodedline` of the `--debug` build. Write the gdb matrix as
   `gdb -batch -x script` runs: break at a line; `next` five times (the lines visited equal the lines CPython's
   `sys.settrace` visits); `bt` inside a call 3 deep (every frame names `file.py:N`); `finish`; `info locals` and
   `print n` for an int and a float local (does gdb show the Python name and value?); an `IndexError` stopped with a
   breakpoint on the runtime's raise function. Record both numbers in `RESULTS.md` "Before". Commit, push, and open
   the PR against `integ`.
2. **Fix the typed path (25 min).** Fix missing `#line` directives and wrong mappings in `emit_c.py` / `cruntime.py`
   until (a) is 100% on the typed path. Locals: if gdb cannot show a Python local by its name, record the C name
   mapping; rename only in debug builds and only if the release C stays byte-identical. The general path is
   `pyboxed2.py` (not editable here): record its gaps as follow-ups with the exact missing lines. Prove the release C
   unchanged with `--debug-dir` diffs on the `lab/compare/src` programs. Commit and push.
3. **Test (15 min).** `test_ail_debug_gdb.py` runs the matrix and `linecov.py` on 4 programs. It skips only when gdb
   is missing, and prints `gdb: <version>` first so the CI log shows whether it ran. Register it. Fill "After".
   Commit, push, and wait for CI; check in a shard log that the gdb checks ran.

## Done-check

- `python3 AIL_CURRENT/test_ail_debug_gdb.py`, `test_ail_debug.py` and `test_ail_debug_lines.py` pass.
- `RESULTS.md`: 100% line coverage on the typed path, at least 26/30 gdb checks, release C byte-identical.
- The 20 shards pass, and one shard log shows the gdb checks ran (not skipped).
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the CI runners have no gdb (keep the readelf part and say so), or if any release build's C changes.
Stop at once and report if any build prints output different from CPython (or from the reference this task names)
without a refusal or a loud stop: give the program, both outputs and the commit. Never commit a change that does that.
Stop when 60 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug] [--debug-dir DIR]`.
  `DIR/program.c` is the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback
  to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations (`.py` files only; the `.ail` brace syntax is retired). Ints are
  int64, and overflow stops loudly. Never silent wrong output: a value AIL cannot compute exactly is refused by name
  or stops loudly.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- `--debug` = `AIL_DEBUG=1`: `-g -O0 -DAIL_DEBUG_SITE=1` (`pipeline.py`), `#line N "file.py"` before every
  statement on the IR typed path (`ir/emit_c.py`), and a `raised near` line for an uncaught error.
- Existing tests: `test_ail_debug.py` (its `line_table` helper reads readelf/objdump), `test_ail_debug_lines.py`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
