**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
# Review: relnotice1 (HEAD `ee738067`)

**What the change really does:** adds `THIRD_PARTY_NOTICES.md` (67-row inventory + follow-ups), copies the PSF-2.0 text to `AIL_CURRENT/stdlib/LICENSE-PSF.txt`, inserts one CPython-derivation line into 11 stdlib docstrings, adds `test_ail_third_party_notices.py` (6 tests; wheel check fails as documented), registers it in `tests.d/`, and regenerates the manifest. `ee738067` adds a `pkg-v12` header sweep that matches only `port of CPython` / `ported ... from CPython`.

**Probes**
- `/tmp/rprobes/use_modules.py` (imports/uses getopt, shlex, colorsys, keyword, stat, token, difflib, tomllib): `g` and `d` same stdout as CPython; `program.c` identical to base (only temp paths differ in `native_report.json`).
- `/tmp/rprobes/doc_getopt.py`, `/tmp/rprobes/doc_tomllib.py`: `module.__doc__` is refused by name — acceptable.
- Worker's 8 `/tmp/probes/*.py`: all same stdout on `g` and `d`.
- `/tmp/rprobes/notice_gap.py`: shows the missing inventory entries below.

**Report claims**
- Verified: `ee738067` is HEAD; both preludes listed with `Notice = no` and a follow-up; wheel contains both preludes; test is 6/5 pass/1 fail only on `LICENSE-PSF.txt`; `update_manifest.py --check` = 0; `test_ail_packaging`, `test_ail_files`, `test_ail_corpus_findings3`, and the 7 touched `test_ail_std_*` modules pass; no push (remote still at `995aa126`).
- **False as a completeness claim:** “Compiler sweep finds exactly `prelude_csv.py`, `prelude_format.py`; inventory now lists 13 CPython-derived files.” The sweep finds exactly those two only because its regex is too narrow; several other `pkg-v12` preludes explicitly declare CPython origins and ship in the wheel.
- **False/unverified:** “`test_ail_safetynet`: only `S4_generators_gc` fails.” It passed on HEAD in my run.

**Defects**

