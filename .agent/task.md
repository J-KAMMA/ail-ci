**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds a typed local `list[tuple[...]]` (≤4 fields, with `str`) path plus `enumerate` over `ail_srows`; adds a `max`/`min(key=)` fold over class-instance lists (catchable empty `ValueError`); adds a NaN-key refusal in `ail_srows_sort_key`; plus tests/docs/manifests. No program was edited.

**Defect (blocking) — module-level class lists now miscompile on the typed path**

Probe `/tmp/rprobes/global_maxkey.py`:
```python
from dataclasses import dataclass
@dataclass
class It:
    x: float
gxs: list[It] = []
def main() -> None:
    gxs.append(It(1.0))
    gxs.append(It(2.0))
    print(max(gxs, key=lambda s: s.x).x)
main()
```
- CPython: `2.0`, exit 0.
- Base (`/tmp/base`) default build: `2.0`, exit 0.
- HEAD default build: **build fails**, `program.c:1000:30: error: 'v_gxs' undeclared` (no executable).
- HEAD general build (`AIL_UNIFIED_FORCE=1`): `2.0`.

Same failure for `/tmp/probes/k6b_mutate.py` and `/tmp/probes/k6d_globalmax.py` (both work on base). Cause: `_struct_key_fold` (pyfunc.py:17958) now makes a function typed for a module-level `olist`; the emitted fold reads `v_gxs` as a local in `py_main`, while an empty module list is declared in a later init function. Minimal fix: refuse the fold when the source is a module-level global (fall back to general as on base), or use the module-global accessor.

**Claim check**
- t366/g14 now typed; base general — verified.
- t347/t318 typed — verified.
- g12/g15/g16 still general with the stated first messages — verified.
- g21_002 first reason — **false**: actual first reason is `json.dumps of data: the type of this value is not known here`, not the `[None, True, False]` bool/number mix.
- Wide >4 str rows "refused by name" — verified for mixed 5-field annotations (message + general path), but **not universal**: an all-`str` 5-field annotation compiles typed as an `olist` of a synthesized tuple class, and a list-literal-initialized annotated srow list falls back general with `a list mixing tuples and plain numbers`. No truncation observed in any case.
- Empty max/min catchable `ValueError`, with text and silently, through argument/attribute/list-item/dict-value — verified.
- "Only `p22_empty_dict` and `p22_maxmin_direct` fall back general" — **false**: `p22_srows` also falls general (`for x in empty` flat walk).
- C stability of the 10 `lab/compare` tasks — verified byte-identical.
- `test_ail_prog22` + `test_ail_safetynet` pass; manifest `--check` OK. The other six modules the report lists were not rerun (not required).

**Pre-existing:** `key_edge` int64 overflow in the key expression is identical on base; a module-level forward-ref empty class list appended in typed code (`k6c_global`) already fails on base; NaN sort refusal differs from CPython on both builds (documented `C?-job-prog22-11021237-1`), typed path raises `ValueError` with empty text while the general path has a descriptive message.

**Unverified:** instruction counts — `perf_event_open` is denied here, so no icount before/after; the report's 8-module test claim beyond the two required modules.

VERDICT: FIX
1. `/tmp/rprobes/global_maxkey.py`: expected `2.0` (CPython and base default); actual HEAD default build fails with `'v_gxs' undeclared` because `_struct_key_fold` types a function that mutates a module-level empty class list. Same for `/tmp/probes/k6b_mutate.py` and `/tmp/probes/k6d_globalmax.py`; base builds and matches CPython.
[cost $0.0768, opencode tokens {"total": 7068146, "input": 68029, "output": 21830, "reasoning": 54511, "cache.write": 0, "cache.read": 6923776}]
    tool time: bash 13.2 min
        183s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pr
         84s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cstab && mkdir -p /tmp/cstab && fails=0; for t in lab/compare/src
         50s bash   cd /tmp/rprobes && for p in k6_mutate k6b_mutate k6d_globalmax k15_nanmethod k16_catch_empty field_srows ret_s
         38s bash   cd /tmp && for p in p22_five p22_six p22_maxkey p22_maxkey_empty p22_empty_dict p22_maxmin_direct p22_catch_si
         33s bash   cd /tmp/rprobes && for p in key_forms key_empty key_edge srow_edge srow_wide srow_alias nonfeature; do echo "=
         27s bash   cd /tmp/rprobes && for p in srow_nan_nokey srow_lit srow_append5 key_side srow_iter_mut srow_edge srow_4str sr
         25s bash   cd /tmp/rprobes && cat > srow_module.py <<'EOF' ROWS: list[tuple[str, int]] = []  def main() -> None:     ROWS
         25s bash   cd /tmp/rprobes && for p in key_forms key_empty key_edge key_default key_tuple srow_edge srow_wide srow_alias 


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/dev/t366.py`
- `lab/census/programs/gdev/g12_018.py`
- `lab/census/programs/gdev/g21_002.py`
- `lab/census/programs/gdev/g15_006.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t347.py`
- `lab/census/programs/gdev/g16_034.py`
- `lab/census/programs/gdev/g14_034.py`
- `lab/census/programs/dev/t318.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog22.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog22.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
