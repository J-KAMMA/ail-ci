**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**Change:** adds a `string.Template` prelude lowering (substitute / safe_substitute / is_valid / get_identifiers, `$$`/`$name`/`${name}`, named refusals for class- and method-as-value, CPython's bytes TypeError), widens `capwords()` to `s=`/`sep=` keywords, and adds the 12 lab programs, `RESULTS.md`, `test_ail_std_string`, DEVLOG and manifest entries.

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`):
- pass: `p2_tpl_types`, `p2_tpl_invalid`, `p2_cap_kw`, `p2_cap_edge`, `p_tpl_basic`, `p_tpl_alias`, `p4_attr_only`, `p4_values_dollar`, `p5_ids`, `p5_dupkw`, `p6_empty`, `p6_unicode`, `p6_cap_bytes`, `p7_ctx`.
- refused by name: method values (`p3_method_value_attr`, `p6_getattr_value`), class value (`p3_class_value`), subclass (`p3_subclass`), `isinstance(t, string.Template)` (`p4_type`), `t.substitute(**m)` (`p4_star`).
- **crash**: `p8_setattr`, `p9_lambda_method` (below).

**Defect**
1. `_Surface.call` (ail_syntax.py:2493-2496) lowers **every** `.substitute/.safe_substitute/.is_valid/.get_identifiers` call once any `string.Template` appears anywhere, without checking the receiver. An unrelated receiver is miscompiled into the Template helper and crashes.
   `p8_setattr.py`:
   ```python
   import string
   class Box: pass
   def check(): return "BOX"
   def main():
       t = string.Template("$x")
       print(t.substitute(x=1))
       b = Box(); setattr(b, "is_valid", check)
       print(b.is_valid())
   main()
   ```
   Expected (CPython, exit 0): `1` then `BOX`.
   Actual (both builds, exit 1): `1` then `AttributeError: 'Box' object has no attribute 'template'`.
   The identical program without the Template (`p9_setattr_only.py`, printing only `BOX`) builds and matches on *both* base and HEAD, so the new gate is what turns it into a crash. `p9_lambda_method.py` (an unrelated class attribute `is_valid = lambda self: "BOX"`, elsewhere a named refusal on base) likewise compiles and crashes instead of refusing.
   Same root cause, smaller effect: `p7_dataclass_flag.py` (a dataclass field named `is_valid`) and `p3_collision.py` are wrongly refused as `string.Template.is_valid used as a value`; these are named refusals, so not blocking by themselves.

**Claims**
- Method-as-value refused by name / `getattr(t,"substitute")(...)` works: verified.
- bytes/bytearray exact `cannot use a string pattern on a bytes-like object`; other non-str messages unchanged: verified (`p2_tpl_types`).
- 11/12 lab programs match CPython on both builds: verified (`test_ail_std_string` passes).
- 10 `lab/compare` C byte-identical: verified (translate+to_c, all 10 same).
- `update_manifest.py --check`: verified.
- 5 test modules, 0 failed: `test_ail_std_string`, `test_ail_stdlib1`, `test_ail_safetynet` re-run, 0 failed (333 s); `test_ail_files` and `test_ail_corpus_findings3` not re-run.

**Pre-existing:** `getattr(obj, name)()` with a non-literal method name crashes identically on base (`p_getattr_class`), so the Template variants of that are not caused here. `capwords`/Template named refusals are acceptable.

**Unverified:** the two remaining required modules; the “6 built before the fix” count; speed (no hot runtime path touched).

VERDICT: FIX
1. Restrict the Template-method lowering to receivers actually known to be Templates (or refuse when not), so unrelated `.is_valid()` / `.substitute()` calls are not hijacked; currently `p8_setattr.py` prints `1\nBOX` (exit 0) on CPython but prints `1\n` then `AttributeError: 'Box' object has no attribute 'template'` (exit 1) on both AIL builds.
[cost $0.0458, opencode tokens {"total": 1840732, "input": 90984, "output": 10094, "reasoning": 34950, "cache.write": 0, "cache.read": 1704704}]
    tool time: bash 19.4 min
        334s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_string te
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && nohup python3 ../tools/par_check.py -j 2 test_ail_std_str
        102s bash   cd /home/runner/work/_temp/w2 && date && for p in p_cap_kw p_tpl_basic p_tpl_types p_tpl_alias p_tpl_invalid; 
        100s bash   cat > /tmp/rprobes/p6_empty.py <<'EOF' import string  def main():     for text in ("", " ", "$$", "$x", "no pl
         97s bash   cat > /tmp/rprobes/p5_typename.py <<'EOF' import string  def main():     t = string.Template("$x")     print(t
         95s bash   cd /home/runner/work/_temp/w2 && date && for p in p2_tpl_types p2_tpl_invalid p2_cap_kw p2_cap_edge; do echo "
         93s bash   cd /home/runner/work/_temp/w2 && date && for p in p4_type p4_attr_only p4_star p4_values_dollar p4_errors; do 
         41s bash   cat > /tmp/rprobes/p8_alias_method.py <<'EOF' import string  class Box:     def is_valid_impl(self):         r


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `string` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `string` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/string/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/string/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_string.py registered in tests.d), and compare them with CPython in the test.
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
