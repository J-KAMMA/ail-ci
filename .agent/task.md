Lane: cmdmod

# cmdmod1: `import cmd` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/cmd.py`)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/cmd/` that build in the default mode and print what CPython prints,
with the same exit status. Today it is 0/10: the stdlib census (`lab/stdcensus/RESULTS.md`) records `cmd` as refused
with `cmd.py:90:13: not in the subset: sys.stdin used as a plain value`. The target is at least 7/10. `cmd.Cmd` is
the base class for small line-oriented command shells, which fits the roadmap's P4 niche (small CLI tools).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/cmd.py` (new)
- `lab/stdlib/cmd/*.py` (10 new programs), `lab/stdlib/cmd/*.in` (stdin inputs) and `lab/stdlib/cmd/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_cmd.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_cmd.txt` (new, one line:
  `test_ail_std_cmd`)
- the manifest files that `tools/update_manifest.py` writes

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import cmd` (see Appendix B). CPython's `Cmd`
stores `sys.stdin` and `sys.stdout` in fields and calls `.readline()` and `.write()` on them; AIL refuses
`sys.stdin` as a value. The AIL copy reads with `input()` (or `sys.stdin.readline()` written at the call site) and
writes with `print(..., end="")` or `sys.stdout.write(...)` at the call site. Follow `AIL_CURRENT/stdlib/shlex.py`
(which met the same `sys.stdin` refusal) and `AIL_CURRENT/test_ail_std_shlex.py` as models.

## Sub-steps

1. **Programs and baseline (15 min).** Write 10 programs in `lab/stdlib/cmd/`, each 20-50 lines of ordinary
   Python 3.12, each a subclass of `cmd.Cmd`. Five read their commands from stdin (an `.in` file of the same name,
   run with `use_rawinput = False` or the default); five need no stdin: they call `onecmd()` directly or fill
   `cmdqueue` and end it with `"EOF"`. Together they must cover:
   - `do_*` methods with and without an argument, `prompt` and `intro`, `do_EOF` returning `True` to stop;
   - `default()` for an unknown command and the CPython text `*** Unknown syntax: ...`;
   - `emptyline()` default (repeat `lastcmd`) and an override that does nothing;
   - `precmd`, `postcmd`, `preloop`, `postloop`;
   - `help` with no argument (the `Documented commands (type help <topic>):` table from docstrings and `help_*`),
     `help name`, and `help unknown` (`*** No help on unknown`);
   - `parseline()` results for `?x`, `!ls`, `  spaced  args  `;
   - a calculator shell that turns arguments into ints with `int()`, given `"42"`, `"-9223372036854775808"` and
     `"99999999999999999999"` (beyond int64): print what CPython prints, or let the program stop loudly.
   Build each program with the default command. Record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before". Commit, push, and open the PR against `integ`.
2. **The module (25 min).** Write `AIL_CURRENT/stdlib/cmd.py` from CPython 3.12's `Lib/cmd.py`. Print it with
   `python3 -c "import cmd, inspect; print(inspect.getsource(cmd))"`. Keep `Cmd` with `cmdloop`, `precmd`,
   `postcmd`, `preloop`, `postloop`, `parseline`, `onecmd`, `emptyline`, `default`, `completedefault`,
   `completenames`, `get_names`, `do_help`, `print_topics`, `columnize`, and the class attributes `prompt`,
   `identchars`, `ruler`, `lastcmd`, `intro`, `doc_leader`, `doc_header`, `misc_header`, `undoc_header`,
   `nohelp`, `use_rawinput`. Drop `readline` completion (no terminal); `complete()` may stay as a stub that returns
   `None`. `get_names` uses `dir(self.__class__)`; if that is refused, find the `do_*` names another way that keeps
   CPython's order (sorted) and write down how in the docstring. Every printed text must be exactly CPython's. Add
   the CPython license line (PSF) to the docstring. Commit and push.
3. **Make the programs pass (20 min).** Build all 10 programs again. Fix the module, never the programs, until at
   least 7 build and match. A refusal that needs a compiler file goes into `RESULTS.md` as a follow-up, with the
   exact refusal text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_cmd.py`, copying the structure of `test_ail_std_shlex.py`. It
   builds every passing program, feeds its `.in` file when there is one, and compares stdout and the exit status with
   `python3`, in the default build and again with `AIL_UNIFIED_FORCE=1`. It skips when there is no C compiler.
   Register the test (Appendix A rule 6) and run it. Fill `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_cmd.py` passes.
- At least 7 of the 10 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `cmd.py` is not picked up by `import cmd`; give the exact message. Also stop if
subclassing a bundled module's class (`class Shell(cmd.Cmd)`) is refused outright; give the exact message. Stop if
fewer than 4 programs can pass without editing a compiler file; name each blocking refusal. Stop when 80 minutes
pass. Push what is done first.

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
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files
   this task names. Edit only the files this task names, plus the manifest files that `tools/update_manifest.py`
   writes.

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
