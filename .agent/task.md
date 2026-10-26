You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**Time:** started 00:24, finished 00:40 (within 35 min).

**What the change really does:** it lowers `& | ^` on tagged ints into new inline `tint.and/or/xor` runtime routines (GC path `tint.py`, typed path as a separate `TINTBITS` piece), routes constant left shifts of >=63 to `tint.shl`, and adds a `driver.py` compile refusal for such shifts. This differs from the worker report, whose "Fix" section only describes the `TINTBITS` splitting/gating commit `412de56` and never mentions the main lowering commit `c3231c2` or the new shift/refusal behaviour.

**Report claims**
- `bit1` is `path: ir`, prints `4142726` — **verified**.
- Bit-free program C byte-identical to base — **verified** (`p8_plain`, `tintonly`, d and g, 0 diff).
- tint-but-no-bitops drops the bit routines — **verified** (`ail_tint_and` count 0, C same as base).
- "25 probes match CPython or raise by name in both builds" — **false/overbroad** (see defect below; base passes, HEAD does not).
- s0: only pre-existing `test_overflow...` — **verified**; base had 2 s0 failures incl. seed=23, HEAD 1 (seed=23 fixed).
- s3: 6F+1E strict subset of base 15F+1E — **verified** against worker's `/tmp/s3_head.log` vs `/tmp/s3_base.log`.

**Tests run on HEAD (`-j 2`):** `test_ail_safetynet` ok; `test_ail_ir_s0` 1 pre-existing failure; `test_ail_ir_s3` 6F+1E, names all present in base. Did not re-run bigint/tint/unified (not required by review step 3).

**Probes (`/tmp/rprobes/p*.py`, `~/tools/cmp.sh` both builds):** `p1_mix`, `p2_bigneg`, `p3_sources`, `p4_shiftvar`, `p7_invert`, `p8_plain`, `p10_shift32`, `p11_smallshift`, `p12_shiftret`, `p13_bigcount`, `p14_shiftneg`, `p15_mixsrc`, `p17/p18_augret`, `p19_lit100`, `p22_ok`, `p23_alias`, plus worker's `boundary`, `big_lit`, `shift_expr`, `shift_chain`, `aug63`, `promote`, `boolbit` — all match CPython in both builds. Operator semantics (&,|,^,<<,>>,~ over negative/large, variable counts, huge counts, aug-assign, list/attr/dict/arg sources) are correct.

**Pre-existing (fail on base identically at the same statement):** `p5_shiftconst`, `p6_shift200`, `p9_aug`, `p16_augbig` fail at module-level big literal shifts (e.g. `1 << 80` as a call argument) with `integer overflow` on both base and HEAD; HEAD additionally loses buffered partial stdout when it reroutes the program. Not counted as blocking.

**Defect (caused by this change)**

1. `AIL_CURRENT/python/pkg-v12/ir/lower.py:2394-2414` (new shift block) treats *any* constant left shift with count >= 63 as "a shift beyond int64", even when the value is 0 and the result fits. It raises `NotS0`, pushing the enclosing `None`-returning function/module body to the legacy emitter; the legacy emitter then converts a callee's big `tint` result to int64 and aborts. Base keeps that body on IR and is exact.

Probe `/tmp/rprobes/p20_regress.py`:
```python
def f(a: int) -> int:
    return a << 64
print(f(1))
print(0 << 63)
print(f(-1))
```
Expected (CPython and base, both builds):
```
18446744073709551616
0
-18446744073709551616
```
Actual (HEAD, default `d` build): empty stdout, stderr `integer overflow`, exit 1. (`g` build is correct.)

Same defect through a helper that returns `None`, `/tmp/rprobes/p21_regress2.py`:
```python
def f(a: int) -> int:
    return a << 64
def show() -> None:
    print(f(1))
    print(0 << 100)
show()
```
Expected `18446744073709551616` then `0`; HEAD `d` prints nothing and exits 1 with `integer overflow`; base passes.

Fix direction: do not classify `value << count` as beyond int64 when the value is zero (or when the shifted result actually fits), and do not send the whole enclosing body to the legacy emitter for shifts the base handled on IR.

**Unverified:** bigint/tint/unified modules (not re-run); instruction-count speed check (not a speed task); worker's individual 25 probes' reported results beyond those I re-ran.

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
