Lane: fd-fmt

# fdfmt1: `ail fmt --check` that reuses an existing Python formatter, proven not to change the build

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** corpus programs whose generated C, output or refusal changes after formatting. Target: 0 of 60.
Second number: the check mode's answers (already formatted / would change) agree with `ruff format --check` on 60/60.
AIL is Python syntax, so AIL writes no formatter of its own: `ail fmt` runs `ruff format` when it is on `PATH`, else
`black`, and neither becomes a dependency of the package.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/fmt.py` (new; `python3 -m ail_lang.fmt --check FILE...` from `packaging/`)
- `lab/fmt/check_build.py` (new) and `lab/fmt/RESULTS.md` (new)
- `docs/FORMAT.md` (new)
- `AIL_CURRENT/test_ail_fmt.py` (new) and `AIL_CURRENT/tests.d/test_ail_fmt.txt` (new, one line: `test_ail_fmt`)
- the manifest files that `tools/update_manifest.py` writes

The `ail fmt` subcommand is wired into `cli.py` later by fdcli1.

## Sub-steps

1. **Formatters in a throwaway venv (10 min).** `python3 -m venv /tmp/fmtvenv && /tmp/fmtvenv/bin/pip install
   ruff==<pin> black==<pin>`; write the pinned versions into `RESULTS.md`. Commit nothing from the venv.
2. **The build check (20 min).** `lab/fmt/check_build.py` takes 60 programs: the `lab/compare/src` programs and the
   rest from `lab/stdlib/*/`, `lab/errux/progs/` (a refusal must stay the same refusal) and `lab/safety/`. For each:
   copy, `ruff format` the copy, build both with `--debug-dir`, compare `program.c` after removing source line numbers
   (`#line` directives and the line arguments of `AIL_DBG_SITE`), compare stdout and the exit status, and compare
   refusal texts with line and column numbers removed. Check that a `# ail: gpu` marker and a PEP 263 coding line
   survive. Record per program in `RESULTS.md`. Commit, push, and open the PR against `integ`.
3. **`fmt.py` (15 min).** `--check FILE...`: exit 0 when every file is formatted; exit 1 and a unified diff on stdout
   when one would change; exit 2 with `ail fmt needs ruff or black on PATH: pip install ruff` when neither exists. It
   never writes files (a `--write` mode is out of scope). It passes `--line-length` from `ail.toml` `[fmt]
   line-length` when present; the default is the formatter's own. Commit and push.
4. **Test and docs (15 min).** `test_ail_fmt.py`: the exit-2 message (always runs); with a formatter on `PATH`, exit
   0 on a formatted file, exit 1 and the diff on an unformatted one, and the C equality of 3 programs; without one,
   those cases skip with the reason. Register it. `docs/FORMAT.md`: what `ail fmt --check` does, the formatter search,
   the build-equality result. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_fmt.py` passes, locally with `/tmp/fmtvenv/bin` on `PATH` and in CI.
- `RESULTS.md`: 0 of 60 with a changed C, output or refusal; 60/60 check answers equal to `ruff format --check`.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if formatting changes the generated C or the output of any program: give the program and the smallest
diff; that is a compiler finding, not a formatter one. Stop at once and report if any build prints output different
from CPython (or from the reference this task names) without a refusal or a loud stop: give the program, both outputs
and the commit. Never commit a change that does that. Stop when 60 minutes pass. Push what is done first.

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


## Owner decision (2026-11-06)

- Wrap an existing formatter (ruff, falling back to black), and do not add it as a dependency. Tests that need it skip when it is absent.

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
