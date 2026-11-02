**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Only the CPython-hybrid safety analysis changes (`AIL_CURRENT/ail_cpython_hybrid.py`): it now accepts `abs` of provable float/int, `int(<int/bool>)`, `str(<number>)`, and int unary `-` only for int/bool-returning clones. Tests/docs were added; code generation is untouched.

**Defect found (caused by this change)**

Probe `/tmp/rprobes/rv21_abs_bool.py`:
```python
def f(x: bool) -> int:
    return abs(x)

def main() -> None:
    print(f(True))
    print(f(False))

if __name__ == "__main__":
    main()
```
- CPython: `1\n0\n`
- HEAD hybrid (`build --cpython`): `True\nFalse\n` — `f` is reported accelerated.
- Base hybrid: `f` is refused (`a call can raise or have side effects`) and output is correct.

Same failure with `rv21_abs_bool_assign.py` (`y = abs(x); return y`). Cause: `_safe_call` accepts `abs` via `_provably_int(..., int_names, True)`, and `int_names` includes `bool` parameters (`ail_cpython_hybrid.py:296`); the accelerated clone returns the bool unchanged instead of `int`. The worker’s probes only call `abs` on an `int` parameter with a bool argument (`mag(True)`), which falls back at the wrapper, so the gap was missed.

**Pre-existing (not caused by the change):** general/default builds stop loudly on `abs(INT64_MIN)` with `OverflowError: integer overflow in unary - or abs()`; identical on base (`rv21_abs_min.py`).

**Claims checked**
- `ba63377` exists; `str(-x)`/`int(-x)` on an int in a str-returning clone are refused again: verified (`rv21_strneg_strret.py`).
- Float `str(-x)` remains accelerated and matches CPython: verified (`rv21_str_neg_float.py`).
- `str(int/float/bool)`, `int(bool)`, `abs(int)` boundaries: verified except the bool-operand `abs` case above.
- `g22_022.shift_and_add_multiply` accelerated; `t139.fmt` and `g21_038.encode_rounded_floats` not: verified.
- All eight programs’ hybrid stdout/exit match CPython on the inputs I ran: verified (no-input runs; the added test covers more inputs).
- `test_ail_prog21`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass (`-j 2`).
- `update_manifest.py --check`: clean.
- 10/10 `lab/compare` `program.c` byte-identical between HEAD and base via `--debug-dir`: verified.
- Speed: not measured (unverified); the change only enables more hybrid acceleration.

VERDICT: FIX
1. `abs(<bool parameter>)` is accepted as an int/bool-result call but produces `True`/`False` instead of CPython’s `1`/`0` when returned as an int. Probe: `/tmp/rprobes/rv21_abs_bool.py` (above); expected `1\n0\n`, actual `True\nFalse\n`. Also `/tmp/rprobes/rv21_abs_bool_assign.py`. Exclude bool parameters from the `abs` int proof (or convert the result to int) and add a regression test.
[cost $0.0282, opencode tokens {"total": 2234722, "input": 32714, "output": 9938, "reasoning": 17990, "cache.write": 0, "cache.read": 2174080}]
    tool time: bash 13.1 min
        239s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3
        181s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21 test_ail_cpython_hybrid 
         81s bash   find / -name 'pymix.py' 2>/dev/null | head; grep -n "sys.path" AIL_CURRENT/ail_chatgpt.py | head
         80s bash   cd /tmp && rm -rf cmpcs; mkdir cmpcs; fail=0; for d in /home/runner/work/ail-ci/ail-ci/lab/compare/src/*/; do 
         32s bash   cd /tmp/rprobes && python3 run_hy.py /home/runner/work/ail-ci/ail-ci /home/runner/work/ail-ci/ail-ci/lab/corpu
         24s bash   cd /home/runner/work/ail-ci/ail-ci && ls lab/census/programs/gdev/g22_014.py lab/census/programs/gdev/g22_022.
         22s bash   cat > /tmp/rprobes/run_hy.py <<'PY' import json, os, shutil, subprocess, sys, tempfile from pathlib import Pat
         19s bash   cd /tmp/rprobes cat > rv21_abs_int_boolann.py <<'PY' def f(x: int) -> bool:     return abs(x)  def main() -> N


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/gdev/g22_014.py`
- `lab/census/programs/gdev/g22_022.py`
- `lab/census/programs/dev/t078.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t419.py`
- `lab/census/programs/dev/t232.py`
- `lab/census/programs/gdev/g21_038.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t139.py`
- `lab/census/programs/gdev/g25_016.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog21.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog21.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
