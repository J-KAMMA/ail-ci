**Fix one pre-existing difference from CPython.** A reviewer of job `pre10` recorded these as already present before that job:

- `round(2.5, -10**6)` → `nan` on both base and HEAD.
- `__round__(self, n=-1)` / `n=1+2`: both HEAD and base pass `None` instead of the default.
- `round(C(), 2)` for a one-parameter `__round__`: both give "type instance doesn't define __round__ method".
- `__round__(self, *args/**kw)`: HEAD raises a bogus missing-argument TypeError; base passed wrong values. Neither matches.

`VERDICT: FIX`

1. Float-literal `__round__` default emits an invalid call `ail_box_float(1.5)` (missing `cx`), so the C compiler rejects the program. Probe `/tmp/rprobes/p_floatdef.py`:
```python
class F:
    def __round__(self, n=1.5):
        return repr(n)
print(round(F()))
print(round(F(), None))
print(round(F(), 2))
```
Expected (CPython): `1.5`, `1.5`, `1.5`. Actual HEAD, both builds: build failure `too few arguments to function 'ail_box_float'` in `pr0_...` (`ail_box_float(1.5)`). Base builds (outputs `None`, `0`, `2`).

2. String-literal `__round__` default emits `ail_box_str(ail_cstr("hi"))`, but `ail_cstr` is not defined in the general-path runtime (it uses `ail_str_from_cstr(cx, ...)`), so the C compiler rejects the program. Probe `/tmp/rprobes/p_strdef.py`:
```python
class S:
    def __round__(self, n="hi"):
        return repr(n)
print(round(S()))
print(round(S(), None))
```
Expected (CPython): `'hi'`, `'hi'`. Actual HEAD, both builds: build failure at `ail_box_str(ail_cstr("hi"))` (`ail_cstr` implicit/int). Base builds (outputs `None`, `0`).

3. The wrapper is emitted even when `round()` is never called, so a program that only defines such a class regresses from working to unbuildable. Probe `/tmp/rprobes/p_nodefuse.py` defines `F` (`n=1.5`) and `S` (`n="hi"`) and prints `"ok"`. Expected/CPython and base: `ok`. Actual HEAD, both builds: C compile failure. Fix `_round_default_c` to emit general-path constructors (`ail_box_float(cx, ...)`, `ail_box_str(ail_str_from_cstr(cx, ...))`), or fall back to the old d2 path when the default cannot be emitted safely.

4. `round(2.5, NoIndex())` (class without `__index__`) now reports `TypeError: 'instance' object cannot be interpreted as an integer`; CPython says `TypeError: 'NoIndex' object cannot be interpreted as an integer` (probe `/tmp/rprobes/p_bad.py`). Use the instance's class name, not `ail_type_name(AIL_T_INST)`.
[cost $0.0000, opencode tokens {"total": 3706907, "input": 74720, "output": 32612, "reasoning": 2903, "cache.write": 0, "cache.read": 3596672}]

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre136.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
