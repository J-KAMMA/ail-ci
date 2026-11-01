**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: `work..HEAD` (7135ab8 + 533249a)

**What the change really does:** adds typed-path static folding for `issubclass(C, ...)` and for `isinstance(x, (Class, builtin/object))`, with `object` treated as an unconditional match, plus `issubclass` in `boolkind.BOOL_BUILTINS`; adds tests/docs. It does not just fix the review defect described in the report.

**Verified**
- 6 required modules pass on HEAD (`test_ail_class_reach`, `test_ail_typed_inherit`, `test_ail_virtual_dispatch`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`): 0 failed.
- `update_manifest.py --check` exits 0.
- 20 lab/compare builds (`src/*/main.ail`, `src/*/main.py`): generated `program.c` hash and exit status identical HEAD vs `/tmp/base`. Report's "17 builds byte-identical" claim is consistent.
- `h05`, `h27`: typed build succeeds (`AIL_NO_GENERAL=1`) and matches CPython; forced general refuses `issubclass` by name.
- Their `object` fix works for a subclass target before `object`, i.e. `(B, object)` with `x: A | None`.

**Defects introduced**

1. `object` is not unconditionally true when a matching class precedes it (`pyfunc.py:16792` breaks out of the loop before seeing later targets). `/tmp/rprobes/objancestor.py`:
```python
class A:
    def __init__(self) -> None: self.x = 1
class B(A): pass
def f(x: A | None) -> None: print(isinstance(x, (A, object)))
def g(x: B | None) -> None: print(isinstance(x, (B, object)))
def main() -> None:
    f(None); f(A()); g(None); g(B())
main()
```
CPython: `True True True True`; HEAD default build: `False True False True`. Base: named refusal. The added regression test only covers `(B, object)` with `A | None`, where `B` is a subclass and does not hit the early break.

2. Static `issubclass` ignores a local/parameter that shadows a class or builtin type name (`_static_issubclass`, `pyfunc.py:16641`). `/tmp/rprobes/objshadow_cls.py`:
```python
class A:
    def __init__(self) -> None: self.x = 1
class B(A): pass
def f(A: int) -> None: print(issubclass(B, A))
def main() -> None: f(1)
main()
```
CPython: `TypeError: issubclass() arg 2 must be a class...`, exit 1, no stdout; HEAD default: prints `True`, exit 0. Same for a local (`A = 7`) and for the left operand (`def f(A: int): print(issubclass(A, object))` -> HEAD prints `True`, CPython raises `TypeError: ... arg 1 ...`). Base refuses these by name, so this is caused by the new folding.

**Report claims**
- "object target unconditionally true": false as stated; order-dependent (defect 1).
- New regression test present and passing: verified, but it misses the ancestor/self cases.
- Probes all same stdout: unverified for their exact programs; incomplete given defect 1.
- Generated C identical: verified on the 20 lab/compare sources.
- Tests/manifest/commit: verified.
- "16 typed / 10 general / 4 refused": unverified (not re-measured); h05/h27 typed behaviour verified.

**Unverified:** h17/h26 pre-existing differences, full 30-program counts, speed (runtime C unchanged for all sampled programs, so no hot-path change expected).

VERDICT: FIX
1. `/tmp/rprobes/objancestor.py`: expected `True True True True`, actual `False True False True` — an `object` target after a matching class is not unconditional.
2. `/tmp/rprobes/objshadow_cls.py`, `/tmp/rprobes/objshadow_local.py`, `/tmp/rprobes/objshadow_left.py`: expected CPython `TypeError`/exit 1, actual `True`/exit 0 — static `issubclass` folds shadowed names.
[cost $0.0388, opencode tokens {"total": 2412610, "input": 83353, "output": 9534, "reasoning": 22763, "cache.write": 0, "cache.read": 2296960}]
    tool time: bash 10.9 min, write 0.0 min, edit 0.0 min
        339s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
        289s bash   cd /home/runner/work/ail-ci/ail-ci && date && rm -rf /tmp/ccmp && mkdir -p /tmp/ccmp && for f in lab/compare/s
          3s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in objtuple objattr objuser objshadow; do echo "===== $p H
          2s bash   cd /tmp/rprobes && python3 - <<'PY' p='objfix.py'; s=open(p).read() s=s.replace("    dct: dict[str, A] = {'k':
          2s bash   cd /tmp/rprobes && python3 - <<'PY' p='objfix.py'; s=open(p).read() s=s.replace("    print(isinstance(x, (int,
          2s bash   for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "===== objfix $wt ====="; timeout 240 bash ~/tool
          2s bash   cd /tmp/rprobes && python3 - <<'PY' p='objfix.py'; s=open(p).read(); s=s.replace("    f(D())\n",""); open(p,'w
          2s bash   for p in objshadow_cls objshadow_local; do echo "===== $p BASE ====="; timeout 180 bash ~/tools/cmp.sh /tmp/rp


--- ORIGINAL TASK ---
**Coverage: class hierarchies.** Measure first: write 30 small programs using single and multi-level inheritance, super().__init__ and super().method(), overridden methods called through a base-typed list, isinstance/issubclass across the hierarchy, class attributes shadowed in subclasses, abstract-style methods raising NotImplementedError. List which are refused, which go general, which are typed, in docs/design/CLASS_REACH.md. Fix the top refusal so it builds (typed where the types are known). Acceptance: compare stdout and exit code with CPython on your own boundary probes; the generated C of the 10 lab/compare tasks must stay byte-identical unless the task is about them; add tests (register new modules in tests.d), run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, commit.

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
