Lane: fd-dbg
Needs: fddbg1

# fddbg2: debugger story, part 2: gdb pretty-printers for AIL values and docs/DEBUGGING.md

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** value kinds that gdb's `print x` shows as CPython's `repr(x)`, out of 12 (int, float, bool, None,
str, bytes, list[int], list[float], list[str], dict[str, int], tuple, a general-path boxed object). Today gdb prints C
structs. Target: at least 10/12 equal to `repr`; the rest named in the docs.

Base: `origin/integ` (with fddbg1 integrated). Files you may create or edit, and no others:
- `AIL_CURRENT/tools_gdb/ail_gdb.py` (new; a gdb Python script, loaded with `gdb -x`)
- `docs/DEBUGGING.md` (new)
- `lab/debug/printers/*.py` (new) and a "Printers" section in `lab/debug/RESULTS.md`
- `AIL_CURRENT/test_ail_debug_printers.py` (new) and `AIL_CURRENT/tests.d/test_ail_debug_printers.txt` (new, one
  line: `test_ail_debug_printers`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Layouts (15 min).** From the generated C of a `--debug` build, write down the struct of each of the 12 kinds
   (`ail_str` is UTF-16 code units with a `bytes` flag; typed lists; `ail_obj` boxes). Write one program per kind with
   a known value and a `# repr:` comment taken from CPython. Commit, push, and open the PR against `integ`.
2. **Printers (30 min).** `ail_gdb.py` registers printers by C type name, reads memory only (never calls into the
   program), bounds every loop by the length field, and prints `<unreadable>` on a bad pointer, never a guess. Long
   containers print the first 100 elements and `...`. Commit and push.
3. **Test and docs (15 min).** The test builds each program with `--debug`, runs
   `gdb -batch -x ail_gdb.py -ex 'break N' -ex run -ex 'print x'`, and compares with the `# repr:` line; it skips
   without gdb. Register it. `docs/DEBUGGING.md`: `ail build --debug`, gdb and the printers, `bt`, what `next` does on
   each path, the known gaps from fddbg1's `RESULTS.md`. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_debug_printers.py` passes.
- At least 10/12 kinds equal to `repr` in `RESULTS.md`.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a printer would need a change to the generated C; name it. Stop at once and report if any build
prints output different from CPython (or from the reference this task names) without a refusal or a loud stop: give
the program, both outputs and the commit. Never commit a change that does that. Stop when 60 minutes pass. Push what
is done first.

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
