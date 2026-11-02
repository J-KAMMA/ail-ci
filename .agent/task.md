**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: prog6 typed reach (work..1a1033d)

**What the change really does.** It broadens pymix kind inference (annotations, list repetition, unpacking, `return []`, no fall-through), makes the hybrid accept indexing/division/modulo/tracked `raise` and `range`/`int` calls, and adds a length-then-fill ABI for `list[int]`/`list[float]` results, with a `-1` overflow fallback and a stdout drain before `_Exit(1)`. It also refuses list results that return a list parameter/alias.

**Probes run** (`/tmp/rprobes`, hybrid via `ail build --cpython`, standalone via `~/tools/cmp.sh`):
- range step via arg/list item/attr/dict, zero literal, `True`/`False`, negative, uncaught: match CPython (boxed caller not bypassed; uncaught exits 1, stderr difference declared).
- list identity: param, alias, local, empty, negative, global, tuple-alias, mutation-through-alias: match; param/alias returns stay boxed, owned local lists type.
- traps: IndexError/ZeroDivisionError/ValueError/RuntimeError caught by a boxed caller: match; uncaught after `print` matches stdout+exit.
- int(str/float) boundaries incl. huge, `inf`, `nan`, 2^63±1: match (fallback).
- int64 edges (`//`, `%`, `+`, `*`, `-x` at INT64_MIN): match.
- list[float]/list[int] results incl. overflow and empty: match (single function).
- general build on `lab/compare`: 6 that build are byte-identical to `/tmp/base`; the 4 failures are identical on base.

**Defects**

1. **Hybrid true division of large int64 values is wrong.** `_unsafe_body` now allows `ast.Div`, but the typed path computes `(double)a / (double)b` instead of CPython's correctly-rounded int division.
```python
def true(a: int, b: int) -> float:
    return a / b
print(true(4865782901354085936, -7048155917072976836))
print(true(-931725450029404348, -7491968275375482579))
```
Expected (CPython): `-0.6903625513685845`, `0.1243632401770559`.
Actual hybrid (accelerated `true`): `-0.6903625513685846`, `0.12436324017705588`.
Base hybrid does not accelerate `true` and matches. (The general path already differed on base; the hybrid regression is new.)

2. **Two or more accelerated list-returning functions break the hybrid extension link.** Each list-return unit defines `ail_ret_spill_take`, so separate unit objects collide.
```python
def a(n: int) -> list[int]:
    return [0] * n
def b(n: int) -> list[int]:
    return [1] * n
print(a(2), b(3))
```
Expected: `accelerated: ["a","b"]`, stdout `[0, 0] [1, 1, 1]`.
Actual: `accelerated: []`; `build.json` note: `multiple definition of 'ail_ret_spill_take'` between `_ail_p_fast_unit1.o` and `_ail_p_fast_unit0.o`; stdout matches only because the extension was dropped and the whole program ran in CPython. A single list-return unit plus scalar units links fine.

**Claims check**
- Range ValueError tracked / boxed `except ValueError` not bypassed: **verified**.
- List param/alias return refused, owned local list still types: **verified**.
- 8 test modules, 0 failed: **verified** (same set, `-j 2`, 530 s).
- `update_manifest.py --check` clean: **verified**.
- "Generated C byte-identical for all 8 target programs": **false** under direct `pyboxed2.build` — g19_038, t402 and g09_014 differ (intended typed clones; the required 10 `lab/compare` tasks are identical).
- "Parameter annotations are not seeded": **inaccurate** — pymix no longer seeds them, but the hybrid's `sitecustomize` still does; no wrong output observed from it.

**Pre-existing:** general-path true-division precision difference; standalone int64 overflow loud stops; typed stderr text instead of tracebacks.

**Unverified:** instruction-count before/after (no `icount` run).

VERDICT: FIX
1. Refuse (or exactly emulate) true `/` on int operands in the hybrid: probe `true(4865782901354085936, -7048155917072976836)` gives `-0.6903625513685846` vs CPython `-0.6903625513685845`.
2. Make `ail_ret_spill_take` link-safe across captured list-return units (or compile units together): two list-return functions yield `accelerated: []` with `multiple definition of 'ail_ret_spill_take'` instead of both being accelerated.
[cost $0.0601, opencode tokens {"total": 5655263, "input": 65921, "output": 13885, "reasoning": 42145, "cache.write": 0, "cache.read": 5533312}]
    tool time: bash 17.7 min
        531s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pro
        229s bash   cd /home/runner/work/ail-ci/ail-ci && files=$(ls lab/compare/src/*/main.py); echo "== HEAD"; python3 /tmp/genc
         68s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_range_step p_range_lit p_list_ident p_list_alias_mut p_traps 
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_range_lit p_list_ident p_list_alias_mut p_traps p_divmod p_id
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in caught_lookup caught_key caught_user_parent slice_step unpack_t
         25s bash   cat > /tmp/genc.py <<'PY' import sys, os, json, hashlib root=sys.argv[1]; files=sys.argv[2:] sys.path[:0]=[roo
         23s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbgtest && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py
         14s bash   cat > /tmp/rprobes/p_global_alias_mut.py <<'EOF' G = [1, 2]  def mut(n: int) -> int:     ys = G     ys[0] = 9 


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/gdev/g19_038.py`
- `lab/census/programs/gdev/g09_000.py`
- `lab/census/programs/gdev/g08_022.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t402.py`
- `lab/census/programs/gdev/g21_024.py`
- `lab/census/programs/gdev/g09_020.py`
- `lab/census/programs/gdev/g14_018.py`
- `lab/census/programs/gdev/g09_014.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog6.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog6.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
