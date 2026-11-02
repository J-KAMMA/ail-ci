**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of prog29

**What the change does:** accepts module-level `frozenset(<str literal>)` (also list/tuple of str) as an ordered deduped `list[str]` readable only via `in`/`not in`/`len`, keeps it at module scope, adds refusals for shadowed `len` and reads before assignment, and lowers `len({...})` to an eager list comprehension plus a private int/str set. That matches the report.

**Verified**
- `g17_026` builds under `--strict` and matches CPython. The other seven report the same first blockers as claimed (`range`, `str(<list>)`, `yield`, instance `__hash__`); `t161`, `g08_004`, `t188` build strict.
- All ten `lab/compare/src/*/main.ail` `program.c` files are byte-identical base vs HEAD (only temp paths in `native_report.json` differ).
- `test_ail_prog29 test_ail_fz208 test_ail_cpython_hybrid test_ail_modconst test_ail_safetynet`: 5 modules, 0 failed. `tools/update_manifest.py --check` clean.
- Own probes (strict typed) matched CPython for setcomp over str/int/list/set/bytes/slice/tuple/bool, empty/duplicates/negatives, and frozenset membership/`len` through arguments, list items, attributes, unicode and duplicates.
- Same-scope parameter/local `len` shadows are refused; nested-def and module-literal shadows are refused; read-before-assignment refusals work for call/class/list.
- No programs/benchmarks edited. DEVLOG/test registration present.

**False / inaccurate claims**
- `prog29_z_shadowlen_param.py` and `..._local.py` were *not* refused; they build typed and match CPython. Correct, since the `len` call is in another function. Report table says refused.
- `prog29_r_order_arg.py` is refused because annotated `frozenset` parameters are unsupported, not by the read-before-assignment check.

**Pre-existing**
- A module-level non-literal binding of `len` (`for len in ...`, `if: len = 5`, `with ... as len`) is mishandled by both base and HEAD non-strict builds: `len(V)` prints `5` where CPython raises `TypeError`. Base differs identically, so this is pre-existing; HEAD additionally accepts it under `--strict` where base refused.

**Defect (caused by this change)**
1. Mutation of the set-comprehension source during iteration. `p_sc_mutate_attr.py`:
```python
class Box:
    def __init__(self) -> None:
        self.xs: list[int] = [1, 2]
    def side(self) -> bool:
        if len(self.xs) < 3:
            self.xs.append(99)
        return True

def f(box: Box) -> int:
    return len({x for x in box.xs if box.side()})

def main() -> None:
    box = Box()
    print(f(box), len(box.xs))

main()
```
CPython and base default build: `3 3`; HEAD default/strict build: `2 3` (both exit 0). CPython's list iterator sees the appended `99`; the new lowering iterates the pre-sized list comprehension bound. `bash ~/tools/cmp.sh p_sc_mutate_attr.py $PWD` shows base `g same / d same`, HEAD `g same / d DIFF`.

**Unverified:** frozenset-iteration general-path order vs base (not compared); instruction counts (`perf_event_open` denied).

VERDICT: FIX
[cost $0.0893, opencode tokens {"total": 6309540, "input": 160608, "output": 19983, "reasoning": 58421, "cache.write": 0, "cache.read": 6070528}]
    tool time: bash 10.3 min
        232s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_prog29 t
         81s bash   cd /tmp && rm -rf cmpbase cmphe && mkdir -p cmpbase cmphe; cd /home/runner/work/_temp/w2; ok=0; bad=0; for t i
         50s bash   cd /tmp/rprobes && cat > p_sc_tuple.py <<'EOF' def f(xs: list[int]) -> int:     return len({(x, x % 2) for x i
         47s bash   cd /tmp/rprobes && cat > p_sc_dict.py <<'EOF' def f(d: dict[str, int]) -> int:     return len({k for k in d}) 
         37s bash   cd /tmp/rprobes && cat > p_sc_byteslit.py <<'EOF' def f() -> int:     return len({b"a" for _ in [1, 2]})  def 
         25s bash   cd /tmp/rprobes && for p in p_ann_list p_ann_set p_ann_dict p_fset_sources p_fset_edges p_fset_types p_setcomp
         24s bash   cd /tmp/rprobes && cat > p_sc_tuple2.py <<'EOF' def f(xs: list[int]) -> int:     return len({(x, x % 2) for x 
         11s bash   cd /tmp/rprobes && cat > p_sc_len_modconst.py <<'EOF' def f() -> int:     return len({x for x in [1, 1, 2]}) l


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/gdev/g17_010.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t161.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t475.py`
- `lab/census/programs/gdev/g16_006.py`
- `lab/census/programs/gdev/g08_004.py`
- `lab/census/programs/gdev/g17_026.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t188.py`
- `lab/census/programs/gdev/g14_020.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog29.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog29.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
