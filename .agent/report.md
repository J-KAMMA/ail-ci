# job job-arena1s4-11040050  started 2026-11-03T15:51:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `2033134` on `job-arena1s4-11040050`.

- **Implemented S4:** packed `ail_pslist` locals for append-only `list[str]`; `ail_pslist_move`, `ail_pslist_reserve`, packed pushes, field store move, unwind/free paths.
- **tree_fold N=3M:** 440,188 → 414,220 KiB peak RSS, wall 1.75 → 1.42 s, minor faults 194,030 → 135,599. Sort phase 429.8 → 404.5 MiB.
- **Correctness:** all 10 compare tasks and all public+hidden cases match, all stay typed. Targeted + required modules pass under `par_check -j 2`; S4 module includes ASan/UBSan.
- **Probe:** `/tmp/probes/arena1s4.py` matches CPython on default and `AIL_UNIFIED_FORCE=1`.
- **Blocker:** still 405 MiB, above the 350 MB bar, so I did not merge/land it. Generated `do_sort` still contains S2's `ail_slist_snapshot` for `let nm = t.nm` (~83 MB); despite the brief saying steps 1–3 are merged, S2 is absent here. S5 would not remove that snapshot or the str key column.
- **Not verified:** all 10 tasks under ASan/UBSan, and CI compare-lab after landing. Details in `docs/design/ARENA1.md`.

Next decision needed: add/fix S2 in the base, or proceed with S5 while accepting the target will likely remain unmet.
[cost $0.0000, opencode tokens {"total": 17873230, "input": 544475, "output": 42669, "reasoning": 47942, "cache.write": 0, "cache.read": 17238144}]
    tool time: bash 52.4 min, edit 0.0 min, write 0.0 min
        646s bash   for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit 
        646s bash   mkdir -p /tmp/allnew /tmp/allbase; for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life
        418s bash   python3 tools/par_check.py -j 2 test_ail_ir_s3 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
        286s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -80
        272s bash   for i in 1 2 3; do python3 lab/compare/run_task.py --task berth_sim --langs ail --out /tmp/berth-new-$i.json >
        267s bash   for i in 1 2 3; do python3 lab/compare/run_task.py --task berth_sim --langs ail --out /tmp/berth-base-$i.json 
         91s bash   python3 tools/rss_phases.py --n 3000000 /tmp/tfbasebin /tmp/tf/tf 2>&1 | tail -60
         89s bash   python3 tools/rss_phases.py --n 3000000 /tmp/tf/tf /tmp/tfbasebin 2>&1 | tail -80

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough. Final report:

## What the diff really does
It adds `ail_pslist_move`/`ail_pslist_reserve` to the runtime and, in the typed path, classifies a `list[str]` local as a dense `ail_pslist` when its only uses are `= []`, `.append(v)`, `len(x)` and one textual-last `o.f = x`; appends become `ail_pslist_push`, the store becomes `ail_pslist_move` (which zeroes the local), and reserves/frees follow. That matches the report's description. The eligibility test is textual: "last mention" is source position, not "executed once".

## Claims
- Runtime + emitter changes, packed push/move/free, reserve hint `o.f.tn`: **verified** (diff + generated C, e.g. `ail_pslist_reserve(&v_nm, ..., (v_t)->f_nm.tn)` in tree_fold).
- "S2 is absent here; `do_sort` still has `ail_slist_snapshot`": **verified** — base `/tmp/base` (06de59e) and HEAD both have 4 `ail_slist_snapshot` call sites and no `ail_pslist_move` in base; base already has `ail_slist_reserve`.
- Targeted modules pass at `-j 2`: **verified** — `test_ail_arena1s4`, `test_ail_safetynet`: 2 modules, 0 failed.
- RSS/wall/faults numbers (440,188→414,220 KiB etc.), "all 10 compare tasks match", ASan on all tasks: **unverified** (too large to rerun). Two non-feature tasks (`berth_sim`, `ledger_bin`) generated **byte-identical C** vs base; tree_fold compiles.
- Target ≤350 MB: **false by the worker's own numbers** (405 MiB), and it was correctly not landed.

