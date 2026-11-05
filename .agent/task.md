Lane: cliexb

# cliexb1: two data CLI tools in `examples/datacli/` (`histo`, `ini2json`), built by AIL, checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** example data tools in `examples/datacli/` that build in the default mode, reach the typed path and
print exactly what CPython prints: 0 today (the directory does not exist) -> 2/2, with wall time and binary size against
`python3` on a 20 MB input. (`examples/apps/` and `examples/textcli/` belong to other lanes; do not touch them.)

Base: `origin/integ`. Files you may create or edit, and no others:
- `examples/datacli/` (new): the 2 tools, `data/`, `gen_big.py`, `README.md`
- `AIL_CURRENT/test_ail_examples_datacli.py` (new) and `AIL_CURRENT/tests.d/test_ail_examples_datacli.txt` (new, one
  line: `test_ail_examples_datacli`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`.

## The tools

Ordinary, idiomatic Python 3 with type annotations on functions; no AIL-only imports. Each reads stdin, takes its options
from `sys.argv`, and is 30-80 lines.

1. `histo.py BINS`: one number per line (ints or floats; blank lines skipped; a line that does not parse is counted and
   reported on stderr as `skipped N`). Print `BINS` equal-width bins from min to max as
   `%12.4f %12.4f %8d  ####` with the bar scaled to 40 characters. Use the values `9223372036854775807` and
   `99999999999999999999` in one edge input: the tool must print what CPython prints or stop loudly.
2. `ini2json.py`: an INI file (`[section]`, `key = value`, `key: value`, `;` and `#` comments, keys lowercased, values
   stripped, a key before any section goes to `DEFAULT`) parsed by hand, without `configparser`. Print
   `json.dumps(result, indent=2, sort_keys=True)`. On a line it cannot parse, print `ini2json: line N: bad line` to
   stderr and exit 1.

## Sub-steps

1. **Tools and inputs (25 min).** Write the 2 tools and `examples/datacli/data/`: per tool one normal input and three
   edge inputs (empty stdin; and odd ones: no final newline, non-ASCII UTF-8, all values equal for `histo`, a bad line
   for `ini2json`, the big ints above). Check each with `python3`. Commit, push, and open the PR against `integ`.
2. **Build and compare (20 min).** Build each tool in the default mode and with `--strict`; run it on every input and
   compare stdout, stderr and the exit status with `python3`. If a tool falls back to the general path, rewrite it in
   plain idiomatic Python until it is typed, or record the fallback note. Commit and push.
3. **Measure (15 min).** Write `gen_big.py` (a 20 MB input per tool, fixed seed). Record in `README.md`: per tool the
   path, the stripped binary size, and the median of 5 wall times for AIL and `python3`. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_examples_datacli.py`: it builds the 2 tools and compares them with
   `python3` on every small input, in the default build and with `AIL_UNIFIED_FORCE=1`. It skips when there is no C
   compiler. Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- 2/2 tools match CPython (or stop loudly on the big-int input) on all 8 small inputs in both builds; the `README.md`
  table has 2 rows.
- At least 1 of the 2 builds with `--strict`.
- `python3 AIL_CURRENT/test_ail_examples_datacli.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop on any output that differs from CPython with no loud stop that you cannot remove by rewriting the tool in plain
Python; record the smallest repro in `README.md` under "Follow-ups". Stop when 80 minutes pass. Push what is done first.

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
