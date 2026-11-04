Lane: census

# stdcensus1: a reproducible census of CPython's pure-Python stdlib on AIL, with ranked blockers

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** CPython 3.12 pure-Python stdlib modules that AIL builds: 1/197 (colorsys only, measured by hand on
2026-10-30 at integ 674bd7f6, never committed) -> a committed, re-runnable count on today's integ, plus a ranked table
"fixing blocker X unblocks N modules". The table picks the next front-end jobs. This job does not change the compiler.

Base: `origin/integ`. All new files go under `lab/stdcensus/` (new directory). Do not edit any other file. Do not edit
`lab/census/` (a different census) or any workflow.

## Method (the same as the 2026-10-30 census, so the numbers compare)

For a module `M`: make a temp dir; copy CPython's source of `M` into it (`M.py`; for a package such as `json` or
`email`, copy the whole package directory; for a dotted name such as `email.utils`, copy the top package). The local copy
shadows AIL's own model of the module, so CPython's code is what gets compiled. Write `main.py`:
`import M` (or `import email.utils`) and `print("ok")`. Build with
`python3 -B AIL_CURRENT/ail_chatgpt.py compile main.py --syntax python -o main` (`AIL_NO_CACHE=1`, timeout 120 s,
`ulimit -v 1500000`, at most 2 builds at a time). Results: `built-typed`, `built-general` (stderr has the general-path
note), `refused` (exit != 0), `timeout`. For a built one, run it and check that stdout is `ok\n` and the exit code 0 like
`python3 main.py`; a difference is `WRONG` (a silent bug: report it first). Record the first refusal line and all distinct
`not in the subset:` lines.

The module list is fixed (197 names; keep this order) in `lab/stdcensus/modules.txt`, one per line:

_collections_abc _compat_pickle _compression _distutils_system_mod _markupbase _osx_support _py_abc _pydatetime
_pydecimal _pyio _pylong _strptime _sysconfigdata__x86_64-linux-gnu _threading_local _weakrefset abc aifc argparse ast
asyncio base64 bdb bisect bz2 cProfile calendar cgi cgitb chunk cmd code codecs codeop collections colorsys compileall
concurrent.futures configparser contextlib contextvars copy copyreg crypt csv dataclasses datetime dbm decimal difflib
dis doctest email email.message email.parser email.utils enum filecmp fileinput fnmatch fractions ftplib functools
genericpath getopt getpass gettext glob graphlib gzip hashlib heapq hmac html html.entities html.parser http http.client
http.server imaplib imghdr importlib importlib.metadata inspect io ipaddress json json.decoder json.encoder json.scanner
keyword linecache locale logging logging.handlers lzma mailbox mailcap mimetypes modulefinder multiprocessing netrc
nntplib ntpath nturl2path numbers opcode operator optparse os pathlib pdb pickle pickletools pipes pkgutil platform
plistlib poplib posixpath pprint profile pstats pty py_compile pyclbr pydoc queue quopri random re re._casefix
re._compiler re._constants re._parser reprlib rlcompleter runpy sched secrets selectors shelve shlex shutil signal site
sitecustomize smtplib sndhdr socket socketserver sqlite3 ssl stat statistics string stringprep struct subprocess sunau
symtable sysconfig tabnanny tarfile telnetlib tempfile textwrap threading timeit token tokenize trace traceback
tracemalloc tty turtle types typing unittest urllib urllib.parse urllib.request uu uuid warnings wave weakref webbrowser
wsgiref.util xdrlib xml xml.dom.minidom xml.etree.ElementTree xml.sax zipapp zipfile zipimport zoneinfo

A name that does not exist on the runner's Python (for example `_sysconfigdata__x86_64-linux-gnu` on a different
platform, `sitecustomize`) is recorded `absent`, not dropped.

## Sub-steps

1. **Runner script (20 min).** Write `lab/stdcensus/modules.txt` and `lab/stdcensus/run.py` (CPython only; argument
   `-j 2`, `--only NAME...`, writes `lab/stdcensus/results.jsonl`, one JSON object per module: name, result, path,
   build seconds, first reason, all reasons). Find CPython's source with `sysconfig.get_path("stdlib")`. Try it on
   `colorsys`, `keyword`, `bisect` and `json`. Record the Python version and integ sha in each run. Commit, push, open the
   PR against `integ`.
2. **Full run (25 min).** Run all 197 at `-j 2`. Commit `results.jsonl`.
3. **Buckets (20 min).** Write `lab/stdcensus/report.py`: it reads `results.jsonl` and writes `lab/stdcensus/RESULTS.md`
   with (a) the counts per result; (b) every module's row (result, seconds, first reason, cut to 160 chars);
   (c) the blocker buckets. A bucket is a refusal text with names and numbers replaced by placeholders (for example
   `os.X is not built`, `import of 'X' guarded by except ImportError`, `a generator expression used as a value`,
   `a class-level constant built through ...`). For each bucket give: modules whose ONLY reasons are in this bucket
   ("fixing this alone unblocks N"), modules that list it at all, and one minimal 3-8 line reproducer program you wrote
   and checked (it is refused with that text, and CPython runs it). Sort by "unblocks alone", then "listed". Put the
   reproducers in `lab/stdcensus/repro/<bucket-slug>.py`. Commit.
4. **Compare (10 min).** Add a short section "Since 2026-10-30": 1/197 then, the count now, and modules whose result
   changed (the old first reasons are not in the repo; compare counts only, plus `colorsys` built then). Any `WRONG`
   result goes at the top with the exact output difference. Push.

## Done-check

`lab/stdcensus/` has `modules.txt`, `run.py`, `report.py`, `results.jsonl`, `RESULTS.md`, and at least the top 10 bucket
reproducers. `python3 lab/stdcensus/report.py` re-creates `RESULTS.md` byte for byte. 20 shards pass (no compiler file
changed, so they should).

## Stop rule

If the full run would take more than 30 minutes, cut it at 30 minutes, record the unfinished names as `not run`, and go on
to the buckets. Do not fix any blocker in this job. Stop at 80 minutes; push what is done.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. Turning a
   correct program into a refusal or a stop is a regression. When a new fast path cannot handle a case, keep the old route.
2. Probe ints beyond int64 wherever ints come from text, fields or arithmetic. Run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, and compare both with `python3`.
3. Push early and open the PR against `integ`. Wait for all 20 `shard` checks on your head commit
   (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `origin/integ` (or from one unmerged PR at most; never from a PR that is itself stacked).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: add `AIL_CURRENT/tests.d/<module>.txt` (one line: the module name), `git add` every new file, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, tag, publish, change repository settings, cancel runs, or edit
   `.github/workflows`.
8. Files owned by busy lanes; do NOT edit them: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, `packaging/ail_lang/cli.py`.
   Also do not edit `DEVLOG.md` or `AIL_CURRENT/DEVLOG.md` (integration writes them). If a fix needs one of these files,
   do not make it: write a finding (file, function, what is needed, the refusal text) in your results file and go on.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.py -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it prints
  `note: ... built on the general path` on stderr. No such note = typed. `--strict` = typed path or refuse.
  `DIR/program.c` is the generated C. Use `AIL_NO_CACHE=1` for timings.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- Model test file: `AIL_CURRENT/test_ail_std_statistics.py` (build each program in a temp dir, run it, compare stdout and
  exit code with `python3 <program>`).
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS < input`. If `perf_event_open` is refused, run `sudo sysctl -w kernel.perf_event_paranoid=1`
  once; if it is still refused, use the median of 5 wall times and say so in the results.
- The oracle is CPython 3.12 (`python3`). Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints.

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