## Defect
1. **A packed local stored inside a loop is zeroed after the first move, so later iterations write an empty list.** The marker accepts the store as the local's last *textual* mention even when that store executes many times.
   Probe `/tmp/rprobes/p2_loopstore2.py`:
   ```python
   def build(o: T, k: int) -> None:
       nm: list[str] = []
       nm.append("a")
       for i in range(k):
           o.nm = nm
   build(t, 3); print(len(t.nm)); print(",".join(t.nm))
   ```
   CPython / base: `1` then `a`. HEAD default build: `0` then an empty line. Generated C (`/tmp/pd2/program.c`) shows `ail_pslist_move(&v__t2->f_nm, &v_nm)` inside the `for`, so the second and third assignments store the zeroed local. General path (`AIL_UNIFIED_FORCE=1`) and base are correct; only the typed path regresses. The added `test_ail_arena1s4` module has no store-in-loop shape, so it passes. Fix: require the store to be outside any loop or provably executed once (or have the move leave a re-initialised copy when the store can repeat).

## Pre-existing
- `p7_appendresult.py` (`r = nm.append("a")`) fails to compile identically on base (`void value not ignored ... ail_slist_push`), so it is not caused by this change.

## Speed
`g00_032`, `g08_028`, `g25_018` (all `list[str]` gdev programs) take no packed path: generated C is byte-identical to base, so instruction counts are unchanged for code that does not use the feature.

## Probes that matched CPython on both builds
`p3_basic` (rebuild shape), `p4_empty` (empty column), `p5_builder` (builder pushed then mutated), `p6_selfelem` (`nm.append(t.nm[i])` then replace the field), `p8_readafter` (stays `ail_slist`), `p10_values` (list item, dict value, argument, literal), `p11_attr` (attribute, empty string, non-ASCII, source mutated after), `p12_aliasing` (field element pushed, then the field appended to).

## Unverified
tree_fold RSS/wall/fault figures; the 10 compare tasks and their hidden cases; ASan/UBSan on all tasks; the worker's `/tmp/probes/arena1s4.py`.

VERDICT: FIX
1. Loop-carried store miscompiles: `p2_loopstore2.py` expects `1` / `a` (CPython and base) but the default typed build prints `0` / empty, because `ail_pslist_move` zeroes the local on the first iteration while the eligibility rule only requires the store to be the local's last textual mention, not to execute once.

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `2a5543a`.

**Defect:** `_mark_packed_str_lists` accepted `o.f = nm` as the local's "last mention" by source position, so a store inside a `for`/`while` body was packed. `ail_pslist_move` zeroes the local, so iteration 2+ stored an empty column (typed path: `build(t,3)` printed `0`/empty vs CPython `1`/`a`).

**Fix:** a field store with any `for`/`async for`/`while` ancestor now disqualifies the local (stays `ail_slist`). Stores outside loops, including after an append loop, still move. Added `_inside_loop`, a docstring update, and `repeated_store`/`while_store` shapes to `test_ail_arena1s4` with both a CPython comparison and a C-shape assertion (`ail_slist_push`, no `ail_pslist_push`/`move`).

**Verification on final commit:**
- Probe `/tmp/probes/a1s4_loopstore.py` (for-store, while-store, if-inside-loop, append+store in loop, def+store in loop, store after append loop): matches CPython in both builds (`g` and `d`, exit 0, same stdout).
- Generated C: loop stores now `ail_slist_push` + `ail_obj_field_slist`; `outer_store` still `ail_pslist_move`; tree_fold still emits 4 `ail_pslist_move` and the `(v_t)->f_nm.tn` reserve, so the packed feature and its memory win are unchanged.
- Required tests, `-j 2`, final commit: `test_ail_arena1s4` ok, `test_ail_safetynet` ok, `test_ail_files` ok, `test_ail_corpus_findings3` ok — 4 modules, 0 failed (283 s).

Not re-measured: RSS/wall for tree_fold (eligibility for its stores is outside loops, generated C unchanged). Still not landed, per the earlier report's >350 MB result.

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: arena1 S4 (packed `list[str]` locals)

**What the diff really does.** Adds `ail_pslist_move`/`ail_pslist_reserve` to the runtime, `_mark_packed_str_lists` (a `list[str]` local whose only uses are `.append`, `len`, and one whole-field store, the store being its last mention), packed push/len/move/free emission, reserve support for these locals, and — in commit 2a5543a — a rejection of any whole-field store that has a `for`/`async for`/`while` ancestor. Plus the test module, DEVLOG and `docs/design/ARENA1.md`. This matches the report's description.

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both builds unless noted; all in `/tmp/rprobes/`):

