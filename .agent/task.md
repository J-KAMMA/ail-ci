Lane: bce-ranges

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s6: field values in the range pass (load numbering + non-negative field facts)

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s3 and bce-s4 merged**
(needs the s3 rules and explain dump, s4 `facts['fields']['nonneg']`; if missing, stop). Time budget:
**80 minutes**. Commit and push after each sub-step (a)–(d); open the PR after (a). Do not touch
`.github/workflows`. Follow Appendix A.

**Number this moves:** ledger_bin icount drops by at least **6%** (hand-edit measured about 8%: `readvar`'s
`r.data[r.pos]` 3.0%, and `data[i]`/`data[start]`/`data[r.pos]` in `main` 5.1%). No task gets worse.

## Shapes (`lab/compare/src/ledger_bin/main.ail`)

```
struct Rd { data: bytes; pos: int; err: int; }
fn readvar(r: Rd) -> int {
    ...  while True {
        if r.pos >= len(r.data) { r.err = 1; return 0; }
        let b = r.data[r.pos];            # line 9: r.pos loaded twice, nothing stored in between
        r.pos += 1; ...
# main:
    let r = Rd(data, 6, 0);  let n = len(data);
    while r.pos < n {  let start = r.pos;  let op = data[start];  r.pos += 1;  ...   # line 49-51
        ...  if r.pos >= n { r.err = 1; }
             else { let c = 0; let i = start;
                    while i < r.pos { c = (c * 31 + data[i]) % 251; i += 1; }     # line 103-106
                    if data[r.pos] != c { r.err = 4; }  r.pos += 1; }               # line 108
```

Needed: (1) two `field.get o.f` with the same SSA `o` and no possible write of `o.f` between them are the same
value (then the guard on the first applies to the second); `r.err = 1` writes another field and does not kill
`pos`; (2) `Rd.pos >= 0` from s4 gives `lo >= 0` to every load of `pos`; (3) a `bytes` field (`r.data`) is
immutable, so `len(r.data)` of two loads of `r.data` with no store to `r.data` between is one length value.

## Changes (guarded by `bce_enabled()`; `AIL_BCE=0` → C identical to base)

(a) **Field load numbering** in `ir/passes/ranges.py` (or a small helper it calls): map each `field.get` to a
    canonical earlier `field.get` of the same object SSA value and field name when, on every path between them,
    no instruction may write that field: a `field.set` of the same field name on **any** object of that struct
    type (objects may alias), a call whose effect summary may write that struct's fields or is unknown, an
    outlined try body. Facts of the canonical value apply to the later one. Inside loops the fixed point must see
    a store to the field anywhere in the loop as a kill on the back edge.
(b) **Non-negative fields**: every `field.get` of a field listed in `facts['fields']['nonneg']` starts with
    `lo = 0`.
(c) **Immutable bytes fields**: `bytes.len` of two numbered loads of a `bytes` field is the same length value for
    `in_bounds`.
(d) Probes + numbers + DEVLOG.

## Probes (append to `test_ail_bce.py`; default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`; CPython oracle)

- `readvar`-like loop over a field cursor: input lengths 0, 1, exactly at the end, one short; the guard written as
  `>=` and as `>` (the `>` version must not be proven: `r.pos == len` reads out of range and raises as CPython);
- a call between the guard and the read that moves `r.pos` (`bump(r)`: not proven, raises at the same place);
- two params `r1`, `r2: Rd` that are the same object at run time: `r2.pos = 99` between `r1`'s guard and
  `r1.data[r1.pos]` (must not be proven);
- `Rd.pos` set negative on one rare path elsewhere in the program (s4 drops the fact): `r.data[r.pos]` with
  `r.pos == -1` reads the last byte exactly as CPython;
- `int(text)` stored into `r.pos` with a text value beyond int64 (rule 2: same stop as today).

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` exits 0; ledger_bin/ail icount
  ratio ≤ 0.94; every other changed task ratio ≤ 1.0, same output.
- `AIL_BCE_AUDIT=1` on all cases of the ten tasks and on `tools/difffuzz.py --run --start 0 --count 300 -j 2`:
  no exit 86, no new diff.
- `tools/par_check.py -j 2 test_ail_bce test_ail_range_checks test_ail_ir_s1 test_ail_ir_s3 test_ail_ir_s3b
  test_ail_borrowed_owner test_ail_boolfield`; `tools/codegen_diff.py --pins` (list pin changes).
- Compile time of ledger_bin and tally_lang within 3% of base; all 20 shards green.

## Stop rule

Stop and report if: any audit run exits 86; ledger's drop is below 4% (attach the explain lines for lines 9 and
105); the effects model cannot say "this call does not write field f" without new summaries (say which calls);
any task's icount rises; or 80 minutes pass.

## Appendix A: standing rules (owner-approved 2026-10-30)

1. **No regressions.** A program that built and matched CPython before must still do so after, in the default
   build. A loud stop only where the value cannot be computed. When a fast path cannot handle a case, keep the
   old route.
2. **Big values.** Wherever ints come from text, fields or arithmetic, probe values beyond int64 too. Run every
   probe in the default build AND with `AIL_UNIFIED_FORCE=1` and compare both with CPython.
3. **CI before you report.** Push early, open the PR against `integ` of `J-KAMMA/ail-ci`, wait for all 20
   `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all
   pass, or say exactly which fail and why.
4. **Stack at most 2 deep.** Branch from integ or from one unmerged PR, never from a stacked PR.
5. **Memory.** Wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py` at `-j 2` at most; leave no
   background jobs running.
6. Batch `gh` queries; never poll in a tight loop.
7. **Registration.** New test module: add `AIL_CURRENT/tests.d/<module>.txt` containing the module name, `git
   add` it, run `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
8. **Never** read or print credentials, run a broad `pkill`, merge PRs, change repository settings, cancel runs,
   or edit `.github/workflows`. **No compare-lab number may get worse.**

## Appendix B: measuring on a GitHub runner

`perf_event_open` is denied on runners: `sudo apt-get install -y valgrind`; `lab/beatc/bce_census.py` then uses
callgrind (`--icount auto`). Base tree: `git worktree add /tmp/base origin/integ`. Reference (2026-11-03, perf
counter): ledger_bin base 5.372e9; all its index checks 11.9%; the sites of this step about 8%.

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
