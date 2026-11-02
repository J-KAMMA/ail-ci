**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed `work..HEAD` (`d32759d`, `793b961`) with `/tmp/base` at `work` (`ecad304`). Started 04:00, finished 04:15.

**What the diff really does.** It lets scalar Optionals appear on non-decorated methods with program-unique names, rewrites `recv.name(...)` calls with a per-call receiver skip, adds a builtin-method-name collision guard, and relaxes the struct-list comprehension check to accept `str` elements. This matches the report's description.

**Defects (caused by this change; base passes all four probes).**

1. **Wrong receiver skip when the method's first parameter is not `self`/`cls` and the receiver is not statically known.**
```python
class C:
    def __init__(this, n: int) -> None: this.n = n
    def take(this, k: int | None) -> int | None:
        if k is None: return None
        this.n -= k; return this.n
def run(o): print(o.take(2))
def main() -> None: run(C(9))
main()
```
Expected stdout `7` (CPython, base both builds); HEAD both builds fail: `not in the subset: take() called without a required argument k__v` / `parameter k__p ... is declared bool, but 2 is not a bool`. The fallback for an unknown receiver assumes the first parameter is `self`/`cls`, so skip is 0 and the Optional pair is shifted into `this`.

2. **A class name shadowed/rebound to a `dict` is still classified as a class, so `dict.get` is captured.**
```python
class Cache:
    def get(self, k: int | None) -> int | None:
        if k is None: return None
        return k + 50
def main() -> None:
    Cache = {1: 10, 2: 20}
    print(Cache.get(1)); print(Cache.get(9))
main()
```
Expected `10\nNone`; HEAD compiles then crashes at runtime on both builds: `TypeError: cannot unpack non-iterable int object`, exit 1. The same program with the rebind at module scope (`Cache = {1: 10, 2: 20}` after the class, call inside `main`) is expected `10\nNone`; HEAD fails to build (`get() called without a required argument k__v`). Base both print `10\nNone`. Root cause: `_name_tags` returns `class` for any name in `class_names` before consulting scope bindings, so both the collision guard and `call_skip` misclassify the receiver.

3. **A call to an Optional method in a class body is not rewritten while the method signature is.**
```python
class C:
    def __init__(self, n: int) -> None: self.n = n
    def take(self, k: int | None) -> int | None:
        if k is None: return None
        self.n -= k; return self.n
class D:
    x = C(6).take(2)
def main() -> None: print(D.x)
main()
```
Expected `4` (CPython, base both builds); HEAD both builds fail (`reading the class attribute D.x through the class: its value is not a constant...` / module constant error). `run()` only refuses module-level Optional method calls; class-body statements are neither lowered nor refused.

**Pre-existing (identical on base).** `p10_collide_collection.py` (list/dict `pop` with user `pop`), `p12_datetime_collide.py` (datetime method collision), `p19_class_arg.py` (class passed as an argument) all fail on both HEAD and base, so they do not block.

**Claims checked.**
- `g12_026.py`: verified typed on HEAD (no general-path note) vs general on base, output matches CPython.
- Generated C of the 10 `lab/compare` tasks: verified `different 0 of 10` against `ecad304`.
- `test_ail_prog13` + `test_ail_safetynet`: verified, 2/2 modules pass on HEAD.
- `update_manifest.py --check`: passes.
- Module-level Optional method call refusal: verified (`p8_module_call` falls back and matches).
- Parameter kinds/defaults/bytes/bool/str/float, annotated/global/constructed receivers, struct-list-of-str: verified on both builds.
- “No more argument shifting”: **false** (defect 1).
- “`dict.get`/`list.pop` now match CPython”: true only for plainly typed receivers; **false under class-name shadowing** (defect 2).
- Worker's 13 opt/4 struct probes: unverified (not in the tree); my independent probes found the gaps above.
- The other 7 test modules in the report, and speed/icount: unverified (not required for this review).

VERDICT: FIX
[cost $0.0408, opencode tokens {"total": 1317143, "input": 132653, "output": 8764, "reasoning": 20270, "cache.write": 0, "cache.read": 1155456}]
    tool time: bash 8.3 min
        234s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_
         65s bash   cat > /tmp/rprobes/p12_datetime_collide.py <<'PY' import datetime  class Event:     def __init__(self) -> None
         50s bash   cd /home/runner/work/_temp/w2 && echo 'p5 expected:'; python3 /tmp/rprobes/p5_this_method.py; echo 'p23 expect
         46s bash   cd /home/runner/work/_temp/w2 && date && ls /tmp/rprobes/p*.py | grep -E '/p([0-9]|1[01])_' | xargs -P2 -I{} b
         36s bash   cat > /tmp/rprobes/p22_local_shadow.py <<'PY' class Cache:     def get(self, k: int | None) -> int | None:    
         20s bash   cat > /tmp/rprobes/p19_class_arg.py <<'PY' class S:     def __init__(self, n: int) -> None:         self.n = n
         20s bash   cat > /tmp/rprobes/p26_nested_call.py <<'PY' class C:     def __init__(self, n: int) -> None:         self.n =
          9s bash   cd /home/runner/work/_temp/w2 && for f in p1_int_kw p6_default_none p5_this_method; do echo "##### $f"; bash ~


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/corpus/programs/deepseek-v4.1-flash-free/t140.py`
- `lab/census/programs/gdev/g19_036.py`
- `lab/census/programs/dev/t002.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t001.py`
- `lab/census/programs/gdev/g06_000.py`
- `lab/census/programs/gdev/g12_036.py`
- `lab/census/programs/gdev/g12_026.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t371.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog13.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog13.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
