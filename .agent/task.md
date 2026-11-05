Lane: bce-ranges

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s3: stronger index proofs in the IR range pass (list.get, while induction, sum rule, constant joins)

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s1 merged** (needs
`lab/beatc/bce_census.py`, `bce_enabled()`, `AIL_BCE_AUDIT`, `test_ail_bce.py`; if missing, stop). Independent of
s2. Time budget: **80 minutes**. Commit and push after each sub-step (a)–(e); open the PR after (a). Do not touch
`.github/workflows`. Follow Appendix A.

**Number this moves:** echo_pack icount drops by at least **5%** (hand-edit measured 5.9%: the check on
`d[i + m]` in `pack`, source `lab/compare/src/echo_pack/main.ail` line 45, ran 67M times). No other task gets
worse.

## Background (file `AIL_CURRENT/python/pkg-v12/ir/passes/ranges.py`)

Facts per i64 SSA value: `[lo, hi]`, `ub = {w: c}` (v <= w + c), `lb = {w: c}`. `in_bounds(env, base, index)`
proves `0 <= index <= len - 1` from `lo >= 0` and a `ub` on a `bytes.len`/`span.len` value of the same base
(one extra symbolic step). Decisions: `bytes.get`, `span.get/set` → mode `nck`; **`list.get`/`list.set` are never
decided** (the `if op in ('span.get', 'list.get')` branch only handles `span.get`). The echo loop:

```
let n = len(d); ...  while i < n {           # i only grows (i += 1, i += bestlen with bestlen >= 0)
    if i + 4 <= n { ... let maxm = n - i; if maxm > 131 { maxm = 131; }
        while p >= 0 and seen < 8 and i - p <= 65535 {
            let m = 4;
            while m < maxm and d[p + m] == d[i + m] { m += 1; }      # d is a bytes parameter
```

`d[i + m]` needs: `i >= 0`, `m >= 4`, and `i + m <= n - 1` from `m <= maxm - 1` and `maxm <= n - i`.
(`d[p + m]` needs a guard on `p`; that is s7, leave it checked.)

## Changes (all guarded by `bce_enabled()`; `AIL_BCE=0` must give byte-identical C to integ)

(a) **Explain dump** `AIL_BCE_EXPLAIN=path`: after the final ranges run, append one JSON line per access still in
mode `ck`: function, op, index fact (`lo`, `hi`, `ub`, `lb` with SSA names), the length values considered, and
which rule failed. Use it to confirm each rule below fires where intended.
(b) **Sum rule** in `in_bounds`/`bounds`: for an index defined as `add(a, b)` (either order; mode `ck` or `nsw`),
if `b <= w + c` (through up to two steps) and `w` is defined as `sub(L, a)` with the *same* SSA `a`, then
`index <= L + c`; then the usual test against the length. Symmetric for lower bounds is not needed.
(c) **Constant arm in joins**: when one arm of an `if` assigns a constant `k` to a carried/yielded value and that
arm's refined env proves `k <= w + c` for a `ub` entry `{w: c}` the other arm has, keep `{w: c}` in the join
(`if maxm > 131 { maxm = 131 }` keeps `maxm <= n - i`). Same for `lb`.
(d) **While induction**: a loop-carried value whose initial value is `a` and whose every back-edge value is
`v + c` with `c >= 0` (or `v + x` with `x.lo >= 0`) gets `lb {a: 0}` and `lo >= a.lo`; check this already holds,
and make it hold through nested `if`/`continue` joins if it does not.
(e) **`list.get`/`list.set` decisions** for lists, with a conservative length rule: accept a `list.len` value of
the same list SSA value only if the function contains no length-changing list op (`append`, `pop`, `insert`,
`del`, `clear`, `extend`, slice store) on any list and no call whose effect summary (`ir/effects.py`) may write
a list or is unknown. Emit `nck` for `list.get/set` exactly as `span.get/set` does.

## Probes (append to `test_ail_bce.py` `PROBES`; default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`; CPython oracle)

For each rule, the proven case **and** the off-by-one neighbour that must still raise at the same place:
- echo-like: `while m < maxm and d[i + m] == d[j + m]` with `maxm = n - i` capped at a constant, `n = len(d)`,
  for `i = 0`, `n - 1`, `n` (empty inner loop), and a variant with `maxm = n - i + 1` (must raise
  `IndexError: index out of range` at the same iteration as CPython);
- the cap arm: `if maxm > 3 { maxm = 3 }` and `if maxm > 3 { maxm = n }` (the second must not be proven);
- induction: `i` grown by `i += k` with `k = len(xs) - len(xs)` (0) and with `k` read from text (unknown sign:
  not proven, still correct), including a text value beyond int64 (rule 2);
- `list.get`: a local list indexed in a loop with no mutation (proven), the same list appended to in the loop or
  passed to a function that appends (not proven; raises at the same place).
Every probe meant to be proven asserts through `AIL_IR_STATS` (`idx_ssa_proven`) or the explain dump that it is.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` exits 0; echo_pack/ail icount
  ratio ≤ 0.95; every other changed task has ratio ≤ 1.0 and same output.
- `AIL_BCE_AUDIT=1` on all cases of the ten tasks (`run_task.py --langs ail --icount none --smoke`) and
  `AIL_BCE_AUDIT=1 python3 tools/difffuzz.py --run --start 0 --count 300 -j 2 --out /tmp/fz`: no exit 86, no new diff.
- `tools/par_check.py -j 2 test_ail_bce test_ail_range_checks test_ail_ir_gridbounds test_ail_mixed_bounds
  test_ail_ir_s1 test_ail_ir_s3 test_ail_ir_rulex`; `tools/codegen_diff.py --pins` (list any pin change in the PR).
- Compile time of echo_pack and tally_lang (`tools/compile_phases.py`, median of 5) within 3% of base.
- All 20 shards green; DEVLOG entry.

## Stop rule

Stop and report if: any audit run exits 86; echo's drop is below 4% (attach the explain line for `d[i + m]`);
the analysis budget is exceeded on any compare-lab function that was not exceeded before; rule (e) changes C
of a task without lowering its icount; or 80 minutes pass. Do not add rules beyond (b)–(e).

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
counter): echo_pack base 6.155e9; all its index checks 9.5%; `d[i + m]` alone 5.9%; `d[p + m]` 1.3% (s7).

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
