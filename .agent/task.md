Lane: codegen

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s5: one index check per parallel-list group (normalized index + CSE)

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s4 merged** (needs
`facts['fields']` groups and `AIL_BCE_FACTS`; bce-s1 tools). If s2 is merged, measure on top of it. Time budget:
**80 minutes**. Commit and push after each sub-step (a)–(d); open the PR after (a). Do not touch
`.github/workflows`. Follow Appendix A.

**Number this moves:** tally_lang icount drops by at least **7%** relative to its base (hand-edit measured 7.8%
for the three sites in `ev`; 14.1% together with s2). ledger_bin and tree_fold may drop slightly (0.95%, 0.47%).
No task gets worse.

## Idea

`ev(p, i)` reads `p.n_op[i]` then `p.n_a[i]`, later `p.n_b[i]`; `p.has[a]` then `p.val[a]`. s4 proves these lists
always have equal length (and only grow). The first access keeps its check; the others are in range **at the
normalized index** the first check produced. Negative indices stay exact: `j` is in `[0, len)` and every member
is read at `j`. The error, its message and its place are unchanged because the first access is the one that
raises in both versions.

## Changes (guarded by `bce_enabled()`; `AIL_BCE=0` → C identical to base)

(a) New IR op `idx.norm(i, len) -> i64` with `attrs['kind']` = the error of the access it came from (read:
    `list index out of range`; store: `list assignment index out of range` / the numeric-field index error the
    accessor raises today — copy exactly what the replaced accessor calls). Verifier entry in `ir/verify.py`,
    effect = may raise (`ir/effects.py`), printing in `ir/text.py`/`emit_text.py` if those print every op, and C:
    `static inline int64_t ail_idx_norm_<kind>(int64_t i, int64_t n) { if (__builtin_expect((uint64_t)i < (uint64_t)n, 1)) return i; i += n; if ((uint64_t)i >= (uint64_t)n) <same fail call as the accessor>; return i; }`
(b) New pass `ir/passes/groupcse.py`, run right after the first `ranges` run (`ir/passes/__init__.py`), only when
    `facts['fields']` has groups. For a `ck` access `Y[i]` (`span.get`, `span.set`, `list.get`, `list.set` on a
    field list `field.list o.f` or a group local) find a **dominating** `ck` access `X[i]` with the same SSA `i`,
    `X` = `field.list o'.g` with the same SSA object `o' = o` (or the same local group), `f` and `g` in one group,
    and **no possible length change of the group between them**: either the group is grow-only, or no instruction
    between them is a group block, a call whose summary may write the struct's lists, or an unknown call.
    Rewrite `X[i]` into `j = idx.norm(i, len X)` + `nck X[j]`, and `Y[i]` into `nck Y[j]`. One `idx.norm` per
    (group, `o`, `i`). Leave `X` unchanged when no `Y` uses it (no gratuitous C changes).
(c) Audit (`AIL_BCE_AUDIT=1`): the s1 audit statement already guards every `nck`; make sure it is emitted for the
    rewritten `Y` accesses with `Y`'s own length.
(d) Probes + numbers + DEVLOG.

## Probes (append to `test_ail_bce.py`; default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`; CPython oracle)

- tally-like evaluator: `ev(p, i)` over `n_op/n_a/n_b`, called with `i` = valid, `-1`, `-len`, `len`, `-len-1`
  (the last two raise at `p.n_op[i]`, same message);
- the same with a recursive call between `n_a[i]` and `n_b[i]` that appends to the group (grow-only: still
  proven) and one that pops from it (not grow-only: must stay checked; `IndexError` at `n_b[i]` as CPython);
- `has[a]` / `val[a]` with `has` read first and `val` second, and the reverse order;
- an index store `p.s_j[t] = v` after `p.s_kind[t]` read (store error message must be the store's own if it is
  the first access);
- group invalidated by one extra `p.n_a.append(0)` elsewhere in the program: no rewrite (C equal to `AIL_BCE=0`);
- two different objects `p`, `q` of the same struct: `p.n_op[i]` does not cover `q.n_a[i]`.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` exits 0; tally_lang/ail icount
  ratio ≤ 0.93; every other changed task ratio ≤ 1.0, same output.
- `AIL_BCE_AUDIT=1` on all cases of the ten tasks (`run_task.py --langs ail --icount none --smoke`) and
  `tools/difffuzz.py --run --start 0 --count 300 -j 2` in audit mode: no exit 86, no new diff.
- `tools/par_check.py -j 2 test_ail_bce test_ail_ir_s1 test_ail_ir_s2 test_ail_ir_s3 test_ail_ir_s3b
  test_ail_range_checks test_ail_mixed_bounds`; `tools/codegen_diff.py --pins` (list pin changes).
- Compile time of tally_lang within 3% of base; all 20 shards green.

## Stop rule

Stop and report if: any audit run exits 86; tally's drop is below 5% (attach `ev`'s C); a rewritten access
would need a different error than the access it replaces; the pass changes C of a task without lowering its
icount; or 80 minutes pass. The `try`-bearing `run` function is skipped by the pass pipeline today; do not
change that here.

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
counter): tally_lang base 21.66e9; `n_a[i]`, `n_b[i]`, `val[a]` in `ev` unchecked: −7.8%.

## Appendix C: tally_lang `ev` today (`lab/compare/src/tally_lang/main.ail` line 274 and its C)

```
fn ev(p: Prog, i: int) -> int {
    let op = p.n_op[i];
    let a = p.n_a[i];
    if op == 100 { return a; }
    if op == 101 { if not p.has[a] { raise ValueError("r"); } return p.val[a]; }
    ...  let l = ev(p, a);  let r = ev(p, p.n_b[i]);  ...
```
```c
    ail_list *ir1 = (&(v_p)->f_n_op);
    int64_t ir2 = ail_list_span_get((ir1)->p, (ir1)->n, v_i);
    ail_list *ir3 = (&(v_p)->f_n_a);
    int64_t ir4 = ail_list_span_get((ir3)->p, (ir3)->n, v_i);
```

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
