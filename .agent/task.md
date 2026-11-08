Lane: fa-selfhost
Needs: shast1

# shparse1: self-hosting parser part 1, expressions (`selfhost/src/ailparse.py`), identical to `ast.parse(mode="eval")`

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the share of S376 expressions that `ailparse.parse_expr` turns into a tree whose dump is
identical to `ast.dump(ast.parse(segment, mode="eval"))`. It is 0 today. The expressions are every `ast.expr` node
whose parent is a statement, with its text taken by `ast.get_source_segment` and wrapped in parentheses when it spans
lines. Attributes are off in this step, and shparse3 adds positions. The target is at least 99.5% identical at stage
1 and 0 accepted-but-different; everything else is refused with `ailparse: <construct> not supported`. A stage 2
check runs on 30 files.

Base: `origin/integ` after shast1. Files you may create or edit, and no others:
- `selfhost/src/ailparse.py` (new): consumes `ailtok` tokens and builds `ailast` nodes
- `selfhost/drv/expr_drv.py` and `selfhost/ref/expr_ref.py` (new: extract the segments, print one dump per line)
- `lab/selfhost/PARSE.md` (new), `lab/selfhost/MISCOMPILE.md` (append, only if needed)
- `AIL_CURRENT/test_ail_selfhost_parse.py` and `AIL_CURRENT/tests.d/test_ail_selfhost_parse.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Write a hand-written recursive-descent parser that follows the precedence of CPython 3.12's `Grammar/python.gram`,
not a PEG engine. Read the grammar, and copy no code: CPython is PSF-licensed, but the generated parser is not a model
for AIL.

## Sub-steps

1. **Operators and atoms (25 min).** Cover `lambda`, `x if c else y`, `or`/`and`/`not`, comparison chains
   (`a < b <= c`, `not in`, `is not`), `| ^ &`, shifts, `+ -`, `* / // % @`, unary operators, `**` (right
   associative, binding tighter than a unary minus on its left), `await`, and the primaries: attribute, call (positional,
   keyword, `*args`, `**kw`), subscript, slice and tuple index. Also cover the atoms: names, numbers, `True`, `None`,
   `...`, and strings with implicit concatenation. Run the expression set at stage 1. Commit, push, and open the PR
   against `integ`.
2. **Displays and f-strings (20 min).** Cover list, tuple, set and dict displays (with `**` unpacking), starred items,
   the four comprehension forms (with several `for`/`if` clauses and `async for`), the walrus `:=`, generator
   expressions as a sole call argument, and f-strings as `JoinedStr` and `FormattedValue` (conversion, nested format
   specs, `=` debugging specifiers as 3.12 expands them). Run all of S376. Commit and push.
3. **Stage 2 and test (15 min).** Build `expr_drv.py` with AIL and run it on 30 fixed S376 files. Write `PARSE.md`:
   identical, refused and different counts; the top 10 refused constructs; and stage 1 and stage 2 seconds. The test
   checks 200 fixed expressions at stage 1 and 20 at stage 2. Register it. Commit, push, and wait for CI.

## Done-check

- At least 99.5% of S376 expressions are identical at stage 1, with 0 accepted-but-different.
- Stage 2 equals stage 1 on the 30 files.
- `python3 AIL_CURRENT/test_ail_selfhost_parse.py` passes, and so do the 20 shards; the diff shows only the listed files.

## Stop rule

Stop on any wrong output (Appendix B): an accepted expression whose dump differs counts as one. Stop when 60 minutes
pass, and push what is done first.

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do
   not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus
   the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C and `DIR/native_report.json` the exact C compiler command. `-o` must not exist yet. A fallback to
  the general path prints `note: ... built on the general path ...` on stderr. Modules on `AIL_PATH` are found by
  `import` (`AIL_CURRENT/ail_modules.py`, line ~283).
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. CPython 3.12 is the
  oracle.
- Self-hosting layout (created by shport0 and shtok1): `selfhost/src/` holds the AIL-written ports. They are plain
  Python 3.12 that both CPython and AIL can run, and they import `ailtok`/`ailast`/`ailparse`, never `ast` or
  `tokenize`. `selfhost/drv/` holds the driver programs that print a canonical dump. `selfhost/ref/` holds
  CPython-only reference scripts that run the ORIGINAL compiler module on CPython's `ast`. `selfhost/seed/` holds the
  committed C seed. `tools/selfhost_diff.py` runs a reference and a candidate over a path list and counts identical,
  different and refused files.
- Three outputs are compared for every input: stage 0 (`selfhost/ref/`, the original module on CPython's `ast`),
  stage 1 (CPython running `selfhost/drv/` + `selfhost/src/`), and stage 2 (the AIL-built binary of the same driver).
- The differential corpus S376 is listed with sha256 in `selfhost/CORPUS.txt`: the 10 `lab/compare/src/*/typed.py`,
  the 10 `lab/compare/src/*/main.py`, the first 200 sorted `lab/corpus/programs/*/*.py`, and the 156 compiler files
  of the `lab/selfhost/CENSUS.md` scope.
- **Wrong output** means that stage 2 prints something different from stage 1 for the same source, or that stage 1
  differs from stage 0. A stage-2-only difference is an AIL miscompile, which is worth more than the port. Stop,
  write a reduced repro of 30 lines or less to `lab/selfhost/MISCOMPILE.md`, and report.

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
