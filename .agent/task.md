**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review of `7fba184` (change `work..HEAD`: `51ddaee`, `7fba184`)

**What the change really does.** It fixes review 1: non-finite/imaginary exponents in `_ail_cm_pow` now map to CPython's `ZeroDivisionError`/`OverflowError`/NaN, the integer `**` fast path is shared with reflected powers and checks overflow, and `cmath.f(...)` calls containing `**mapping` are lowered to a runtime `_ail_cm_kw` that parses arguments like CPython (explicit keywords, mappings, `*args`). Only `cmathlib.py` and `prelude_cmath.py` change.

**Probes run** (`cmp.sh`, both g and d builds):
- `rv_pow`, `rv_rpow`, `rv_plain`, `rv_dataflow`, `rv_kw5`, worker's `p_pow2`, `p_star2`, `p_powgrid`, `p_powedge`, `p_over`, `p_minbad` — same stdout as CPython; review 1 defects 1 and 2 are fixed.
- `rv_kw` — `**` mapping semantics (empty/non-empty, `a`/`b`/tols, duplicates, non-string keys, custom `keys()`, non-mapping list/int/None/str/tuple, `*list + **`) match except the star error below.
- `rv_zeroexp`, `rv_min1` — **DIFF/crash** (defect 1); base matches CPython.
- `rv_starbase` — **DIFF** (defect 2).
- Plain non-cmath program: `program.c` byte-identical to `/tmp/base`. No `lab/compare/src` task imports `cmath`, so all 10 C files are unaffected (stronger than the report's 5).
- `test_ail_std_cmath`, `test_ail_safetynet` on HEAD: 2/2 pass (272 s). `update_manifest.py --check`: rc=0.

**Defects**
1. Regression: zero base with a large integral float exponent now crashes instead of returning `0j`. Removing the zero-base early return makes `math.floor(b.real)` run before the `abs(b.real) <= 100` guard, so AIL's int-based `floor` raises.
   ```python
   import cmath
   print(0j ** 1e300)
   print(0.0 ** complex(1e300, 0.0))
   print(0j ** 1e19)
   ```
   Expected `0j\n0j\n0j` (CPython and `/tmp/base` both print this). Actual: no stdout, `OverflowError: integer overflow in int(float) (ints are 64-bit; --exact-int gives exact ints)`, exit 1, both builds. Reorder `abs(b.real) <= 100.0` before `math.floor`, or restore the zero-base early path.
2. The new `*args` collection loses CPython's star message: `_ail_cm_args` iterates the value directly.
   ```python
   import cmath
   print(cmath.isclose(*5, **{}))
   ```
   Expected `TypeError: cmath.isclose() argument after * must be an iterable, not int`. Actual `TypeError: 'int' object is not iterable`. Base gave a named compile-time refusal (`a **kwargs call argument`), which was acceptable; the change introduced this wrong runtime message. Only invalid starred operands are affected.

**Report claims.** Non-finite powers fixed: verified. `**mapping` / non-mapping / custom mappings / non-string keys / duplicates: verified, except the invalid-star message ("`*args + **` match" is false for a non-iterable `*`). Reflected-power claims (`inf ** (2+0j)`, `inf ** (1+0j)`): verified. `lab/compare` C unchanged: verified (all 10, via no-cmath sources + a plain-program C diff). Tests 2/2 rerun pass; `test_ail_files`/`test_ail_corpus_findings3` not rerun (per scope). Manifest check rc=0: verified. "`p_powbig` int(float) overflow pre-existing": true for non-zero bases, but the zero-base form is new (defect 1).

**Pre-existing.** Non-zero base with a huge integral float exponent (`(2+0j) ** 1e300`, `1j ** 1e300`) has the same `int(float)` overflow / wrong messages on base. `_ail_cm_tname` still falls back to `object` for user types. `cmath.isclose(1.0, a=1.0, b=1.0)` is a named compile-time refusal on base and HEAD alike.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`; speed (no non-cmath hot code touched, so not measured); pathological custom mappings that mutate during `**` expansion.

VERDICT: FIX
[cost $0.0400, opencode tokens {"total": 1908167, "input": 89585, "output": 10854, "reasoning": 24432, "cache.write": 0, "cache.read": 1783296}]
    tool time: bash 15.8 min
        273s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_cmath test_a
         94s bash   cd /tmp/rprobes && for p in rv_rpow rv_dataflow rv_plain; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/rpro
         83s bash   cd /tmp/rprobes && for p in p_powgrid p_over p_minbad; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.
         79s bash   cat > /tmp/rprobes/rv_min1.py <<'EOF' import cmath print(0j ** 1e300) print(0.0 ** complex(1e300, 0.0)) print(
         72s bash   cd /tmp/rprobes && for p in rv_pow rv_rpow rv_kw; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.p
         64s bash   cd /tmp/rprobes && printf 'import cmath\ndef show(l,f):\n    try: print(l, repr(f()))\n    except Exception as
         59s bash   cd /tmp/rprobes && for p in p_star2 p_pow2; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /home/ru
         54s bash   cat > /tmp/rprobes/rv_zeroexp.py <<'EOF' import cmath def show(label, f):     try:         print(label, repr(f


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `cmath` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `cmath` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/cmath/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/cmath/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_cmath.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
