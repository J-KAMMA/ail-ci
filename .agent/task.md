**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — emit1 (lane emitdesign)

**What the change really does:** adds `lab/emit/` (callgrind per-line measurement, an `other` sub-classifier, hand-edit bound scripts + patches + JSON data) and `docs/design/EMIT_LEAN.md`, plus DEVLOG/DIFFERENCES rows. `git diff work..HEAD -- AIL_CURRENT tools` is empty: no compiler, runtime or corpus change. That matches the task.

**Reproduced**
- `analyze.py --tasks echo_pack` (fresh work dir): AIL 5,447,660,698 / C 1,866,703,076 vs committed 5,447,660,701 / 1,866,703,042 — reproducible to ~30 instructions.
- `classify.py` rerun: `data/causes.json` byte-identical.
- `bounds.py --only echo_pack_dict2`: saved 1,927,251,228 vs committed 1,927,251,194 — matches the rank-1 bound.
- Required modules on HEAD, `par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 3/3 pass.
- Manifest `--check` clean; line references in the design (`_depth_call` 677, guard 763, wrapper 795, `dict_op` 1693, `ail_tab_hslot` 5350, `ail_bytes_to_int` 6015) all correct.

**Defects**

1. **Rank 3 is off by 6.2×: the queued change buys 190M, not 1,184M.** The 1,184M is `tally_lang_norec`, i.e. deleting the entry guard with nothing put back — not the change design 2 proposes. The design's own `tally_lang_edge` patch is the correct replacement, and it was measured (a leftover `bounds.py` run wrote it during review; I reran it independently):
   - probe: `python3 lab/emit/bounds.py --tasks tally_lang --only tally_lang_edge,tally_lang_norec --work /tmp/rv-b --out /tmp/rc/bounds_edge.json`
   - expected by EMIT_LEAN (lines 20, 38-40, 157, 220-224, 347-348): net ≈ the 1,184M "tally_lang_edge bound in the same file"; actual: **189,632,811 net** (19,585,728,469 → 19,396,095,658), and no such row exists in `RESULTS.md` or `data/bounds.json` (which omits the variant entirely).
   - consequence: at 190M the cause ranks ~7th, below overflow (1,012M), list helpers (1,001M), accessors (952M) and ASCII (490M); the "three queueable total 4.1e9" is 3.1e9, and task B's headline benefit is 6.2× overstated. Step 2.3 ("record the net") was never done in a committed file.

2. **Design 1's `fast` mark permits iteration, so it can change output.** It requires only "never iterated *while inserted into*" and says the order list is unused because the dict is "never iterated (that is part of the mark)" — the mark as written does not imply that (`for k in d:` / `list(d)` / `repr(d)` after inserts qualifies).
   - probe: `d = {1: 'a', 2: 'b'}; d[3] = 'c'; print(list(d))`
   - expected (CPython): `[1, 2, 3]`; with an `ail_fdict` (open addressing over `used[]`, no order list) the iteration order is hash order. The mark must be "never iterated/printed/compared", or the structure must keep insertion order.

3. **Design 3's shift rule is unsound for a negative left operand.** "`x << k` with `hi(x) < 2^(63-k)`" checks only the upper bound; Python's `<<` overflows on magnitude.
   - probe: `x = -2**62; print(x << 2)`
   - expected: `OverflowError`; the rule as written proves "cannot overflow" (`hi(x) = -2^62 < 2^61`), emits `mode='wrap'`, and yields a silent wrapped value. A `lo(x) >= -(2^(63-k))` condition (or a magnitude bound) is required.

**Minor / non-blocking**
- DEVLOG says the checks are `11%`; the RESULTS table gives 5,607/57,185 = 9.8% (RESULTS text says 10%). One is wrong.
- `echo_pack_dict2`'s 1,927M bound also removes idict growth, the order list and cleanup (fixed `1<<20` table, arrays never freed), so it is not purely "the probe"; it is labelled an upper bound, but the docs attribute the whole amount to cause 1.
- 4a/4b: not applicable (no compiler, runtime, I/O or buffer change). No speed/icount run needed for the same reason.

**Unverified:** only `echo_pack` totals were re-measured (not the other five); `ticket_audit_nometa` and the remaining bounds were not re-run; no `.agent/cmp.sh` corpus pass (nothing to compile differently).

VERDICT: FIX
1. `tally_lang_edge` is measured at 189,632,811 Ir, not the 1,184M the ranking uses: record the net in `RESULTS.md`/`data/bounds.json`, retitle design 2, re-rank cause 3 (~7th), and restate the queueable total as ~3.1e9 (probe: `bounds.py --only tally_lang_edge`, expected 19,585,728,469 → 19,396,095,658, saved 189.6M; actual committed docs claim a 1,184M net bound that does not exist).
2. Design 1's fast-dict mark must exclude all iteration/printing: `d={1:'a',2:'b'}; d[3]='c'; print(list(d))` expected `[1, 2, 3]`, fast dict gives hash order.
3. Design 3's shift rule must bound the negative side: `x=-2**62; print(x<<2)` expected `OverflowError`, rule as written proves wrap and silently wraps.
[commandcode stop=end_turn turns=40 out_tokens=22363]


--- ORIGINAL TASK ---
Lane: emitdesign

# emit1: why AIL's typed C executes more instructions than hand-written C, and a design to emit leaner C (measurement + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/emit/*` and `docs/design/EMIT_LEAN.md`.

**Why (owner, 2026-11-07: subtract before adding):** roof1 (`lab/roof/RESULTS.md`, section "Subtraction") found that
54-100% of the typed path's extra instructions over C are in the `other` class: the shape of the emitted code
(temporaries, reloads, one statement per Python operation), not checks. `ticket_audit` executes 5.4x C's
instructions, `echo_pack` 2.9x, `tree_fold` 2.0x, `ledger_bin` 1.9x, `tally_lang` 1.7x.

## Measure (`lab/emit/RESULTS.md`)
Reuse `lab/roof/attrib.py`. For those five programs plus `berth_sim`: take the 10 hottest emitted functions, put the
emitted C next to the matching hand-written C (`lab/compare/src/<task>/main.c`), and sub-classify the `other`
instructions by cause, with Ir per cause: e.g. struct/string passed by value, temporaries that block register
allocation (address taken), repeated loads through a pointer gcc cannot prove unaliased, helper calls not inlined
(and why: size, `noinline`, separate unit), generic helpers where a specialised loop exists (string building,
byte parsing, dict probe), redundant length/cap reloads, int<->float or width conversions, exceptions/unwind state
checks after calls. Show 2-3 concrete before/after C snippets per cause, and for each cause the Ir if it were removed
(measure by hand-editing the emitted C in a throwaway copy, rebuilding with the same flags, and checking stdout
byte-identical: that is the real bound, not an estimate).

## Design (`docs/design/EMIT_LEAN.md`)
Rank the causes by measured Ir saved across the six programs. For the top 3: what in the emitter (file:function)
produces it, the change, how correctness is proven (CPython-identical on the corpus via `.agent/cmp.sh`, icount no
loss on any compare program), and its interaction with exe bytes (allowed to change). Split each into implementation
steps of at most 2 hours with its own files, test and number, written as ready-to-queue task text at the end.

## Sub-steps
1. (70 min) Sub-classification + hand-edit bounds in RESULTS.md. Commit, push.
2. (50 min) EMIT_LEAN.md with ranking and step split. Commit, push.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
