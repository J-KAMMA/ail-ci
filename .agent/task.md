Lane: appmd

# appmd1: a real example app, `mdlite` (Markdown subset to HTML, about 300 lines of plain Python), built by AIL and checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** real apps of more than 200 lines that AIL builds from plain Python and that match CPython on
real inputs. The existing examples are small tools of 30-80 lines. Target: one 250-400 line app that builds in the
default mode, matches CPython byte for byte on at least 10 inputs (among them the repository's own docs), reaches
the typed path (or the exact fallback line is recorded), and has a measured speed and binary size against CPython.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `examples/mdlite/mdlite.py`, `examples/mdlite/README.md`, `examples/mdlite/RESULTS.md`
- `examples/mdlite/data/*.md` (6 hand inputs) and `examples/mdlite/make_big.py`
- `AIL_CURRENT/test_ail_examples_mdlite.py` and `AIL_CURRENT/tests.d/test_ail_examples_mdlite.txt` (one line:
  `test_ail_examples_mdlite`)
- the manifest files that `tools/update_manifest.py` writes
No compiler or runtime file is edited. A refusal is recorded, not fixed.

## The app (write it into README.md)

`mdlite [FILE]` reads Markdown from FILE or stdin and writes HTML to stdout. Supported: ATX headings `#`..`######`;
paragraphs; blank-line separation; `*em*`, `**strong**`, `` `code` ``; `[text](url)` links; fenced code blocks with an
optional info string (`<pre><code class="language-x">`); `-`/`*` bullet lists and `1.` ordered lists, one nesting
level by 2+ spaces; `>` block quotes (one level); `---` horizontal rule; HTML escaping of `&`, `<`, `>`, `"` in text and
code. Anything else is plain text. Exit 0; a missing FILE prints `mdlite: cannot open FILE` to stderr and exits 1.
Write it the way a Python user would: functions, a small class for the block state, `str` methods; no `re` (a hand
scanner), so the typed path has a chance.

## Sub-steps

1. **The app and inputs (35 min).** Write `mdlite.py` and 6 hand inputs that cover every feature, the nesting rules,
   unclosed emphasis, a fence without a closing line, empty input, and non-ASCII text (Japanese and an emoji). Check
   it under `python3`. Commit, push, and open the PR against `integ`.
2. **Build and compare (15 min).** Build with `python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/mdlite/mdlite.py
   -o /tmp/mdlite` (default mode), and record typed or general with the first fallback line. Compare stdout, stderr
   and the exit status with `python3` on the 6 inputs, on `docs/tutorial.md`, `docs/QUICKSTART.md`, `docs/INSTALL.md`,
   `README.md`, and on the missing-file case. Also build with `AIL_UNIFIED_FORCE=1` and compare. If the app falls back
   to the general path, record why; change the app's spelling only where an ordinary Python user would plausibly have
   written it that way, and list each change in `RESULTS.md`. Commit and push.
3. **Measure (15 min).** `make_big.py` (fixed seed) writes a 20 MB input from repeated, varied blocks into a temp
   dir. Measure AIL and CPython on it: instructions with `tools/icount.c`, wall median of 3, peak RSS
   (`/usr/bin/time -v`), and the AIL binary size. Write `RESULTS.md`: date, commit, path, the comparison table, the
   numbers, and every refusal or fallback as a follow-up with its exact text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_examples_mdlite.py` (structure of
   `AIL_CURRENT/test_ail_examples_tutorial_project.py`): build once, compare with `python3` on the 6 inputs, the 4 doc
   files and the missing-file case. Skip when there is no C compiler. Register it (Appendix A rule 6), run it, commit,
   push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_examples_mdlite.py` passes, with at least 10 inputs matching CPython.
- `mdlite.py` is 250-400 lines; `RESULTS.md` has the path, the speed ratio, RSS and binary size.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the app cannot build in the default mode without a compiler edit; give the first refusal line and
a 5-15 line reproducer. Stop when 80 minutes pass. Push what is done first.

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
