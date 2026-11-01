**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Commit `84f2280` adjusts the `cmath` prelude/lowering: complex `**` routes non-finite exponents through `_ail_cm_pow`, zero bases raise CPython's power error, `cmath.log(z, base)` rejects a zero log-base, `complex()` follows `complex_new`, `cmath` arguments are type-checked, and keyword calls are lowered to runtime `TypeError`s. No compiler/runtime change outside this path.

**Probes** (in `/tmp/rprobes`, run with `cmp.sh`; g and d agree with each other throughout):
- `p_log2`, `p_ctor2`, `p_args2`, `p_parse2` — **same stdout** as CPython (base-vs-log, constructor forms/messages, malformed strings, argument types, keyword/isclose rules).
- `p_pow2`, `p_pow3` — **DIFF** (defect 1).
- `p_star2` — **DIFF** (defect 2).
- `p_types2` — DIFF only in type names (pre-existing resolver, below).
- `p_plain2` and `lab/compare` `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit` — `program.c` byte-identical to `/tmp/basework` (`work`).
- Worker's original probes `p_pow`, `p_special`, `p_complex2`, `p_forms`: same stdout (8 review defects fixed).

**Defects**
1. Non-finite exponents are still wrong for bases whose argument is non-zero. `_ail_cm_pow` lets `math.cos(inf)`/division raise `ValueError`/`ZeroDivisionError: float division by zero`; CPython maps this to `ZeroDivisionError: 0.0 to a negative or complex power`.
   ```python
   import cmath
   try: print(2j ** float("inf"))
   except Exception as e: print(type(e).__name__ + ": " + str(e))
   ```
   Expected `ZeroDivisionError: 0.0 to a negative or complex power`; actual `ValueError: math domain error`. Same for `2j ** -inf`, `(1+1j) ** inf`, `(-2+0j) ** inf`, `(2+0j) ** complex(0.0, inf)` (actual `ZeroDivisionError: float division by zero`), etc. The report's "inf/NaN exponents give `(nan+nanj)`" is false in general.
2. The new keyword-rejection lowering mishandles `**mapping`: `cmathlib.py:145` only excludes `ast.Starred` positional arguments, not keywords with `arg is None`.
   ```python
   import cmath
   print(cmath.isclose(1.0, 1.0, **{}))
   ```
   Expected `True`; actual `TypeError: 'None' is an invalid keyword argument for isclose()`. Likewise `cmath.sqrt(**{})`: expected `TypeError: cmath.sqrt() takes exactly one argument (0 given)`; actual `TypeError: cmath.sqrt() takes no keyword arguments`.

**Report claims.** 8 defects fixed: verified. `log` base / `complex()` / malformed strings / explicit keyword rejection: verified. `lab/compare` 5 C files identical: verified. `test_ail_std_cmath` + `test_ail_safetynet`: pass (760 s). Manifest `--check`: rc=0. "all cmath args use ... not `<type>`": false for user types (below). `test_ail_files` and `test_ail_corpus_findings3`: unverified (not rerun, per scope).

**Pre-existing.** `_ail_cm_tname` falls back to `"object"`, so `cmath.sqrt(Thing())` says `not object` where CPython says `not Thing` (and a function gives `not object` vs `not function`); the fallback predates this commit. The other `lab/compare` tasks fail to compile on base too.

**Unverified.** Earlier worker probes `pcm1`/`pforms`/`pflow`/`pnum`/`pspecial`/`pstrings`/`phash`/`phash2` (not rerun); speed (no hot code touched); full suite.

VERDICT: FIX
[cost $0.0374, opencode tokens {"total": 1728757, "input": 84863, "output": 11965, "reasoning": 21049, "cache.write": 0, "cache.read": 1610880}]
    tool time: bash 17.4 min
        325s bash   cmp /tmp/cmpdep/head/dd/program.c /tmp/cmpdep/base/dd/program.c && echo PLAIN_C_IDENTICAL; cd /home/runner/wor
        149s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('p_ctor2.py') t=p.read_text() t=t.replace(
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_std_cmath test_ail_s
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && setsid nohup bash -c 'python3 ../tools/par_check.py -j 2 test_ail
        103s bash   ls /tmp/probes 2>/dev/null | head -20; cd /tmp/probes 2>/dev/null && for p in p_pow p_special p_complex2 p_for
         66s bash   cat > /tmp/rprobes/p_types2.py <<'EOF' import cmath   class Thing:     pass   def fn(x):     return x + 1   de
         62s bash   cd /tmp/rprobes && for p in p_pow2 p_log2 p_ctor2 p_args2 p_parse2; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py
         51s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('p_pow2.py') t=p.read_text() t=t.replace('


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
