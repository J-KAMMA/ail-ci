**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: `job decexact2` (property store follow-up)

**What the change really does.** Commit `4d02142` rewrites every successful `return AIL_OK` in an exact prelude function to run `ail_exact_visible` before leaving the exact depth, and makes a store to a getter-only property raise `AttributeError` naming the run-time class instead of silently setting an instance attribute. Commit `0c187ff` adds `_class_defines_plain_attr` and uses it, for read and store, to let a subclass's plain class attribute shadow an inherited property. This broadly matches the report, but the shadow test excludes the property owner class itself.

**Probes (HEAD, both `g`/`d`; base `/tmp/base` where needed):**
- Early-return leaks fixed: `p1_roundfrac`, `p2_floordivfrac`, `p3_dec_mathfloor`, `p4_leaktyped`, `p5_hashfrac` all stop with `OverflowError: integer overflow in int()`, exit 1. Verified.
- Subclass plain attribute: `p14_subplain`, `p15_subplain2`, `p23_annshadow`, `p26_setter_plain_deep` match CPython; `p16_submsg` matches the run-time class name. Verified.
- `p27_frac_ro_via` (attribute, list item, dict value): matches. `p_prop_setter_inherit`, `p_deeper_prop` match.
- Non-feature program: `plain.py` `program.c` byte-identical base vs HEAD. Verified.
- **New defect found:** `/tmp/rprobes/p_sameclass_after.py`:

```python
class A:
    @property
    def x(self):
        return 1
    x = 0
a = A()
print(a.x)
a.x = 5
print(a.x)
```

  CPython: `0`, `5`, exit 0. HEAD (both builds): `1`, then `AttributeError: property 'x' of 'A' object has no setter`, exit 1. Base: `1`, `1`, exit 0. So the exit-1 is caused by this change. Same for the subclass form `/tmp/rprobes/p_attr_after_prop2.py` (CPython `4`,`8`; HEAD `3`, then the same AttributeError; base `3`,`3`, exit 0).

**Pre-existing (same on base and HEAD, does not block):**
- Reading an inherited property when a subclass defines a plain *method* of the same name still returns the property value (e.g. `p_submethod_read`: `B 1` vs CPython's bound method).
- Reading a class-body attribute assigned after a `@property` of the same name returns the getter (`...+after`: `1`/`3` vs CPython `0`/`4`). Only the read is pre-existing; the new store error above is not.
- `hash(Fraction(1,3))` differs (`p6_legit`).
- `del f.numerator` is refused at compile time (`not in the subset: del on a Attribute`).

**Claims:** early-return leaks — verified; `Fraction.numerator` assignment — verified by `test_read_only_property_assignment_stops`; subclass plain-attribute shadowing — verified for `p14`/`p15`; run-time type in inherited errors — verified; `p18`/`p19`/`p20` — unverified (files absent); `p_accept`/`p_frac_small`/`p_exact_ret` — unverified directly (acceptance tests pass); "5 modules, 552 s" — I reran only the changed module plus safetynet; `update_manifest.py --check` — verified clean.

**Tests:** `test_ail_int64_default` + `test_ail_safetynet` on HEAD: 2 modules, 407 s, 0 failed. Other three modules were not rerun.

**Unverified:** snapshot/`icount` (non-Decimal C is byte-identical, so no change expected); `p18`–`p20`; the other three test modules.

VERDICT: FIX
1. A class that assigns a plain class attribute after a getter-only `@property` of the same name no longer stores to the instance: HEAD raises `AttributeError: property 'x' of 'A' object has no setter` (exit 1), while CPython stores and prints (`p_sameclass_after.py`: expected `0\n5\n`, actual HEAD `1\nAttributeError...`; base exits 0). The store blockers only consider more-derived classes (`d != c`), so the owner's own later plain binding is ignored; include the owner when `_class_defines_plain_attr(c, attr)` is true (same for the read path, which already reads the property instead of the class attribute on base too).
[cost $0.0217, opencode tokens {"total": 947361, "input": 46332, "output": 4993, "reasoning": 15268, "cache.write": 0, "cache.read": 880768}]
    tool time: bash 11.5 min
        408s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_int64_defaul
        156s bash   cd /tmp/rprobes && for p in p1_roundfrac p2_floordivfrac p3_dec_mathfloor p4_leaktyped p5_hashfrac p6_legit; d
         68s bash   cd /tmp/rprobes && cat p6_legit.py; echo ===; timeout 600 bash ~/tools/cmp.sh /tmp/rprobes/p6_legit.py /tmp/ba
         20s bash   date; cd /tmp/rprobes && for p in p23_annshadow p26_setter_plain_deep p27_frac_ro_via; do echo "##### $p HEAD"
         17s bash   cd /tmp/rprobes && for p in p_submethod_read p_deeper_prop p_prop_setter_inherit p_del_roprop p_attr_after_pro
          8s bash   cd /tmp/rprobes && cat > p_attr_after_prop2.py <<'EOF' class A:     @property     def x(self):         return 
          6s bash   date; cd /tmp/rprobes && for p in p14_subplain p15_subplain2 p16_submsg p18_subplain_mixed p19_subplain_setter
          4s bash   date; cd /tmp/rprobes && cat > p_sameclass_after.py <<'EOF' class A:     @property     def x(self):         re


--- ORIGINAL TASK ---
**Decimal must work in the default int64 mode.** Since #284 ints are int64 by default and overflow stops. The Decimal prelude computes with 10 ** prec (prec 28), so `Decimal(1) / Decimal(3)` stops with "OverflowError: integer overflow in **" unless --exact-int is given. Decimal is a library; the user never asked for big ints, so this is wrong.

Fix: the Decimal (and Fraction, if it has the same problem) prelude code must use exact ints internally in every mode, while user code stays int64. Prefer the existing mixed / per-function exact-int machinery (intmode.py, bigcap.py) over a global switch. User-visible ints that come out of Decimal (int(d), d.as_tuple()) follow the user mode: they stop loudly if they exceed int64 in the default mode.

Acceptance:
- In the default mode these print the same as CPython: `Decimal(1)/Decimal(3)`, `Decimal("2").sqrt()`, `Decimal("10.50")*Decimal("3")`, `Decimal(2) ** 100`, `getcontext().prec = 50` then a division, `Decimal("1e30") + 1`.
- The tests marked exact only because of Decimal (test_ail_stdtop1) pass again without AIL_EXACT_INT=1.
- No change in run icount on lab/compare tasks that do not use Decimal: the generated C must be byte-identical for those tasks.
- Run the touched test modules plus test_ail_int64_default and test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
