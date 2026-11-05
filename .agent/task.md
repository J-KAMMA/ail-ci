**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review — bce s7 (work..HEAD)

**What the change really does.** `symbounds` gains while-loop bounds (`_while_index`, `while_of`), `LICM.version` widens its versioning scope to the whole loop region whenever BCE is on, and `LICM.entry_version` clones a function body under an `if (params)` guard. `_nondecreasing` now only accepts `v = a + c`, `c >= 0`.

**Verified claims.**
- `sub` rejected in `_nondecreasing`; `dec_neg2`, `list_append`, `le_entry_oob` match CPython in both builds (re-ran).
- `dec_while_guard` added and asserts `versioned=0`; `test_ail_bce` + `test_ail_safetynet` pass (`-j 2`, 155 s).
- `update_manifest.py --check` passes.
- `AIL_BCE=0` generated C is byte-identical to base (cond2_bytes); a no-feature program's C is identical to base.
- `.ail` added: `entry_emit_guard`, `echo_while_guard`, `dec_while_guard`.

**False / not done.**
- Task (d) required probes for a while bound reassigned in the loop and a list param appended in the loop to be appended to `test_ail_bce.py`; only `dec_while_guard` was added (those two were run only as throwaway `/tmp` probes). No big-text bound probe either.

**Defects**
1. The whole-test scope widening assumes the induction compare is the **first** conjunct, but `_while_index`/`_first_cmps` (and `entry_version`) accept it anywhere in the `and` chain. An access in an earlier conjunct is then versioned as if it were inside `[init, e-1]` and emitted unchecked.
   Probe `/tmp/rprobes2/cond2_bytes.py`:
   ```python
   def f(d, v, b):
       e = b - 1
       n = 0
       while d[v] == 0 and v < e:
           n += 1
           v += 1
       return n
   print(f(b"abc", 5, 2))
   ```
   Expected (CPython, and base): exit 1, empty stdout, `IndexError: index out of range`.
   Actual (HEAD default build): exit 0, stdout `0`. Generated C's fast arm does `v_d.p[ir8]` with no check. `AIL_BCE=0` restores the correct exit 1; `AIL_BCE_AUDIT=1` exits 86 (`removed check would fire in f site 0`), confirming the guard is unsound.
   Second instance `/tmp/rprobes2/cond2_body.py` (`f(b"\x00\x00\x00", 4, 3)`): expected stdout `2` + exit 1; actual stdout `2\n0`, exit 0. Same root cause.
2. (Task compliance) missing required regression probes in `test_ail_bce.py` (loop bound reassigned inside the loop; list param appended inside the loop), so the required shape is not pinned.

**Pre-existing:** none observed — the two probes above match CPython on `/tmp/base`.

**Unverified:** the central numbers (term_rank ≤0.98, echo_pack ≤0.985) and stripped-byte sizes — `perf_event_open` is denied and valgrind is absent; DEVLOG itself says icount was not measured. Compile-time gate (DEVLOG reports max +3.1%, i.e. not clearly within the 3% done-check). Census outputs/10 tasks not re-run.

VERDICT: FIX
1. `while <access> and v < e` over-elides: induction compare accepted from any conjunct while the versioning scope is widened to the whole test; access in the first conjunct is unchecked. Probe `/tmp/rprobes2/cond2_bytes.py`: expected exit 1 + empty stdout (`IndexError`), actual exit 0 + `0`. Restrict the versioned scope/bound to a first-conjunct `v < e` (in `_while_index` and `version`), or leave earlier-conjunct accesses checked.
2. (Compliance) add the required loop-bound-reassignment and list-append probes to `AIL_CURRENT/test_ail_bce.py`, per task (d).
[commandcode stop=end_turn turns=51 out_tokens=49507]


--- ORIGINAL TASK ---
Lane: bce-ranges

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s7: entry and while-loop versioning for checks that hold under one cheap guard

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s3 merged** (needs the s3
rules and `AIL_BCE_EXPLAIN`; bce-s1 tools). Time budget: **80 minutes**. Commit and push after each sub-step
(a)–(d); open the PR after (a). Do not touch `.github/workflows`. Follow Appendix A.

**Number this moves:** term_rank icount drops by at least **2%** (measured 2.5%: `emit_line`'s `data[i]` and
`data[j]`) and echo_pack by at least **1.5%** more than after s3 (measured 2.1%: `d[p + m]`). No task gets
worse; stripped binary bytes may grow only on a task whose icount drops at least 1%, by at most 1% (owner rule
pending; if the owner has not answered, report the bytes and keep going).