| probe | target | result |
|---|---|---|
| r1_basic | packed build with `if`/`continue`/`break`, `while`, annotated local | match |
| r2_loopstore | for/while/if stores | match (program falls back to general path; base identical — pre-existing) |
| r3_exc | raise between appends and store; raise after the move | match |
| r4_builder | builder mutated after push, dict value, non-ASCII, long text | match |
| r5_selfandstay | same-field append, `len` after store, two fields, return | match |
| r6_fielditer | iterate field while packing, empty local into non-empty field, wide-mode field | match |
| r7_reserve | `len` in loop, nested loops, two packed locals | match |
| r8_twopass | post-store `len` (must stay slist) | match |
| r9_nofeature | no feature | C identical except the 2 new unused helpers |
| r10_reserve2 | local-bound reserves, `if`/`continue`/`break`, early return, range steps | match; typed C has `ail_pslist_reserve(..., src->f_nm.tn)` |
| r11_definloop | `nm = []` inside the loop, view-then-move | match |
| r12–r14 init | local in `__init__` | general-path fallback, identical on base (pre-existing) |
| r15_targets | `o.inner.nm = nm`, `objs[0].nm = nm` | match, 2 moves in typed C |
| r16_frame | exception frame holds `ail_pslist`; unwind | match; frame cell + unwind use `ail_pslist_free` |
| r17_repeat | repeated for/while store | HEAD matches; **mid 2033134 prints `A 0` vs CPython `A 1 a`** — report's bug+fix verified; HEAD C has `ail_slist_push`+`ail_obj_field_slist`, no move |
| r18_plainreserve | plain `list[int]`/`list[str]` reserve | generated C byte-identical base vs HEAD |
| r21_comp2 | `len(nm)` in a comprehension, `len(nm)` as loop bound | match; comprehension reads `v_nm.n` |
| r22_sources | append from `list[str]` param element, empty str, str field | match |

**Pre-existing** (fails identically on `/tmp/base`, does not block):
- `r20_comp`/`r23_appendexpr`: `[nm.append(x) for …]` and `y = nm.append(x)` fail the default build with “void value not ignored / invalid use of void expression” because `ail_slist_push` is void too. The `g` build matches CPython on both trees.

**Claims**
- Fix commit and the repeated-store defect: **verified** (r17 at 2033134 vs HEAD).
- `_inside_loop` disqualification: **verified** in code and C.
- “tree_fold still emits 4 `ail_pslist_move`”: **3 call sites** (+1 definition line); intent correct.
- “`(v_t)->f_nm.tn` reserve”: **verified** (2 of 3 sites; fold has hint 0).
- tree_fold generated C unchanged by the fix commit: **verified** — mid and HEAD `program.c` are byte-identical.
- tree_fold output: **verified** on the public case and a 20k-node random tree with all 10 op kinds (base vs HEAD identical).
- Other nine tasks’ C unchanged: **verified** for ledger_bin (0 diff) and ticket_audit (only the 2 new helpers).
- Tests: test_ail_arena1s4 and test_ail_safetynet green (`-j 2`, 2 modules, 0 failed, 175 s); ASan/UBSan test inside the module passed. test_ail_files / test_ail_corpus_findings3 not re-run by me.
- RSS ≤ 350 MB: **not met** (DEVLOG reports 414 MB, not landed), which is what the task's own stop rule prescribes.

**Speed.** gdev programs `g25_032`/`g08_028` compile to byte-identical C on base vs HEAD, so their instruction counts cannot differ; the plain-reserve path is also byte-identical (r18). `perf_event_open` is denied here, so I could not run `tools/icount.c` on tree_fold; its C change only replaces a copy with a move and eliminates builder copies.

**Unverified:** full 10-task/per-case output run, RSS/wall/re-measurement, tree_fold instruction counts, the worker's own `/tmp/probes` files (absent here; reproduced equivalently).

The change is correct for the shapes it claims, and the only failures I found are identical on the base.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T18:53:30Z