1. The inventory and the new sweep still miss CPython-derived `pkg-v12` preludes, so the wheel ships them without a notice and the test cannot catch them.
   Probe (first 15 lines vs. inventory):
   ```python
   # /tmp/rprobes/notice_gap.py
   import re, sys
   from pathlib import Path
   repo = Path(sys.argv[1])
   inv = set(re.findall(r'^\|\s*`([^`]+)`', (repo/'THIRD_PARTY_NOTICES.md').read_text(), re.M))
   for p in sorted((repo/'AIL_CURRENT/python/pkg-v12').glob('*')):
       if p.suffix not in ('.py','.c','.h'): continue
       head = '\n'.join(p.read_text(errors='replace').splitlines()[:15])
       if re.search(r"(?i)(algorithms? (?:are|is) (?:those|the ones) of CPython|CPython 3\.12's (?:Mersenne|calendar|_pydecimal|fractions|ipaddress)|follow CPython 3\.12's|error texts are those of CPython|of CPython 3\.12)", head):
           rel = p.relative_to(repo).as_posix()
           print(('LISTED  ' if rel in inv else 'MISSING '), rel)
   ```
   Expected: no `MISSING` rows (each such file inventoried with a CPython/PSF origin and a notice or follow-up).
   Actual: `MISSING` `prelude_decimal.py`, `prelude_fraction.py`, `prelude_html.py`, `prelude_ipaddress.py`, `prelude_random.py`, `pathlib_prelude.py`; also `prelude_calendar.py` and `prelude_numbers.py` by header inspection. Their headers say, e.g., “The algorithms are those of CPython 3.12's `_pydecimal.py`”, “CPython 3.12's Mersenne Twister … bit for bit”, “follow CPython 3.12's `pathlib.py`”. I confirmed all eight are in the built `ailc` wheel. `compiler_derived()` returns only `prelude_csv.py` and `prelude_format.py`, so `test_ail_third_party_notices` does not fail for these absent entries; `test_derived_CPython_files_have_the_notice` hard-codes `len(derived) == 13`, encoding the incomplete count.

**Pre-existing:** none found. `test_ail_safetynet` passed on HEAD.

**Unverified:** the claim that `S4_generators_gc` fails on base `995aa126` (not reproduced; possibly flaky).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1698565, "input": 43744, "output": 5868, "reasoning": 22969, "cache.write": 0, "cache.read": 1625984}]
    tool time: bash 24.8 min
        695s bash   cd /home/runner/work/ail-ci/ail-ci; date; timeout 900 python3 tools/par_check.py -j 2 test_ail_std_colorsys te
        234s bash   cd /home/runner/work/ail-ci/ail-ci; date; timeout 900 python3 tools/par_check.py -j 2 test_ail_packaging test_
        176s bash   cd /home/runner/work/ail-ci/ail-ci; date; timeout 900 python3 tools/par_check.py -j 2 test_ail_third_party_not
        145s bash   rm -rf /tmp/dh; mkdir -p /tmp/dh; cd /tmp; AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/
        135s bash   cd /tmp; date; for p in /tmp/probes/*.py; do n=$(basename $p); r=$(timeout 60 bash ~/tools/cmp.sh $p /home/run
         98s bash   cd /tmp/rprobes; cat > doc_getopt.py <<'EOF' import getopt print(repr(getopt.__doc__)) EOF cat > doc_tomllib.p
          1s bash   mkdir -p /tmp/rprobes; cd /home/runner/work/ail-ci/ail-ci; date; python3 AIL_CURRENT/test_ail_third_party_noti
          1s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'EOF' import sys, tempfile, zipfile from pathlib import Path s


--- ORIGINAL TASK ---
Lane: notice

# relnotice1: third-party notices for vendored and derived code (CPython stdlib copies, typeshed), checked by a test

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** files in the repository and in the `ailc` wheel that are copied or derived from third-party
code but carry no notice of where they come from and under which license. Not measured today. Known cases:
`AIL_CURRENT/stdlib/` holds AIL copies of CPython 3.12 modules (`getopt.py`, `difflib.py`, `shlex.py`,
`colorsys.py`, `keyword.py`, `token.py`, `stat.py`, `tomllib/`), which are under the PSF License; `third_party/typeshed`
has its own `LICENSE`; the root only has `LICENSE-MIT` and `LICENSE-APACHE`. Publishing `ailc` (roadmap P3) with PSF
code and no PSF notice is a license problem. The target: 0 such files without a notice, a `THIRD_PARTY_NOTICES.md`,
and a test that fails when a new derived file arrives without an entry.

Base: `origin/integ`. Files you may create or edit, and no others:
- `THIRD_PARTY_NOTICES.md` (new, repository root)
- `AIL_CURRENT/stdlib/LICENSE-PSF.txt` (new: the PSF License version 2 text, as printed in CPython's `LICENSE` file;
  copy it from `/usr/lib/python3.12/LICENSE.txt` or the system's CPython `LICENSE` file)
- the module docstring (first lines only) of each derived file under `AIL_CURRENT/stdlib/`, to add one line:
  `Derived from CPython 3.12 Lib/<name>.py; PSF License, see stdlib/LICENSE-PSF.txt.`
- `AIL_CURRENT/test_ail_third_party_notices.py` (new) and `AIL_CURRENT/tests.d/test_ail_third_party_notices.txt`
  (new, one line: `test_ail_third_party_notices`)
- the manifest files that `tools/update_manifest.py` writes
Do not edit `packaging/ail_wheel_backend.py` or `pyproject.toml`: another lane owns them. If the wheel needs a
change, write it in `THIRD_PARTY_NOTICES.md` under "Follow-ups" with the exact line to change.

## Sub-steps

1. **Inventory (20 min).** Find every vendored or derived file: everything under `third_party/` and
   `AIL_CURRENT/stdlib/`; any `.c`/`.h` copied from elsewhere (`zlib_glue.c` is AIL's own glue; check whether it
   copies zlib code); files whose header says "from CPython", "derived", "copied", "vendored", "Copyright" (grep
   `-i -E 'copyright|derived from|vendored|adapted from|license'` across `AIL_CURRENT`, `packaging`, `tools`, `lab`,
   `examples`). For each stdlib copy, confirm it is derived by comparing it with
   `python3 -c "import X, inspect; print(inspect.getsource(X))"`. Write the table (file, origin, license, already has
   a notice yes/no) into `THIRD_PARTY_NOTICES.md`. Commit, push, and open the PR against `integ`.
2. **Notices (20 min).** Add `LICENSE-PSF.txt` and the one-line docstring note to each derived stdlib file. Do not
   change code: only docstring text. Rebuild one program per touched module (from `lab/stdlib/<name>/`) to prove the
   docstring edit did not change its output. Fill `THIRD_PARTY_NOTICES.md`: for each origin, the license name, the
   license file path, and the list of files. Commit and push.
3. **Test (25 min).** Write `AIL_CURRENT/test_ail_third_party_notices.py`:
   - every file under `AIL_CURRENT/stdlib/` and `third_party/` is listed in `THIRD_PARTY_NOTICES.md` or is marked
     there as AIL's own;
   - every file marked as derived from CPython names `LICENSE-PSF.txt` in its first 15 lines;
   - every license file the notices name exists;
   - when a C compiler and the wheel backend are available: build the wheel into a temp dir
     (`ail_wheel_backend.build_wheel`) and check that `LICENSE-PSF.txt` and each derived stdlib file are in it, and
     the two root licenses are under `.dist-info/licenses/`. Report the wheel result as a test, not a skip, if it
     fails.
   Register the test (Appendix A rule 6). Commit and push.
4. **Verify (15 min).** Run the new test, `test_ail_packaging`, and the `test_ail_std_*` modules of every stdlib file
   you touched. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_third_party_notices.py` passes (or its wheel check fails with a follow-up written).
- 0 derived files without a notice; the count of derived files is in `THIRD_PARTY_NOTICES.md`.
- Every touched stdlib module's own test still passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a file's origin or license cannot be determined in 5 minutes; list it as "unknown" and go on.
Never guess a license. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`. (This job changes docstrings only.)
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

- `packaging/ail_wheel_backend.py`: `LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")` (line ~43) go to
  `.dist-info/licenses/`; `sdk_files()` selects compiler and `stdlib/` files from the manifest flags.
- `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`) finds `AIL_CURRENT/stdlib/*.py` for `import X`.
- The project license is MIT OR Apache-2.0; the PyPI name is `ailc`.

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
