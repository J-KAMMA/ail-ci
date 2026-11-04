Lane: stdlex

# stdlex1: `import keyword` and `import token` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/`)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/keyword/` and `lab/stdlib/token/` that build in the default mode and
print what CPython prints, and how many of them are typed. The stdlib census (`lab/stdcensus/RESULTS.md`) has
`keyword` built-general (`field '__contains__' requires a class instance`, from
`iskeyword = frozenset(kwlist).__contains__`) and `token` refused (`the name 'globals' is not a known
function/class/builtin`, from `tok_name` built over `globals()`). Target: at least 11/12 programs build and match,
and every `keyword` program is typed. Both modules are what small linters, highlighters and code generators import.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/keyword.py` and `AIL_CURRENT/stdlib/token.py` (new)
- `lab/stdlib/keyword/*.py` (6 new programs), `lab/stdlib/token/*.py` (6 new programs),
  `lab/stdlib/keyword/RESULTS.md` (new; covers both modules)
- `AIL_CURRENT/test_ail_std_keyword.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_keyword.txt` (new, one line:
  `test_ail_std_keyword`)
- the manifest files that `tools/update_manifest.py` writes

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import keyword` (Appendix B), as
`AIL_CURRENT/stdlib/getopt.py` and `shlex.py` already are. Follow `AIL_CURRENT/stdlib/shlex.py` and
`AIL_CURRENT/test_ail_std_shlex.py` as models.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs, each 15-40 lines of ordinary Python 3.12. Together they
   cover: `keyword.kwlist`, `keyword.softkwlist`, `keyword.iskeyword(s)`, `keyword.issoftkeyword(s)` on keywords, soft
   keywords (`match`, `case`, `_`, `type`), non-keywords and `""`; `iskeyword` passed as a value
   (`[w for w in words if keyword.iskeyword(w)]` and `filter(keyword.iskeyword, words)`); a tiny identifier checker
   (`s.isidentifier() and not keyword.iskeyword(s)`); `token.NAME`, `token.OP`, `token.NUMBER`, `token.ENDMARKER`,
   `token.tok_name[n]`, `token.ISTERMINAL`, `token.ISNONTERMINAL`, `token.ISEOF`, `token.EXACT_TOKEN_TYPES["+="]`,
   `token.N_TOKENS`, and a loop that prints the whole `tok_name` table sorted. Build each with the default command and
   record typed, general or refused, with the first refusal or fallback line, in `RESULTS.md` under "Before". Commit,
   push, and open the PR against `integ`.
2. **The modules (25 min).** Write `keyword.py` and `token.py` from CPython 3.12's sources (print them with
   `python3 -c "import keyword, inspect; print(inspect.getsource(keyword))"`). Keep every public name and value.
   Rewrite only what the compiler refuses: `iskeyword` and `issoftkeyword` become `def`s over a set
   (`def iskeyword(s: str) -> bool`), and `tok_name` becomes an explicit dict literal generated once from CPython's
   values (write a one-off generator command in the module docstring so it can be regenerated). Keep `__all__`. Add
   annotations that help the typed path. Commit and push.
3. **Make the programs pass (20 min).** Build all 12 again. Fix the modules, never the programs, until the target is
   met. A refusal that needs a compiler file goes into `RESULTS.md` as a follow-up with the exact refusal text. Commit
   and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_keyword.py`, copying the structure of
   `test_ail_std_shlex.py`. It builds every passing program and compares stdout and exit status with `python3`, in the
   default build and again with `AIL_UNIFIED_FORCE=1`. It also asserts `keyword.kwlist`, `softkwlist`, `tok_name` and
   `EXACT_TOKEN_TYPES` of the bundled files equal CPython's (load them with `runpy` under `python3`). It skips when
   there is no C compiler. Register the test (Appendix A rule 6) and run it. Fill `RESULTS.md` under "After". Commit,
   push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_keyword.py` passes.
- At least 11 of the 12 programs build and match CPython in both builds; every `keyword` program is typed.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `keyword.py` is not picked up by `import keyword` (the compiler may treat `keyword` as
built in); give the exact message. Also stop if fewer than 6 programs can pass without editing a compiler file; name
each blocking refusal. Stop when 80 minutes pass. Push what is done first.

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
