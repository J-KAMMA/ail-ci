You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** removes `driver.py`'s blanket refusal for module-variable writers, makes int module statics `ail_tint` when the whole program is eligible (`GLOBAL_INT_TINT`), lowers `global.load/store` as tint, and adds `tint.pow`/`ail_tint_pow`; `bigcap.py` also trusts a module literal for constant powers.

**Probes (HEAD vs CPython, base checked):**
- `p1_counter` typed prints `2`; base refused. Verified.
- `p2_grow`, `p5_pow`, `p12_biglit`, `p17_double`: default path matches CPython; p2/p12 typed refusal is same as base (big power literal), acceptable.
- `p3_mixed`, `p4_neg`, `p11_while`, `p15_flow`: default matches; base same default output.
- `p6_negpow`, `p7_float`: typed refusal, default matches CPython and base.
- `p20_retmin`: **new regression** (below).
- `p13_str`/`p21_str`: C unchanged; `p13_plain`/`p14_modconst` C differs only by the unused `ail_tint_pow` helper.

**Tests:**
- `test_ail_globals`: **30/32**, not 32/32 (2 failures).
- `test_ail_safetynet`: 5/5 OK.
- `test_ail_bigint test_ail_tint test_ail_unified`: 62/62 OK.
- `test_ail_dunders test_ail_nested_functions test_ail_unbound`: 27 failures on both HEAD and base, identical names (report verified).
- `test_ail_files`, `test_ail_corpus_findings3`: not run.
- `tools/update_manifest.py --check`: **rc=1**, seven stale files; `par_check.py` preflight raises `ValueError: hash mismatch: python/pkg-v12/pyfunc.py`.

**Defects:**
1. Returning a module int that grew past int64 now crashes the default (typed) build. Probe `/tmp/rprobes/p20_retmin.py`:
```python
x = 4611686018427387904
def get() -> int:
    return x
def main() -> None:
    global x
    x *= 4
    print(get())
main()
```
Expected `18446744073709551616` (CPython and base default/general path). Actual HEAD default: no stdout, stderr `integer overflow`, exit 1 (both AIL_IR=0 and AIL_IR=1). Caused by the new tint global being converted to the function's int64 return.
2. Required `test_ail_globals` still fails: `test_a_range_bound_is_read_once_and_a_while_test_every_time` — typed refusal `a range loop with a tagged start or step needs a tagged index`; `test_floats_negative_and_large_starts_and_every_operator` — typed refusal `a bit operation on an unproven int` (`e |= 3`). Both tests must pass typed; report's 32/32 claim is false.
3. `MANIFEST.json` was not refreshed after commit `6db0182`; `--check` fails and `par_check.py` cannot run (hash mismatch), contradicting the report.

Minor: int-only programs that never touch module variables get a new unused `ail_tint_pow` in their C, so that C is not byte-identical to base (no behavioural difference observed).

Probe both builds with `bash ~/tools/cmp.sh`, add each fixed case to the tests, then commit. If a finding cannot be fixed safely, refuse the construct by name at compile time instead of leaving a silent wrong answer.

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
