**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** It relaxes the hybrid body gate (division/modulo, constant-step slices), seeds return annotations and a `str`-slice kind, and routes int/bool clone division traps through the existing int64-overflow `setjmp`; the general-build C is untouched.

**Probes (hybrid `build --cpython`, HEAD unless noted):**
- `p_div2.py` (int `%`,`//` literal; int/int `/` → float; float `%`,`//` literal): all accelerated, stdout/exit match.
- `p_div3.py` (variable/negative int divisors, INT64_MIN edges, bool/attr/list/dict routes): all accelerated, match.
- `p_zero_uncaught.py`, `p_boolzero.py`, `p_boolzero2.py` (uncaught `% 0`, `// False`, bool return): accelerated, stdout before trap preserved, exit 1 and traceback match.
- `p_slice.py`, `p_slice2.py` (empty/negative/far bounds, `[::-1]`, `[::-2]`, variable bounds, str/unicode, refused variable/zero steps): accelerated ones match.
- `p_neglit.py`, `p_mixed_bad.py` (float function with a **signed literal divisor**): fails (defect 1).
- `p_augdiv.py` / `p_augdiv_int.py` (aug-assignment): int path now fixed vs base; float path identical on base (pre-existing).
- C-identity: all 10 `lab/compare` tasks compiled HEAD vs `/tmp/base --debug-dir`; 7 `program.c` byte-identical, 3 refused identically on both.
- Tests: `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet` pass; `update_manifest.py --check` passes.

**Report claims:**
- int/bool zero-division → fallback and stdout flush: **verified**.
- float/str with possibly-zero divisor stays CPython: verified for BinOp; **false for `x /= y` aug-assign** (pre-existing hole, see below).
- "non-zero literal divisors remain eligible" incl. optional sign: **false** (defect 1).
- all ten `lab/compare` identical: **verified** (7 C-identical, 3 identical refusals).
- tests/manifest: first three modules and manifest verified; `test_ail_files` / `test_ail_corpus_findings3` not re-run (reviewer scope).

**Pre-existing (identical on `/tmp/base`, no block):** `def fdiv(x: float, y: float) -> float: x /= y; return x` with `fdiv(3.0, 0.0)` is accelerated and loses pre-trap stdout on **both** HEAD and base (`_unsafe_body` only scans `BinOp`, never `AugAssign`). Probe `p_augdiv.py`: CPython prints `start...`/`before-zero` then raises; both hybrids print nothing and stderr `division by zero`.

**Unverified:** instruction counts (`perf_event_open: Permission denied`), the worker's exact 13 probes, and `test_ail_files`/`test_ail_corpus_findings3`.

VERDICT: FIX
1. `AIL_CURRENT/ail_cpython_hybrid.py:80-88` `_provably_nonzero` rebinds `node = node.operand` and then evaluates `isinstance(node.op, ast.USub)`, raising `AttributeError: 'Constant' object has no attribute 'op'`. It is reached at line 111 exactly when the result is **not** int/bool and the divisor is a signed literal, and the exception aborts the whole hybrid analysis, so **every** function in the module loses acceleration (the program still runs correctly in CPython). Probe:
   ```python
   def add1(x: int) -> int: return x + 1
   def modp(x: int) -> int: return x % 7
   def head(s: str) -> str: return s[:2]
   def fdivneg(x: float) -> float: return x / -2.0
   print(add1(2), modp(20), head('hello'), fdivneg(7.0))
   ```
   Expected: `accelerated: ["add1","head","modp","fdivneg"]` (7.0/-2.0 cannot trap), stdout matches CPython.
   Actual: `accelerated: []`, build note `no extension: 'Constant' object has no attribute 'op'`; removing `fdivneg` restores `["add1","head","modp"]`. Same failure with `x % -2.0` / `x // -2.0`. Fix: keep the `UnaryOp` in a separate variable or test `step.op` before reassigning `node`.
[cost $0.0680, opencode tokens {"total": 5840351, "input": 142586, "output": 15167, "reasoning": 34214, "cache.write": 0, "cache.read": 5648384}]
    tool time: bash 15.6 min
        352s bash   cd /home/runner/work/ail-ci/ail-ci && date && for t in berth_sim echo_pack ledger_bin rail_transfer scar_life 
        262s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_
        206s bash   cd /home/runner/work/ail-ci/ail-ci && date && for t in chain_relax tree_fold ticket_audit; do for w in new bas
         14s bash   cd /tmp/rprobes && date && bash hcmp.sh p_slice.py /home/runner/work/ail-ci/ail-ci 2>&1 | head -100
         14s bash   cd /tmp/rprobes && cat > p_slice2.py <<'PY' def vstep(xs: list[int], k: int) -> int:     s = 0     for v in xs
         13s bash   cd /tmp/rprobes && date && for p in p_zero_uncaught p_zero_after p_zero_try p_bad_slice; do echo "=== $p"; bas
          9s bash   cd /tmp/rprobes && cat > p_mixed_ok.py <<'PY' def add1(x: int) -> int:     return x + 1  def modp(x: int) -> i
          7s bash   cd /tmp/rprobes && cat > p_augdiv.py <<'PY' def fdiv(x: float, y: float) -> float:     x /= y     return x  de


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/corpus/programs/deepseek-v4.1-flash-free/t237.py`
- `lab/census/programs/gdev/g00_010.py`
- `lab/census/programs/dev/t024.py`
- `lab/census/programs/gdev/g18_008.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t131.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t380.py`
- `lab/census/programs/dev/t434.py`
- `lab/census/programs/gdev/g15_020.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog4.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog4.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

Run `python3 tools/update_manifest.py`, then only the new test module, the test modules of the files you touched, and `test_ail_safetynet`. Then commit.

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
