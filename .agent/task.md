**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: `job decexact2` (Decimal/Fraction exact internals in int64 mode)

**What the change really does.** Adds `exact_depth` to the runtime: overflow in `+ - * unary- // << **` and int-from-string construction promotes to a big int only when `exact_depth > 0` (or in `--exact-int`, where `main` starts it at 1). A program using Decimal/Fraction is forced onto the big-int runtime (`pyboxed2.build`); prelude functions/methods enter/leave the depth and scan their return value for a big int when leaving to user code. Fraction's fields become `_n`/`_d` with `numerator`/`denominator` properties. This matches the report.

**Verified (probes run with `cmp.sh` on HEAD and `/tmp/base_w2`):**
- Acceptance values (`p_accept`): both builds match CPython for `1/3`, `sqrt`, `10.50*3`, `2**100`, prec 50, `1e30+1`, Fraction cases.
- Visible ints: `int()`, `__int__`, `__trunc__`, `__floor__`, `__ceil__`, `as_integer_ratio`, `.numerator`, `.denominator`, `round(Decimal(...))` stop loudly in int64 mode; `int(Decimal(2)**62)` works, `**63` stops, `INT64_MIN` works. `as_tuple` refused by name identically to base (pre-existing).
- Exact mode: `p_ratio_dec`, `p_num`, `p_int_dec`, `p_userbig2` with `AIL_EXACT_INT=1` match CPython.
- No depth leak after a Decimal exception; user code still stops on `x**100` after a Decimal call.
- No-Decimal C: `program.c` byte-identical base vs HEAD for all 10 `lab/compare` `main.ail` and the 6 `main.py` that build; report JSON differs only in temp paths.
- Tests: `test_ail_int64_default`, `test_ail_stdtop1`, `test_ail_safetynet` all pass (542 s); `update_manifest.py --check` clean.

**Claims / false:** DEVLOG/DIFFERENCES say `int()`, `__trunc__`, `__floor__`, `__ceil__`, `__round__` and `as_integer_ratio` are "covered by the same return check". False: the guard is inserted only before the function's final `return AIL_OK` (`pyboxed2.py:4263-4267`), so source-level early returns bypass it.

### Defects
1. Big ints escape to user code through prelude early returns, enabling arbitrary-precision *user* arithmetic (the behaviour the task forbids).
   - `p_roundfrac.py`: `print(round(Fraction(2) ** 100))` — expected named stop (base: `OverflowError: integer overflow in **`); actual HEAD: exit 0, prints `1267650600228229401496703205376`.
   - `p_floordivfrac.py`: `print((Fraction(2) ** 100) // 1)` — expected stop; actual prints the big int, exit 0.
   - `p_dec_mathfloor.py`: `math.floor(Decimal(2) ** 100)` / `math.ceil(...)` — expected stop; actual prints `1267650600228229401496703205000` (the `_ail_dec_floor` helper's early return leaks it).
   - `p_leaktyped.py`: leaked `n = (Fraction(2)**100) // 1` then `print(add(n, 1))` — expected stop; actual prints `1267650600228229401496703205377` (base stopped). Same leak works through a list item, dict value and `n+1`, `n*2`, `n%7`.
   Cause: `Fraction.__floordiv__`/`__round__` (and the stdtop `_ail_dec_floor`/`_ail_dec_ceil` helpers) return from inside `if` branches; only the tail return gets `ail_exact_visible`.
2. Minor: `Fraction(1,2).numerator = 3` silently succeeds and has no effect; CPython raises `AttributeError`. Base also differed (it allowed it with effect), so this is a new mismatch, not a fixed defect.

**Pre-existing:** `Decimal.as_tuple()` refused by name on both base and HEAD; `Fraction.numerator` assignment was already non-CPython on base.

**Unverified:** gdev `icount` runs (non-Decimal `program.c` is byte-identical, so no run-count change expected); Decimal paths beyond those probed.

VERDICT: FIX
1. Apply the `exact_depth == 1` visibility check to every successful return of a Decimal/Fraction prelude function, not only the final tail return (at minimum `Fraction.__floordiv__`, `Fraction.__round__`, `Fraction.__hash__`, and the stdtop `_ail_dec_floor`/`_ail_dec_ceil` helpers); otherwise `round(Fraction(2)**100)`, `(Fraction(2)**100)//1`, `math.floor/ceil(Decimal(2)**100)` print big ints and user code then computes with them exactly in int64 mode. Expected: loud `OverflowError: integer overflow in int()` (exit 1); actual: exit 0 with the big value printed.
[cost $0.0400, opencode tokens {"total": 2647079, "input": 99057, "output": 9222, "reasoning": 20144, "cache.write": 0, "cache.read": 2518656}]
    tool time: bash 51.2 min
        608s bash   cd /tmp/rprobes && for p in p_accept p_int_dec p_int_frac p_ratio_dec p_ratio_frac p_num p_den p_round p_trunc
        543s bash   cd /home/runner/work/_temp/w2 && timeout 1500 python3 tools/par_check.py -j 2 test_ail_int64_default test_ail_
        470s bash   cd /tmp && rm -rf cdiff && mkdir cdiff && cd cdiff && for f in /home/runner/work/_temp/w2/lab/compare/src/*/ma
        341s bash   cd /tmp/rprobes && for p in p_roundfrac p_mathfloorfrac p_floordivfrac p_intfrac p_num p_floor2 p_ratio_frac p
        330s bash   cd /tmp/rprobes && cat > p_boundary.py <<'EOF' from decimal import Decimal from fractions import Fraction prin
        243s bash   cd /tmp/rprobes && cat > p_floor2.py <<'EOF' from fractions import Fraction print((Fraction(2) ** 100).__floor
        123s bash   cd /tmp/rprobes && for n in p_dec_mathfloor p_decint p_divmodfrac p_roundfrac2; do :; done cat > p_dec_mathflo
         99s bash   cd /tmp/rprobes && cat > p_leak2.py <<'EOF' import sys from decimal import Decimal try:     Decimal(1) / Decim


--- ORIGINAL TASK ---
**Decimal must work in the default int64 mode.** Since #284 ints are int64 by default and overflow stops. The Decimal prelude computes with 10 ** prec (prec 28), so `Decimal(1) / Decimal(3)` stops with "OverflowError: integer overflow in **" unless --exact-int is given. Decimal is a library; the user never asked for big ints, so this is wrong.

Fix: the Decimal (and Fraction, if it has the same problem) prelude code must use exact ints internally in every mode, while user code stays int64. Prefer the existing mixed / per-function exact-int machinery (intmode.py, bigcap.py) over a global switch. User-visible ints that come out of Decimal (int(d), d.as_tuple()) follow the user mode: they stop loudly if they exceed int64 in the default mode.

Acceptance:
- In the default mode these print the same as CPython: `Decimal(1)/Decimal(3)`, `Decimal("2").sqrt()`, `Decimal("10.50")*Decimal("3")`, `Decimal(2) ** 100`, `getcontext().prec = 50` then a division, `Decimal("1e30") + 1`.
- The tests marked exact only because of Decimal (test_ail_stdtop1) pass again without AIL_EXACT_INT=1.
- No change in run icount on lab/compare tasks that do not use Decimal: the generated C must be byte-identical for those tasks.
- Run the touched test modules plus test_ail_int64_default and test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
