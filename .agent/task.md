**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
# Review: html2 bundled `html` package

**What the diff really does:** adds `AIL_CURRENT/stdlib/html/{__init__.py,entities.py}` (typed `escape`, a scan-loop `unescape`, and 2231-entry entity tables) plus 12 lab programs, a test module, and manifest pins. This matches the report's description, with one undisclosed deviation: 133 `html5` values and their copies in `_html5` are `"?"` instead of CPython's astral characters (only the source docstrings say so; `RESULTS.md` does not).

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both builds):
- `p1_astral_named.py`: `html.unescape("&Afr;&bopf;&Sopf;&Zopf;")` → expected `'𝔄𝕓𝕊ℤ'`, actual `'???ℤ'`; `'&Afr;'` → expected `'𝔄'`, actual `'?'`. **Both builds. DEFECT.**
- `p2_numeric_astral.py`: default build matches CPython (`😀`); general path exits 3 `AIL limit: chr_non_bmp`. Base behaves identically for a runtime `chr(128512)` → pre-existing.
- `p3_named_boundaries.py` (`&amp`, `&ampx`, `&notit;`, `&`, `&&`, `&#x`, 32/40-char names): both builds match.
- `p4_numeric_edges.py` (`&#0;`, `&#0000065;`, 30-digit, `&#X41`, surrogates, 0x10FFFF): both builds match.
- `p5_shapes.py` (escape quote true/false, argument/list item/attribute/dict value, alias + list mutation): both builds match.
- Pure-Python fuzz of the bundled `unescape` vs `html.unescape` (200k random strings + boundary codepoints): 0 mismatches; `_invalid_charrefs`/`_invalid_codepoints` equal; only the 133 astral names differ.
- Non-html program: `--debug-dir/program.c` byte-identical to base (`p6_nohtml.py`).

**Guard tests:** `test_ail_pre105` on HEAD fails 17 subtests (expected `"import of 'html'"`; got the mixed-import error and `no module named 'html.parser'`); it passes on `/tmp/base`. `test_ail_pre27/pre52/stdtop4` were still running after 7 minutes and I killed them at the time box — unverified.

**Claims:** 01/03 escape-only typed with only the `shadows … html` note — verified (02 not run). `11_roundtrip` matches both builds — verified. 08/09/12 general path — unverified. "11/12 match CPython" — consistent with the toy programs but false as a general statement of semantics: astral named refs return `'?'`. Build time not met — consistent with the observed multi-minute `entities` builds, not re-measured.

**Defects**
1. `test_ail_pre105` regression (required guard test): `import math, html` is no longer refused naming `html`. Expected: refusal containing `"import of 'html'"`; actual: `one import statement mixes local modules…`. Broken by the bundled package, and `RESULTS.md` confirms it.
2. Silent wrong values for astral named references. Probe `p1_astral_named.py`:
   - `html.unescape("&Afr;&bopf;&Sopf;&Zopf;")` expected `'𝔄𝕓𝕊ℤ'`, actual `'???ℤ'`
   - `html.entities.html5["Afr;"]` expected `'𝔄'`, actual `'?'` (133 entries differ)
   Both builds. The default build demonstrably produces astral characters (`chr(0x1F600)` probe prints `😀`), so the "16-bit runtime" justification is false on the typed path; the table should keep CPython's values or the general path should refuse by name rather than corrupt.
3. Task requirement not met: importing `html.entities.html5` takes ~260 s vs the required <0.42 s (2× hello world). Disclosed, but the number the task asked for is missed.

**Not checked:** `test_ail_std_html.py` (its 12×2 builds include 260 s entities programs — not run), `test_ail_pre27/pre52/stdtop4` (killed at time box), exact build-time medians.

VERDICT: FIX
1. `test_ail_pre105` fails 17 subtests: expected refusal naming `html` (`"import of 'html'"`), actual mixed-import error / `no module named 'html.parser'` (`prog.py:1:1`).
2. `p1_astral_named.py`: expected `'𝔄𝕓𝕊ℤ'` and `'𝔄'`, actual `'???ℤ'` and `'?'`; `html.entities.html5` has 133 wrong (`'?'`) values.
3. Build-time target missed (~260 s vs required <0.42 s for an `html.entities.html5` import).
[commandcode stop=end_turn turns=33 out_tokens=20874]

## fix round skipped: only 50 minutes left


--- ORIGINAL TASK ---
Lane: htmlmod

