Lane: shseed

# shseed1: self-hosting prep, an estimate of the committed C seed's size (measurement only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the expected size of the C seed. The self-hosting plan commits the generated C of the
AIL-written compiler, so that a user can build AIL with only a C compiler. If that C is hundreds of MB, the plan
changes (split files, compression, or a smaller seed). Today there is no estimate. The target is a low/mid/high
estimate in bytes of C source and of the `-O2` binary, with a fitted ratio and its error. No compiler file is edited.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `tools/selfhost_seed_estimate.py`
- `lab/selfhost/seed_corpus.json` and `lab/selfhost/SEED.md`
- `AIL_CURRENT/test_ail_selfhost_seed.py` and `AIL_CURRENT/tests.d/test_ail_selfhost_seed.txt` (one line:
  `test_ail_selfhost_seed`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **The corpus run (25 min).** Write `tools/selfhost_seed_estimate.py`. Pick at least 40 programs that build today:
   `lab/stdlib/*/*.py`, `examples/algos/*.py`, `examples/textcli/*.py`, `examples/mdlite/*.py`, and the compare-lab
   `typed.py` and `main.py` sources. Prefer programs over 100 lines, and include some that import a bundled module from
   `AIL_CURRENT/stdlib/`. For each, build with `--debug-dir` in the default mode and record: source lines (without
   blank and comment lines), AST node count (`ast.walk`), top-level functions and classes, typed or general,
   `program.c` bytes, and stripped binary bytes. Also build a bare `print("ok")` twice, typed and general, to get
   the fixed runtime part. Use `ulimit -v 1500000` and at most 2 builds at a time. Write `seed_corpus.json`
   (`schema: ail.selfhost_seed/1`, base commit). Commit, push, and open the PR against `integ`.
2. **The fit (15 min).** Subtract the fixed runtime part, then fit C bytes per AST node and per source line,
   separately for typed and general builds (least squares through the origin; report R² and the median absolute
   error in %). Count the compiler's own lines and AST nodes over the scope of `lab/selfhost/CENSUS.md` with `ast`
   (do not compile them). Give three estimates: low (all typed, best fit), mid (the typed/general mix of the corpus),
   high (all general, worst decile ratio). Commit and push.
3. **Report and test (20 min).** Write `lab/selfhost/SEED.md`: the corpus table summary, the fits, the three
   estimates for C bytes, gzip bytes of that C (measure the corpus's gzip ratio), and the binary, and how each
   compares with GitHub's 100 MB file limit and with today's Python sources (205k lines). Say plainly which
   assumptions could make the estimate wrong. Write `AIL_CURRENT/test_ail_selfhost_seed.py`: it checks that the JSON
   parses, has at least 40 rows, and that the three estimates in `SEED.md` equal what the tool computes from the
   JSON (`--report-only`, no builds). Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- `seed_corpus.json` has at least 40 measured programs plus the two bare builds.
- `SEED.md` gives low/mid/high in bytes for C, gzip and binary, and R² for each fit.
- `python3 AIL_CURRENT/test_ail_selfhost_seed.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if fewer than 25 programs build, or if R² is below 0.5 for both fits (report the scatter instead of an
estimate). Stop when 60 minutes pass. Push what is done first.

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
