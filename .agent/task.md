**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — `work..HEAD` (`f5da488`, `8e626c0`, `11fbf00`)

**What the change really does.** It replaces the TypedDict `dict(...)`/shadowed-`dict` paths with one generated helper (`td_base`/`td_add`/`td_splash`/`td_done`) that records positional and keyword sources, checks mapping, duplicate keys, string keys and arity, and keeps the functional declaration's declared typename. It also refuses module-level rebinding of handled typing names/aliases. The helper now materialises `*args` as a list, which changes evaluation order.

**Review defects from last round**
- Module-level `cast` shadowing: **verified fixed** — `p_cast_module`, `p_cast_alias_module` match CPython via the general path.
- TypedDict `**` non-string keys: **verified fixed** — `p_td_kw_unshadow`, `p_td_kw_param`, `r1_td_kw_edge`, `p_errtext` all match CPython on both builds.

**Other claims**
- Functional declared name, duplicate/precedence order, `len` shadow, non-mapping (`list/int/str/iterable`) for `**`: **verified** (`p_rev2_functional_name`, `p_rev2_len_shadow`, `p_rev2_dict_shadow`, `p_rev2_dict_shadow_len`, `p_rev2_nonmap`, `p_errtext`, `r14`).
- `p_rev2_precedence.py` "matches": **false** — it differs on the pre-existing positional-update message (`element #0` vs `element`); same diff on base. Not blocking.
- `p_rev2_nonmap.py` "only keys()-only difference": **false** — `KeysGet` also differs; both custom-mapping cases are documented/pre-existing AIL `dict` limits.
- Tests: **verified** — `test_ail_std_typing test_ail_safetynet test_ail_files test_ail_corpus_findings3`, 4 modules, 0 failed (291s). `update_manifest.py --check` rc 0.
- Non-typing C: **verified** identical `program.c` to `/tmp/base` (only `native_report.json` temp paths differ).

**Defects**

1. Starred positional arguments are unpacked before earlier keyword arguments.
```python
from typing import TypedDict
class Movie(TypedDict):
    title: str
def boom():
    print("boom")
    raise ValueError("boom")
try:
    Movie(title=boom(), *5)
except Exception as exc:
    print(type(exc).__name__, exc)
```
Expected/CPython: `boom` then `ValueError boom`. Actual HEAD (both builds): `TypeError 'int' object is not iterable` (no `boom`). `_typed_dict_expr` puts `node.args` into a list before applying keywords, so `Movie(title=f(), *g())` evaluates `g` before `f`; base refused starred TypedDict calls by name.

2. Non-iterable `*` reports a different error.
`p_star_bad.py` (`Movie(*5)`, `Movie(*None)`): expected `TypeError __main__.Movie() argument after * must be an iterable, not int`; actual `TypeError 'int' object is not iterable`.

**Pre-existing (identical on `/tmp/base`):** positional-update message missing `#0` (`Movie([1])`, `Movie([1], **{...})`); `keys()`/`__getitem__` custom mappings still rejected (base also failed, documented in `DIFFERENCES.md`); rebinding through `global cast` inside a function still lowers to the value (`MY:5` vs `5`); TypedDict values/aliases (`M = Movie`) still fail to compile.

**Observation (not counted — named refusal):** module-level `dict = 5` (and `isinstance = 5`) with a TypedDict call now refuses to compile because the generated helper mentions `dict`; base compiled that program and matched CPython. The refusal is named, so per the rules I do not count it as a blocking defect.

**Speed:** not measured; the change only affects programs that import `typing` and construct a TypedDict.

VERDICT: FIX

1. `p_order_error.py` — expected `boom` / `ValueError boom`; actual `TypeError 'int' object is not iterable`, because `*args` is evaluated before a preceding keyword argument.
2. `p_star_bad.py` — expected `TypeError __main__.Movie() argument after * must be an iterable, not int`; actual `TypeError 'int' object is not iterable`.
[cost $0.0000, opencode tokens {"total": 1886158, "input": 239497, "output": 8515, "reasoning": 38914, "cache.write": 0, "cache.read": 1599232}]
    tool time: bash 10.6 min
        292s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         57s bash   cd /tmp/rprobes && date && for p in r1_td_kw_edge r2_td_kw_mapping r3_td_alias r3a_td_alias r3b_td_container r
         56s bash   cd /tmp/rprobes && date && for p in p_dict_global p_len_global p_str_global p_isinstance_global p_mapping_cust
         51s bash   cd /tmp/probes && date && for p in p_rev2_precedence p_rev2_functional_name p_rev2_len_shadow p_rev2_eval_orde
         46s bash   cd /tmp/probes && date && for p in p_td_kw_unshadow p_td_kw_param p_td_kw_places p_td_kw_mixed p_td_kw_dup p_t
         24s bash   cd /tmp/rprobes && cat > p_errtext.py <<'EOF' from typing import TypedDict class Movie(TypedDict):     title: 
         16s bash   cd /tmp/rprobes && date && for p in p_mapping_custom p_len_global p_str_global p_dict_global p_isinstance_glob
         14s bash   cd /tmp/rprobes && date && for p in r2_td_kw_mapping r3_td_alias r3a_td_alias r3b_td_container r6_td_reassign 


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `std_typing` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-std_typing-11020445`. Its change is `git diff 9eea12760b88062cf5830cc6d272b98e74e3789f FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

Apply the same change to this tree, resolving conflicts by keeping both sides' fixes. Then run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, run the test modules the change touches plus `test_ail_safetynet`, and commit. Change nothing else.

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
