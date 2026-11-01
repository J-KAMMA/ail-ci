**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review

**Change:** adds a per-scope receiver classifier (`collect_template_scopes`/`scope_of`/`kind_of_name`/`kind_of_value`, `receiver_kind`) so the `string.Template` method lowering is skipped only when a receiver is *known non-Template*; allows attribute assignment targets; adds 6 tests. It does not restrict lowering to receivers *known to be Templates*.

**Probes (HEAD, both builds; base = `work` = 0846cca):**
- `p_review_p8` (exact review probe): HEAD now named refusal (`the method .is_valid() (on a instance:Box)` / class has no `__init__`), base crashed. Acceptable per "or refuse when not".
- pass/match: `p_param_ok`, `p_known_other`, `p_no_feature` (generated C byte-identical to base), plus worker probes `pA_arg_call`, `pI_call_param`, `pK_call_unknown`, `pM_call_unknown`, `pN_false_other`, `pG_direct`.
- refused by name: `pE2_value_arg`, `pF_value_call`, `pH_value_ok`, `pJ_dict_value`; `p_class_lambda`, `p_setattr_init`.
- **crash on HEAD, named refusal on base**: `p_self_attr`, `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop`.

**Defect**
1. `_Surface.call` (`ail_syntax.py:2657-2662`) lowers when `receiver_kind(...) != 'other'`, so a receiver of *unknown* kind still goes to `template_method`. `p_self_attr.py`:
   ```python
   import string
   class Box:
       def __init__(self):
           self.substitute = lambda v: "SUB" + str(v)
       def run(self):
           return self.substitute(5)
   def main():
       t = string.Template("$x")
       print(t.substitute(x=1))
       print(Box().run())
   main()
   ```
   Expected (CPython, exit 0): `1` / `SUB5`. Actual (HEAD g and d, exit 1): `1` then `AttributeError: 'Box' object has no attribute 'template'`. Base refuses the same program by name (`string.Template.substitute used as a value`) on both builds, so this is a refusal→crash regression. Same root cause in the other five probes (receiver is `self`, a subscript, a call result, an attribute chain, a loop variable, or a tuple-unpack target). The review asked for lowering only on receivers actually known to be Templates (or refusing otherwise); that is still not implemented.

**Claims**
- Scope/parameter resolution: verified (`p_param_ok`, `pA_arg_call`, `pI_call_param`; code as described).
- Value gate refuses unknown receivers on reads, assignment targets allowed: verified.
- `pE2/pF/pH/pJ` refused by name; `pA/pI/pK/pM/pG` match: verified.
- `p3_collision2`, `p7_dataclass_flag`, `p9b_class_method`, `p_template_ok`: files not present, **unverified** (`p_class_lambda`/`p_setattr_init` equivalents refuse by name).
- `lab/compare` 10/10 C identical: 5/10 compile and are byte-identical; 5 fail on both trees here (e.g. `chain_relax` needs `--exact-int`), so **unverified**.
- Tests: re-ran `test_ail_std_string` + `test_ail_safetynet`, 0 failed (242 s, `-j 2`); `update_manifest.py --check` rc 0. `test_ail_files`, `test_ail_corpus_findings3` not re-run (not edited).

**Pre-existing:** none newly observed; `p_class_lambda`/`p_setattr_init` base crashes are now named refusals (improvement).

**Unverified:** speed (no runtime hot path; compile-time AST walk only); the 5 lab/compare tasks needing extra flags.

VERDICT: FIX
1. `_Surface.call` still hijacks `.substitute/.safe_substitute/.is_valid/.get_identifiers` calls on receivers whose kind is unknown (`self`, `d[k]`, `f()`, `h.b`, loop/tuple-unpack targets). Probe `/tmp/rprobes_r/p_self_attr.py`: expected CPython `1\nSUB5` (exit 0); actual HEAD both builds `1` then `AttributeError: 'Box' object has no attribute 'template'` (exit 1), while base refuses it by name. Restrict lowering to receivers known to be `string.Template` (or refuse/leave unknown receivers alone), as the review requested; `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop` show the same defect.
[cost $0.0212, opencode tokens {"total": 873442, "input": 41556, "output": 5506, "reasoning": 15372, "cache.write": 0, "cache.read": 811008}]
    tool time: bash 17.2 min
        395s bash   cd /tmp && rm -rf lc && mkdir lc && cd lc && n=0; same=0; for f in /home/runner/work/ail-ci/ail-ci/lab/compare
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        183s bash   cd /tmp/rprobes_r && for p in p_review_p8 p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_f
        120s bash   cd /tmp/rprobes && for p in pA_arg_call pI_call_param pK_call_unknown pM_call_unknown pN_false_other p3_collis
         48s bash   cd /tmp/rprobes_r && for p in p_class_lambda p_setattr_init; do for wt in /home/runner/work/ail-ci/ail-ci /tmp
         21s bash   cd /tmp/rprobes_r && for p in p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_for_loop p_re
         18s bash   cd /tmp/rprobes_r && rm -rf dbg_head dbg_base exe_head exe_base && AIL_NO_CACHE=1 python3 /home/runner/work/ai
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 tools/update_manifest.py --check; echo "rc=$?"; date


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