## Background

`ir/passes/licm.py` (part 3) with `ir/passes/symbounds.py` already versions **`for.range`** loops: it builds a
once-per-entry guard (`up >= 0 and up + w - 1 < len(cur)`) in atoms defined before the loop, with caps
(`ATOM_MAX`, `COEF_MAX`, `CONST_MAX`, `TERMS_MAX`) so the guard cannot overflow, and runs the fast copy when the
guard holds. Two shapes it does not reach:

```
# term_rank/main.ail -- called only as emit_line(st, data, pos, e) with 0 <= pos <= e <= len(data)
fn emit_line(st: St, data: bytes, a: int, b: int) -> void {
    let i = a;
    while i < b {
        if not isw(data[i]) { i += 1; continue; }            # line 60
        ...  let j = i;
        while j < b { let c = data[j]; ...  j += 1 ... }      # line 65
# echo_pack/main.ail, inner loop (p >= 0 from the outer while test; maxm <= 131)
            while m < maxm and d[p + m] == d[i + m] { m += 1; }      # line 45, d[i + m] proven by s3
```

## Changes (guarded by `bce_enabled()`; `AIL_BCE=0` → C identical to base)

(a) **While loops.** Let `symbounds` treat a `while` loop whose test is `v < e` (or `v < e and …`, the first
    conjunct) with a carried `v` stepping by a constant `+1` (or any `+c`, `c >= 1`) like a `for.range` with
    `lo = v_init`, `hi = e` when `e` is loop-invariant (defined before the loop, no store to it in the loop).
    Then `d[p + m]` gets the guard `p >= 0 and p + maxm - 1 < len(d)` (plus `m_init >= 0`).
(b) **Function-entry versioning.** For a function whose body has `ck` accesses inside loops that the explain
    dump shows would be proven by facts on parameters only (`a >= 0`, `b <= len(data)` for a `bytes` param, or a
    list param no instruction in the function can change the length of — no length-changing op on any list, no
    call that may write a list or is unknown), emit at entry `if (<guard on params>) <fast body> else <body>`.
    Limits: only when at least one loop access becomes `nck`; at most 200 IR instructions cloned per function;
    at most 4 guard terms; guard arithmetic with the `symbounds` caps.
(c) Audit: the s1 audit statement must cover every `nck` access in fast copies (it checks against the real
    length, so a wrong guard is caught).
(d) Probes + numbers + DEVLOG.

## Probes (append to `test_ail_bce.py`; default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`; CPython oracle)

- `emit_line`-like function called with `(a, b)` = `(0, len)`, `(len, len)`, `(0, len + 1)` (slow copy: raises at
  the same place), `(-1, 3)` (slow copy: `data[-1]` reads the last byte as CPython), and with `b` from text beyond
  int64 (rule 2);
- the echo inner loop with `p = -1` reachable (guard false → slow copy), with `maxm` exactly `len - p`, and one
  more (raises at the same iteration as CPython);
- a `while` loop whose bound `e` is reassigned inside the loop (must not be versioned);
- a list param that the function appends to inside the loop (must not be versioned).
Each versioned probe asserts (explain dump or `AIL_IR_STATS`) that the fast copy exists.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` exits 0; term_rank/ail ratio
  ≤ 0.98, echo_pack/ail ratio ≤ 0.985; report stripped bytes for every changed task.
- `AIL_BCE_AUDIT=1` on all cases of the ten tasks and on `tools/difffuzz.py --run --start 0 --count 300 -j 2`:
  no exit 86, no new diff.
- `tools/par_check.py -j 2 test_ail_bce test_ail_ir_gridbounds test_ail_range_checks test_ail_ir_s1
  test_ail_ir_s3 test_ail_ir_rulex`; `tools/codegen_diff.py --pins` (list pin changes).
- Compile time of term_rank and echo_pack within 3% of base; all 20 shards green.

## Stop rule

Stop and report if: any audit run exits 86; a task's icount rises; a task's stripped binary grows more than 1%;
(b) needs whole-program call-site facts (that is a different step); or 80 minutes pass. If (a) lands and (b) does
not fit, land (a) alone and report (b)'s state.

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
counter): term_rank base 15.62e9 (`emit_line` sites 2.5%); echo_pack base 6.155e9 (`d[p + m]` 1.3% alone, 2.1% on
top of `d[i + m]`).

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
