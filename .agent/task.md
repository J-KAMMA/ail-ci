**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: job-rbdecexact2_rr1 (HEAD febe20f4, base work=ad118e55)

**What the change really does.** Re-applies the accepted `decexact2` work: Decimal/Fraction prelude functions enter `cx->exact_depth` so their arithmetic promotes to big ints inside the library, `ail_exact_visible` guards each prelude return, `_exact_library()` keeps the big-int runtime for library users, overflow arms stop when depth ≤ 0, and getter-only property stores raise CPython's `AttributeError` (with `_class_defines_plain_attr` shadowing both read and store). This matches the report — no misrepresentation.

**Faithfulness.** All `+` source lines of the accepted patch (`e466453..job-decexact2-11020914`) are present in the re-apply: bigint_obj 49/49, cruntime 3/3, dunderrt 9/9, prelude_fraction 92/92, pyboxed2 104/104, tests 10/149/20 — zero dropped hunks; only ids/hashes/DEVLOG differ. dunderrt keeps `ordering`/`reversed_` beside `_int_ret`; pyboxed2 keeps array dispatch beside the exact-depth set.

**Probes** (`cmp.sh`, g+d, 22 files in /tmp/rprobes):
- Match CPython both builds: `r1_basic, r2_frac, r3_roprop, r7_nouse, r8_shadow, r9_fracdiv0, r10_frac_setter_shadow, r16a, r16b, r20_edges, r21_empty, r8_astuple`.
- Declared int64 stop (exit 1, `OverflowError: integer overflow in int()`, stdout prefix of CPython): `r4_intleak, r13_alias, r16c, r16d` (the `as_integer_ratio`/tuple escapes). `r11_rt_overflow, r12_leak_exc, r14_frac_from_int, r18_fraction_import` stop in user code at the declared boundary — `r12` also shows no `exact_depth` leak after a caught `ZeroDivisionError` inside the library (stdout keeps the two lines CPython prints first).
- Refused by name both builds: `r9_logb` (`decimal.Decimal.logb is not supported`).
- **C unchanged for non-users:** `r7_nouse` (no Decimal/Fraction) and gdev `g16_002.py` → `program.c` and `program_mix0.c` byte-identical to /tmp/base2 modulo the source path; `exact_depth` appears nowhere.

**Tests on HEAD** (`par_check -j 2`): `test_ail_stdtop1` ok 293s, `test_ail_hostile_input` ok 239s, `test_ail_safetynet` ok 140s; `test_ail_int64_default` 11/13 — the two failures are exactly `math.lcm()` op-18 and `int()` text ending in `\n  raised near …`, and both reproduce **identically on /tmp/base2** (character-for-character messages), so pre-existing (relrterr3 suffix).

**Pre-existing** (identical on base): `r15_prop_inherit` / `r22_setter_method` — a subclass that shadows an inherited property with a plain *method* still reads the property (`b.x` → 1 instead of 5/CPython's instance value); the change's method-agnostic read path doesn't cover it, and base behaves the same.

**Claims:** defect fix verified (row text + `as_tuple` probe + `logb` refusal; `test_ail_stdtop1.py:530` has the `logb` entry); `update_manifest.py --check` exit 0 verified; `tools/diff_ids.py` indeed absent; `.agent/pipeline.md` untracked verified; the "18 probes" list and the `test_ail_files`/`test_ail_corpus_findings3` results I did not re-run.

**Unverified:** worker's 18-probe table verbatim, `test_ail_files`, `test_ail_corpus_findings3`, explicit icount numbers (unnecessary: generated C is identical for non-users, so instruction counts cannot change).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=38 out_tokens=27174]

## full suite
test_ail_int64_default

## suite fix skipped: only 86 minutes left


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `decexact2` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-decexact2-11020914`. Its change is `git diff e466453f11c1074b1e876e1908cb46b506200ed9 FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

> Re-run of rbdecexact2, whose GitHub run was lost (no verdict 57.5 h after dispatch). If its branch job-rbdecexact2-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

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