# html2: `html.unescape` and `html.entities` as a bundled AIL package (`AIL_CURRENT/stdlib/html/`), `html.escape` kept typed

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/html/` that build in the default mode and print what CPython prints,
with the same exit status. On `integ` today `html.escape` builds on the typed path and matches, but
`html.unescape` is refused (`not in the subset: html.unescape is not supported`) and `html.entities` is not
available. Target: at least 10/12 programs, with every program that uses only `html.escape` still typed. Second
number: build time of a program that imports the 2231-entry `html.entities.html5` table (median of 3,
`AIL_NO_CACHE=1`), which must stay under 2x a hello-world build; record both.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/html/__init__.py` and `AIL_CURRENT/stdlib/html/entities.py` (new)
- `lab/stdlib/html/*.py` (12 programs) and `lab/stdlib/html/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_html.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_html.txt` (new, one line:
  `test_ail_std_html`)
- the manifest files that `tools/update_manifest.py` writes

**Regression guard.** Four existing tests use `html.escape`: `test_ail_pre105`, `test_ail_pre27`, `test_ail_pre52`,
`test_ail_stdtop4` (find them again with `grep -l "html" AIL_CURRENT/test_*.py`). A bundled package may replace the
compiler's own model of `html.escape`. Run those four before and after your change; they must pass, and a program
that used only `html.escape` must still build with no general-path note.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/html/`, each 15-40 lines of ordinary
   Python 3.12. Together they cover: `escape` with `quote=True` and `quote=False` (keep at least 3 escape-only
   programs); `unescape` of named references with and without the `;` (`&amp`, `&ampx`, `&notit;`), numeric
   (`&#65;`, `&#x41;`, `&#X41`), invalid code points (`&#0;`, `&#x80;` to `&#x9f;` mapped by CPython's table,
   `&#xd800;`, `&#x110000;`, a 30-digit number, which is beyond int64 and must give CPython's `\ufffd`, not a stop),
   text with no `&`; `html.entities.name2codepoint`, `codepoint2name`, `entitydefs` and `html5` lookups; a small tool
   that strips tags with a loop and unescapes the text; a round trip `unescape(escape(s)) == s` over a fixed list.
   Build each with the default command; record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before (integ <short sha>)". Run the four guard tests and record the result. Commit, push, and
   open the PR against `integ`.
2. **The package (25 min).** Write `AIL_CURRENT/stdlib/html/entities.py` from CPython 3.12's `Lib/html/entities.py`
   (generate it with a short script from `html.entities`, keep the dict order; do not hand-type the table) and
   `AIL_CURRENT/stdlib/html/__init__.py` from `Lib/html/__init__.py`: `escape`, `unescape`, `_replace_charref`,
   `_invalid_charrefs`, `_invalid_codepoints`, `_charref`. Write `escape` with `str.replace` calls in CPython's order so
   it stays typed. `unescape` uses `re.sub` with a function: if the compiler refuses that, rewrite it as a scan loop
   with the same results, and write the rewrite in the docstring. The numeric branch must not convert a
   30-digit number to int64: check the length (or compare as text) before `int()`, as CPython's result for it is
   `\ufffd`. Commit and push.
3. **Make the programs pass (20 min).** Build all 12 again in the default build and with `AIL_UNIFIED_FORCE=1`. Fix the
   package, never the programs, until at least 10 build and match and the escape-only programs are typed. Run the
   four guard tests. Measure the build-time number. If importing the package prints a note such as
   `shadows the standard library module html` on stderr, record it in `RESULTS.md` as a follow-up for
   `ail_modules.py` (do not edit that file). Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_html.py`, copying the structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: it builds every passing program and compares stdout and the exit status with
   `python3`, in both builds, asserts no general-path note for the escape-only programs, and skips when there is no
   C compiler. Register it (Appendix A rule 6). Run
   `python3 tools/par_check.py -j 2 test_ail_std_html test_ail_pre105 test_ail_pre27 test_ail_pre52 test_ail_stdtop4`.
   Fill `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_html.py` passes, and so do the four guard tests.
- At least 10 of the 12 programs build and match CPython in both builds; escape-only programs are typed.
- `RESULTS.md` has the before/after table and the build-time row.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the bundled package makes any guard test fail or moves an escape-only program to the general
path and you cannot fix it inside the package in 15 minutes; give the exact message. Stop if a bundled package
directory is not picked up by `import html`. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/` are standard modules shipped as AIL source; a package is a directory with an
  `__init__.py`. `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`, line ~85) searches them after the program's own directory
  and `AIL_PATH`. Examples: `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
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
