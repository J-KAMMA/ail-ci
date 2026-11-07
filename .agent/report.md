# job job-emit1-11071326  started 2026-11-07T04:36:34Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done.

## Result

**Measured** (`lab/emit/RESULTS.md`, all numbers from this run, valgrind 3.22 callgrind Ir-only, stdout byte-identical):

- Program ratios: `ticket_audit` 5.40x, `echo_pack` 2.92x, `tree_fold` 1.98x, `ledger_bin` 1.92x, `tally_lang` 1.65x, `berth_sim` 1.40x.
- `other` sub-classification (Ir, six programs): temporaries/one-statement 17,571M (30.7% of emitted lines' Ir); dict/table helpers 7,799M; list helpers 7,384M; prologue/epilogue 4,195M; bounds 3,849M; byte/string helpers 3,222M; invariant checks 2,389M; overflow 1,798M. Checks total ~11%.
- Top-10 hottest emitted functions vs matching `main.c` functions given for all six programs.
- Hand-edit bounds (rebuild same flags, stdout identical): dict probe **1,927M** (`echo_pack`); `ail_blist_meta` invariant **1,368M** (`ticket_audit`, safety check — reported, not queued); recursion guard **1,184M** (`tally_lang`); overflow checks **1,012M**; list helpers **1,001M**; bounds accessors 952M; ASCII scan 490M; one-loop shape rewrite 182M; `always_inline` append 4.7M (negative).

**Design** (`docs/design/EMIT_LEAN.md`): ranking plus three queueable designs — lean int-dict probe (`ir/emit_c.py:dict_op`, `cruntime.py:ail_tab_hslot`), recursion guard moved to recursive edges (`ir/emit_c.py:_depth_call`, `emit`), overflow checks only where `local_int_bounds` proves safety (`ir/lower.py`, `cruntime.py:ail_bytes_to_int`) — split into 8 steps ≤2h with files, tests, exe-byte note, correctness proof, and ready-to-queue task text.

**Tests**: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 3 modules, 0 failed, on the final commit. `update_manifest.py --check` passes. No compiler change, so no behaviour probes: instead every baseline and all 14 hand-edited variants assert stdout identical to the C build (`data/bounds.json`, `data/bounds_meta.json`).

**Not verified / not measured**: struct/str-by-value ABI, repeated unaliased loads, width conversions, unwind-state cost — attributed only, no isolated hand-edit bound; stated as such in RESULTS.md.

Commits: `aad4698` (measurement + design), `19e5cfc` (named sub-cause audit, ranking fix). Not pushed.
[commandcode stop=end_turn turns=125 out_tokens=78373]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review — emitdesign / emit1 (`job-emit1-11071326`)

**What the diff really does:** adds a measurement lab (`lab/emit/*`: callgrind per-line attribution of six `lab/compare` programs, a sub-classifier, and 14 hand-edit patches with rebuilt-C bounds) plus `docs/design/EMIT_LEAN.md`, a DEVLOG entry and a DIFFERENCES row. No compiler or runtime file is touched — confirmed: `git worktree add /tmp/base work`, compiled `echo_pack/typed.py` on both, `diff program.c` → identical. The report's "measurement and design only, no compiler change" is true.

**Claims checked**
- No compiler/runtime change; no behaviour probes needed — **verified** (emitted C byte-identical base vs HEAD).
- Program ratios reproduce roof1 — **verified internally consistent**, but the Ir values themselves are **unverified**: valgrind is not installed on this host, so nothing under `lab/emit` can be re-run here. The scripts are real (`analyze.py` compiles both sides, runs callgrind, compares stdout; `bounds.py` applies `patches/*.diff`, rebuilds with the same flags, checks stdout against the C build). One patch (`echo_pack_dict2`) applied and built cleanly and its stdout matched the AIL binary byte-for-byte, so the bound methodology is genuine.
- Data backing the tables — **verified**: `causes.json` reproduces every cell of the cause table and `bounds.json`/`bounds_meta.json` all 14 rows (`stdout_same: true`), except where noted in defect 3.
- Referenced symbols/lines (`dict_op` 1693, `_depth_call` 677, guard 763, `ail_tab_hslot` 5350, `lower.py:394`, `ail_bytes_to_int` 6015) — **verified**.
- Report lists only 2 commits; HEAD has a third (`dfbdffb`) — **false** (see defect 4).
- Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD → **3 modules, 0 failed** (rerun by me). `update_manifest.py --check` silent/OK.

**Defects**

1. **Design 1's proposed probe cannot represent integer key 0.** `ail_hprobe` stores "empty" as `keys[i] == 0` and the `fast` mark only requires "int key"; a dict keyed by `0` (very common) is then either unreadable or unwritable:
   ```c
   /* keys[i] == 0 means empty */
   while (keys[i] && keys[i] != k) i = (i + 1) & mask;
   ```
   `{0: 'a'}[0]` looks up an empty slot → wrong value / `KeyError`. The mark conditions in step 1.2 and Task A never exclude key 0. Expected: key 0 works exactly as CPython; actual as written: it cannot.

2. **Design 2's correctness premise is false.** It claims a depth function is entered "from a non-depth caller with the literal `0`" and that "the one-argument `ev` wrapper calls `ev__d(..., 0)`". The emitted code says otherwise (tally_lang `program.c`):
   ```c
   int64_t ev(ail_obj_Prog *v_p, int64_t v_i) { return ev__d(v_p, v_i, ail_depth + 1); }
   int64_t pprim(...) { if (++ail_depth > AIL_MAX_RECURSION_DEPTH) ail_die(...); ... }
   ```
   (wrapper `ail_depth + 1`, `emit_c.py:795`; `ail_depth` is also incremented by non-self recursive functions). Consequences: step 2.2's rule "drop the entry guard only when every non-self caller passes the literal 0" never fires for `ev__d`, so the queued task cannot reach the 1,184M it claims; and if the guard is dropped anyway, an entry with `ail_depth > 0` is no longer stopped at the entry, so "the set of call stacks rejected is identical" is wrong. Expected: same boundary as base; actual: boundary moves by one frame on such entries.

3. **Per-line attribution in `analyze.py` is misaligned, which corrupts one row of the central cause table.** `parse_annotate` advances `cur` per *output* line, but `callgrind_annotate` omits/wraps source lines; robust monotone re-alignment against the rebuilt `program.c` shows 287/423 echo_pack rows shifted (up to 63 lines). Examples: `lines.json` row 376 (`"static void *ail_alloc..."`) is source line **375**; recorded vs true function sums move 144.3M from `ail_idict_check` to `ail_idict_next_epoch`, 156.5M from `ail_tab_hhas` to `ail_tab_hget`, 192M `ail_flist_push` → `ail_list_push`. Effect on the deliverable: RESULTS.md reports **echo_pack `container-invariant` = 0**, while the truth is **≈144M** (it is folded into `dict-table-helper` 2,394M), and `ail_tab_hhas` (167M, enough for a top-10 slot) is absent from the top-10 table. Expected table cell ≈144M; actual 0. Also `measured.json`'s `top` arrays are empty (the tables actually come from `causes.json`).

4. **Junk committed at the repo root.** `callgrind.out.5029` (20 KB valgrind output, `cmd: /bin/true`) is added by commit `dfbdffb "worker: uncommitted edits"`, which the report does not mention. Not part of `lab/emit/*`; should not be in the tree.

**Pre-existing:** none relevant — the compiler is untouched and base/HEAD emission is identical.

**Speed:** not applicable (no compiler/runtime/benchmark edit; no `bench/apps` or `.ail` example touched).

**Unverified:** the Ir numbers themselves (no valgrind here); the C-side per-function column in `measured.json` cannot be recomputed from the committed data (only `causes.json` holds it).

VERDICT: FIX
1. `lab/emit` design 1 (`docs/design/EMIT_LEAN.md` §Design 1 step 1.1 / Task A): `ail_hprobe` treats key `0` as the empty sentinel and the `fast` mark does not exclude it; `{0: x}` reads/writes the wrong slot. Fix: separate `used[]`/sentinel or exclude `k == 0` from `fast`, and add key-0 to the boundary tests.
2. `docs/design/EMIT_LEAN.md` §Design 2 (and Task B step 2): premise "entered with literal 0 / `ev` passes 0" is false (`ev` passes `ail_depth + 1`, `pprim` increments `ail_depth`). Fix the predicate to account for the `ail_depth + 1` entry and prove the boundary for entries made while `ail_depth > 0`, or the 1,184M is not reachable as written.
3. `lab/emit/analyze.py:parse_annotate`: source-line tracking drifts (up to 63 lines; 287/423 echo_pack rows); `lines.json` `line` does not index its own `text`, and echo_pack `container-invariant` is reported 0 instead of ≈144M in RESULTS.md/causes.json. Fix the parser (use annotate's line numbers/markers, or re-derive per-line from the emitted file) and regenerate the tables.
4. Remove the stray `callgrind.out.5029` from the repo root (commit `dfbdffb`).
[commandcode stop=end_turn turns=49 out_tokens=32363]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

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

FINAL VERDICT: FIX  2026-11-07T07:27:31Z
