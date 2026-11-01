**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does.** `work..HEAD` (2fafbd0 + 0aacd83) adds the 12 `lab/stdlib/decimal` programs and `test_ail_std_decimal`, makes `Decimal.as_tuple` build, and rewrites the int64 default to keep coefficients in a new `_DecInt` arbitrary-precision class with int64 fast paths (string arithmetic only on overflow). `stdtop.py` stops refusing `as_tuple`, and the manifest/docs/DEVLOG are updated. This matches the report, with two false claims (below).

**Verified**
- `test_ail_std_decimal`, `test_ail_stdtop1`, `test_ail_safetynet`: 3 modules, 0 failed; the decimal test builds and compares all 12 lab programs with CPython.
- `tools/update_manifest.py --check` exits 0.
- A program that does not import `decimal` produces byte-identical `program.c` / `program_mix0.c` on HEAD and `/tmp/base`.
- `lab/compare` is untouched by the diff, so its committed C is unchanged.
- Big-coefficient probes `r_big`, `r_boundary2`, `r_float`, `r_quant`, `r_places`, `r_long`, `r_hash` match CPython on both builds (int64 boundaries, negatives, add/sub/mul/div/mod/divmod, float construction incl. subnormals/1e308, quantize/sqrt/format, values via argument/list/attribute/dict). No silent wrap seen.
- `as_tuple` finite/NaN/inf/negative/empty, slicing, `_fields`, containment, `count`/`index`, concatenation, hashing, equality, unpacking match CPython.
- `int()` of a coefficient above int64 stops loudly, as declared.

**False claims / limitations**
- Report says `_DecTuple` supports `reversed`; it does not (defect 2). The worker's `p7_slice.py` never calls `reversed(t)` (only `t[::-1]`), so this was untested.
- Report says `s_mix.py` is 0.13 s. The real `s_mix.py` (with `Decimal(i)/Decimal("100")`) is ~50 s on HEAD (old 2fafbd0 ~81 s); 0.15 s is `s_mul.py` (no division). The "string algorithms only on overflow" wording is false for division, whose `10**shift` intermediate is big by construction. Not a regression vs 2fafbd0, but the number is mislabeled.

**Pre-existing (identical on base)**
- `hash(Decimal("NaN"))` is a random nonzero value in CPython but `0` in AIL (`_ail_dec_hash` k==2); base is also `0`.
- `reversed()` on any user class defining `__reversed__` fails in AIL (`r_revcls.py` fails on base too).

**Unverified**
- Worker probes `p1,p3,p4,p6,p7,p8,p9,p10,p11` not re-run; `test_ail_bytearray_decimal`, `test_ail_files`, `test_ail_corpus_findings3` not run; exact-int (`AIL_EXACT_INT=1`) not tested; no gdev instruction counts (prelude-only change).

VERDICT: FIX

1. `Decimal(d.as_tuple())` round-trip fails. Probe `/tmp/rprobes/r_roundtrip.py`:
   ```python
   from decimal import Decimal
   d = Decimal("1.2345"); t = d.as_tuple()
   print(isinstance(t, tuple)); print(Decimal(t))
   ```
   CPython: `True` then `1.2345`. AIL (g and d): `False` then `TypeError: conversion from _DecTuple to Decimal is not supported`, exit 1. `_DecTuple` is not a tuple, and `Decimal.__init__` only accepts `tuple`/`list`; `_ail_dec_from_tuple` already works with len/indexing, so accepting `_DecTuple` there fixes it. This is a common round-trip idiom and is a direct gap in the new `as_tuple` feature.
2. `reversed()` on the `as_tuple` result crashes. Probe `/tmp/rprobes/r_tuple.py` (minimal):
   ```python
   from decimal import Decimal
   print(list(reversed(Decimal("1.2345").as_tuple())))
   ```
   CPython: `[-4, (1, 2, 3, 4, 5), 0]`. AIL (g and d): `TypeError: '_DecTuple' object is not reversible`, exit 1, because the runtime's `reversed()` ignores a user class's `__reversed__`. The report explicitly claims `reversed` support, so either the claim or the feature must be corrected.
[cost $0.0541, opencode tokens {"total": 2619133, "input": 126572, "output": 9444, "reasoning": 36781, "cache.write": 0, "cache.read": 2446336}]
    tool time: bash 23.9 min
        366s bash   cd /home/runner/work/ail-ci/ail-ci && date; python3 tools/par_check.py -j 2 test_ail_std_decimal test_ail_stdt
        269s bash   cd /tmp && for name in old head; do dir=t_$name; [ "$name" = head ] && dir=t_head2; for p in s_mul s_div s_add
        113s bash   cd /tmp && rm -rf ts_head ts_base && mkdir ts_head ts_base && for pair in "head /home/runner/work/ail-ci/ail-c
        104s bash   cd /tmp/ts_head && echo "--- head s_mix out"; cat /tmp/head.s_mix.out; echo "--- head log tail"; tail -3 /tmp/
         91s bash   cd /tmp && rm -rf tsg_head tsg_base && mkdir tsg_head tsg_base && for pair in "head /home/runner/work/ail-ci/a
         85s bash   cd /tmp/rprobes && cat > r_roundtrip.py <<'EOF' from decimal import Decimal for s in ["1.2345", "-0", "1234567
         64s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/old && git worktree add /tmp/old 2fafbd0 2>&1 | tail -1; cd 
         60s bash   date; cd /tmp/rprobes && for p in r_places r_quant; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `decimal` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `decimal` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/decimal/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/decimal/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_decimal.py registered in tests.d), and compare them with CPython in the test.
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
