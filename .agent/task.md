Lane: fd-explain

# fdexp1: `ail explain <file>`: per-function typed / general status and the reason

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** functions whose typed/general status `ail explain` reports correctly, on a new 30-program probe
set. Today there is no such command: the default build prints one program-level `note: ... built on the general path
because ...` line, and `--strict --json` lists blockers. Target: at least 95% of the probe's functions correct, and 0
functions reported `typed` that the build does not compile on the typed path.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/explain.py` (new; runnable as `python3 -m ail_lang.explain FILE [--json]` from `packaging/`)
- `lab/explain/progs/*.py` (30 new programs) and `lab/explain/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_explain.py` (new) and `AIL_CURRENT/tests.d/test_ail_explain.txt` (new, one line:
  `test_ail_explain`)
- the manifest files that `tools/update_manifest.py` writes

The `ail explain` subcommand itself is wired into `cli.py` later by fdcli1; this job does not touch `cli.py`.

## Sub-steps

1. **Probe set and baseline (15 min).** Write 30 programs in `lab/explain/progs/`, 10-40 lines each, ordinary
   annotated Python 3.12: 10 fully typed, 10 with one function that falls to the general path (a dict return, a
   `str | None` mix, `int` used as a value, an untyped container, ...), 10 with blockers in two or three different
   functions, including a method and a nested function. Each file starts with `# expect: name=typed name=general ...`
   for every top-level function and method. Run the default build and `--strict --json` on all 30. Record in
   `RESULTS.md` under "Before": the default note, `blocker_count`, and whether `--strict --json` lists every blocked
   function or only the first. Commit, push, and open the PR against `integ`.
2. **The command (25 min).** `explain.py` builds the file once with `--strict --json` into a temporary directory and
   once in the default mode, and prints one line per function in source order:
   `prog.py:12 g  general  returning a dict, ...; write instead: ...` or `prog.py:3 f  typed`. A first line gives the
   program's status from the default build (`typed`, `general`, or `refused` with the message). If `--strict --json`
   reports only the first blocker, find the next one by building a temporary copy in which each blocked function's
   body is replaced with `raise NotImplementedError`, at most 10 rounds; mark those lines `(found after hiding f)`.
   A function never seen in any blocker list is `typed` only if the last round built with `--strict`; otherwise
   print `unknown`, never a guess. `--json` prints `ail.explain/1` with the same fields. The temporary copies never
   touch the user's file. Commit and push.
3. **Check against the expectations (10 min).** Run all 30. Count correct functions; fix `explain.py`, never the
   programs' expectations, unless the build itself proves an expectation wrong (then write that down). Commit and push.
4. **Test (10 min).** `test_ail_explain.py` runs explain on 8 of the programs (fast ones), compares the status column
   with the `# expect:` line, and checks that `--json` parses. It skips when there is no C compiler. Register it
   (Appendix A rule 6). Fill `RESULTS.md` "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_explain.py` passes.
- `RESULTS.md` shows at least 95% of the probe's functions correct and 0 false `typed`.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if neither `--strict --json` nor the hiding rounds can tell the status of a function without editing a
compiler file; name the hook that is needed (file, function). Stop at once and report if any build prints output
different from CPython (or from the reference this task names) without a refusal or a loud stop: give the program,
both outputs and the commit. Never commit a change that does that. Stop when 60 minutes pass. Push what is done first.

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
- The server: `packaging/ail_lang/lsp.py` (JSON-RPC over stdio, standard library only). Its docs: `docs/LSP.md`.
  Its test: `AIL_CURRENT/test_ail_lsp.py` (scripted sessions). Hover today shows a type only when it is certain from
  the source (literal-only names, annotations, signatures); a wrong type is worse than no type (lsp1b review).
- Diagnostics come from the same `ail check` front end that `ail build` uses; never write a second checker.
- `compile SRC -o OUT --strict --json` prints `ail.strict/1` JSON: `blockers[]` with `path`, `line`, `column`,
  `function`, `statement`, `construct`, `why`, `write_instead`, `blocks_functions` (checked 2026-11-06 on integ ff12fa93).

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
