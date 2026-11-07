Lane: arena

> Re-run of arena1s3 (FINAL VERDICT: ERROR  2026-11-03T15:00:00Z). This is a roadmap job (docs/ROADMAP.md); check the previous run's branch and log first and continue from what it got right.

**arena1 step 3 of 5: reserve the known bound before append loops (tree_fold RSS → ≤ 380 MB).**
The design is in `arena1-design.md` (appendix below)
(see row 9 of the attribution). Base: integ with steps 1–2 merged, or stacked on one unmerged PR (2 deep at most).

**The number to move.** tree_fold peak RSS on the laptop, N = 3M, default glibc, median of 3: from the step-2 value
(about 410) to **≤ 380 MB**. A hand edit of `rebuild` alone reached 375. Applying the rule to `compact` and `do_fold`
as well should take the prune and fold phases below that too.

**What is wrong.** `rebuild`, `compact` and `do_fold` append once per iteration of `for k in range(n)` to fresh
`list[int]` and `list[str]` locals. Each list grows by `realloc` doubling. Below 32 MB, glibc serves these from the brk
heap: after the first large free its mmap threshold rises to 32 MB. Each doubling leaves a freed hole that stays
resident, which costs 39–46 MB at N = 3M. This is heap retention, not live data. A fixed mmap threshold removes it too,
but costs +15% wall (re-faulting), so it is rejected. Reserving up front removes the holes and is faster.

**Change** (AIL_CURRENT/python/pkg-v12/pyfunc.py):

1. In the `for` lowering (`_for`, `_for_core`, `_for_inner_impl`, lines 25864–26348), take the loops of the form
   `for v in range(a, b)`, `for v in range(n)` or `for v in xs` (a list) whose body appends to a function-local
   `list[int]`, `list[float]`, `list[str]` or bytes-builder local at most once per iteration on every path. Such an
   append may sit under an `if`, but not inside an inner loop.
2. For those loops, emit before the loop: `ail_list_reserve(&x, min(trip, 4194304))`, or `ail_flist_`/`ail_slist_`
   reserve, each with `extra` = the remaining room needed.
   - trip = `b - a` clamped at 0, or `xs.n`.
   - The cap is the same constant `ail_slist_reserve` already uses for comprehensions.
   - Only reserve when the bound expression is pure: names, int constants, `len()` of a local or field.
   - Never reserve for a list that is iterated or indexed by the same loop's body before the append.
3. No runtime change is needed; `ail_list_reserve` and `ail_slist_reserve` exist.

**Tests to add** (tests.d module; output against CPython, and grep the generated C):

- Unconditional and conditional appends in `range(n)` loops get a reserve.
- `break` after one iteration on `range(10**12)`: no OOM, same output. The cap makes this work.
- `range(a, b)` with `b < a`, and with negative bounds.
- A loop whose bound is a call with side effects: no reserve.
- Two appends to the same list per iteration: no reserve.
- An append inside an inner loop: no reserve.
- Iterating `xs` while appending to `xs`: no reserve, same output.
- Run with AIL_UNIFIED_FORCE=1.

**Proof:**

- identical output on all 10 lab/compare tasks (all cases) and on lab/corpus;
- no path flips;
- ASan and UBSan with no new reports;
- par_check `-j 2`, then all 20 shards green;
- run tools/rss_phases.py on tree_fold (N = 1M and 3M) and on echo_pack and ledger_bin, and report peak RSS, wall
  (median of 5) and faults for all 10 tasks before and after;
- after landing, run compare-lab on CI for all 10 tasks and record tree_fold against C.

**Stop rule:**

- Any output or path difference, or any sanitizer report: stop.
- tree_fold above 380 MB, any task's RSS up more than 2%, or wall up beyond noise: do not land.
- If CI shows steps 1–3 moving tree_fold by less than 15% in total, report and stop the arena1 line (see design §5).
- Stop at 2 hours.

Commit and push after each sub-step.


## Appendix (files from the design session, copied here because the runner cannot read them)

### arena1-design.md

````
# arena1 design: cut tree_fold's peak RSS (replaces the code-blind plan in arena1.md)

Follow C:\Users\bluec\ail-work\agent-brief-rules.md. Base: integ 4f1245b1 (read-only worktree
/home/bluec/pub/wt-arena-design). All numbers below were measured on the laptop (WSL Ubuntu 24.04, glibc 2.39,
gcc 13, THP `madvise`), under `ulimit -v 1500000`, on the tree_fold perf input regenerated with
`gen.random_tree(random.Random(1), N, chain=0.35)` plus the 17 perf ops. RSS is `/usr/bin/time -f %M` (KiB, quoted
here in MB = KiB/1000). Every hand-edited build printed byte-identical output to the C program.

## 0. Headline

| | AIL | C | ratio |
|---|---:|---:|---:|
| laptop, N = 3M, peak RSS | 477.7 MB | 198.1 MB | 2.41× |
| CI (BEAT_C.md D), N = 3M | 602.8 MiB | 193.5 MiB | 3.1× |
| laptop, N = 1M | 173.0 MB | 67.3 MB | 2.57× |

The CI number is higher than the laptop for the same program. The CI runner was not re-measured here, so S1 starts by
recording the integ baseline with compare-lab. Every step judges itself on the laptop number and then on CI.

**The classic candidates do not apply.** tree_fold builds on the typed path. Every `list[int]` is a flat `int64_t`
array, and the `list[str]` struct field is already a dense packed list (`ail_pslist`: 8 B of offset per element plus
the text). Only one struct object exists (`T`). After the parse, AIL's RSS equals C's: 133.1 MB against 133.2 MB at N
= 3M. **The whole gap appears after the parse**, in buffers that are copied, kept alive too long, or left as heap
holes.

## 1. Where the bytes come from

### 1.1 Phase picture (N = 3M, peak RSS after running the first k ops)

| prefix ends with | AIL MB | C MB |
|---|---:|---:|
| parse only | 133.1 | 133.2 |
| `stats` | 156.6 | 133.5 |
| `total` | 180.0 | 133.5 |
| first `sort` | **474.7** | 168.4 |
| … `fold` … `print` (all 17) | 475–479 | 168–198 |

Each op run alone on the 3M tree gives: sort 431, mirror 408, fold 365, prune 361, cut 337 and print 188 (C: 168, 133,
141, 168, 133 and 161). The run's peak is the first `sort` (`do_sort` → `rebuild`). mirror, fold and prune are close
behind, and they all share the rebuild-the-columns pattern.

### 1.2 Attribution at the peak (N = 3M, end of the first sort)

The sources are an LD_PRELOAD heap tracker (`arena1-heapsnap.c`: live bytes by call stack at the live-byte peak), a
build of the generated C with `-g`, and the generated code read by hand. "Touched" means pages actually written; the
2× growth slack of mmapped blocks is never touched.

| # | what | B/node | MB touched | C equivalent | evidence |
|---|---|---:|---:|---|---|
| 1 | parsed tree `T` (names: `e` 8 + text 3.6; `w`, `dep`, `par`: 3×8) | 35.6 | 107 | 32 B/node (96 MB) | tracker; parse-only RSS equal to C |
| 2 | input buffer `data` | 9.3 | 28 | same | tracker |
| 3 | **dead temps in `main`**: `stats`' `cc = [0]*n` (cleared, never freed: hoisted local) and `total`'s `for x in t.w` snapshot `v__t94` (kept until `main` returns) | 16 | 48 | 0 | tracker sites py_main:8706 and the snapshot; phase table +23.5 MB each |
| 4 | **sort: `let nm = t.nm` snapshot** (`ail_pslist_snapshot`: a 24 B `ail_str` spine plus a text copy) | 27.6 | 83 | 0 | tracker `ail_pslist_snapshot` 72+11 MB |
| 5 | sort: str key column `_ail_sk1_c2` (24 B `ail_str` views) + `pre` 8 B | 32 | 96 | 0 | `ail_slist_reserve` 72 MB; `ail_keysort_perm` |
| 6 | sort: int key columns c0, c1 + `idx`, `cs`, `sub` + keysort perm/buf | 40–56 | 120–168 | ~20 B/node (int32 `ord`, `Pr`) | tracker |
| 7 | **rebuild: local `nm: list[str]` spine** (`ail_slist`, 24 B/element, grown by doubling) | 24 | 72 (100 requested) | 0 (C relinks in place) | tracker `ail_slist_push` rebuild:7701 |
| 8 | rebuild: new `w`/`dep`/`par` + `ord`, `ni` (+ caller's `idx`, `cs`) | 40 (+16) | 120 (+48) | in place | tracker |
| 9 | **glibc heap retention**: `realloc` doubling of 8–32 MB lists inside the brk heap (the dynamic mmap threshold rises to 32 MB after the first large free) leaves holes that stay resident | 17–23 | 50–68 | small | fixed `mmap_threshold`: −50 MB; exact reserve before append loops: −39…−46 MB (§3) |

Rows 4–5 and 7–8 are not all live at once. The sort has three near-equal sub-peaks: building the c2 column (rows
1–6, about 434 MB live), keysort (about 423 MB) and the end of rebuild (about 423 MB). The tracker's sum of 386 MB
(with a fixed threshold) matched the measured 383 MB. **This is why one fix alone barely moves the peak.**

**Rows priced at about zero** (measured, not assumed):

| candidate | share at peak | why |
|---|---:|---|
| smaller object header / refcount word | < 0.01% | one struct object (`ail_obj_header` 8 B) |
| unboxed ints in containers | 0 | already unboxed `int64_t` arrays on the typed path |
| size-class pools / free lists | < 0.3% | live small allocations at the sort peak are under 1 MB; the 1.16M small allocations per 1M nodes are short-lived `str(int)` for print. Emulated stack buffers for them: 0 MB change |
| tighter growth factor | 0 direct | 75 MB requested but never touched at the peak (mmapped) = 0 RSS. Its real cost is row 9 (holes), which exact reservation fixes better |
| THP `madvise` hint | 0.6% | build without the hint: −3 MB |
| regions with escape analysis | ≈ 0 | regions bulk-free small objects; the peak is a few dozen large flat buffers that a liveness rule can free or avoid |

### 1.3 Time side (for the speed-claims record)

The laptop splits AIL N = 3M into wall 1.52–1.68 s, of which **sys is 0.63–0.75 s**, and **226k minor faults**. C
takes wall 0.71 s, sys 0.13 s and 49k faults. Page faults on freshly touched buffers are about 39% of AIL's wall here.
That share is the measured basis for "allocation is ~35%" in BEAT_C.md. Every byte not touched also saves faults, so
the fixes below are expected to be neutral or faster, never slower. The fixed-mmap-threshold variant shows the
opposite case (§2).

## 2. Priced candidates (bound = what the full-run peak becomes)

The peak is the maximum over phases, so a fix is priced by the next-highest phase after it. Achieved values come from
hand edits of the generated `program.c` that emulate each fix. These are not projections: all ran on N = 3M, default
glibc, with output identical to C.

| step | candidate | removes at peak | bound (projected) | achieved (emulated) | wall (noisy) |
|---|---|---|---|---|---|
| — | baseline | — | — | 477.7 | 1.52–1.68 |
| S1 | free dead loop-body list locals and loop snapshot temps at block end | row 3: 48 MB | ≤ 431 (the single-sort peak) | **441** (−7.6%) | 1.49–1.54 |
| S2 | read-only field alias: `let x = o.f` with no copy when provably unchanged | row 4: 83 MB (c2-build sub-peak) | max(other sub-peaks) ≈ 423 + slack | **410** (−14% cum.) | 1.39–1.49 |
| S3 | exact reservation before append loops with a known trip-count bound | row 9 (holes) at rebuild/compact/fold ends | sort phase ≈ 368 | **375** with rebuild only (−21.5% cum.); prune and fold become the peak at ~370 until compact/fold also reserve | 1.54–1.57 |
| S4 | packed local `list[str]` (dense `ail_pslist` local), moved into the field instead of copied | row 7: 72 → 35 MB; also the `pslist_assign` copy and fold's per-name `ail_bl_copy` into the sarena | sort phase ≈ 338 (fixed-threshold model) | sort phase **332** (rebuild only, with S3); full run 384 because prune and fold were not yet converted | 1.37–1.55 |
| — | indirect str sort key (key kind "element of a str list, indexed by an int column") | row 5: 72 MB at keysort | ≤ 1% unless keysort is the top sub-peak | 409 vs 410; 371 vs 375 | 1.31–1.41 |
| — | fixed `M_MMAP_THRESHOLD` (mallopt or tunable) | row 9: 50–68 MB | −10…−16% | 427 (baseline), 358 (with S1–S4) | **+15%** (sys 0.63 → 1.0 s: 359k faults) |
| S5 (optional) | hand an owned list local to a callee as its last use (`rebuild(t, idx, cs)`), so the callee frees it at its own last use | row 8: 48 MB at rebuild end | ≈ 290–310 live | not emulated | — |
| — | free `data` after the parse | row 2: 28 MB | — | — | rejected: `sargs`/`kw` are views into `data` |

**Assumed fraction against achieved.** Each emulated step realised between 60% and 100% of its removal bound on the
phase it targets. The full-run peak moves less, because another phase or heap holes take over. That is the reason for
the order below.

## 3. Chosen fix

**S1 + S2 + S3, then S4.** These are four liveness and representation rules of the general compiler. None of them is a
region allocator.

- S1 and S2 are cheap and measured: −14% together.
- S3 is the surprise. glibc's realloc doubling of lists below 32 MB leaves resident holes, and reserving the known
  bound before an append loop removes them. With S1 and S2 it measured −21.5% on its own at the sort phase.
- S4 takes the sort phase down to 332. Once S3 is applied to compact and do_fold as well, the projected full-run peak
  is **about 335–345 MB, −28…−30% against 477.7** (2.41× → about 1.7× C).
- S5 is a conditional extra (−48 MB at the rebuild end) if the full-run peak after S4 is still the rebuild end and the
  CI gain is under 25%.

**Rejected:**

- Fixed mmap threshold: +15% wall on the laptop. A memory-versus-speed trade like this needs the owner.
- Indirect str key column: ≤ 1% after S2 and S3. Revisit if keysort becomes the top sub-peak after S4.
- Header, pools, unboxing and regions: about 0 share (§1.2).

The floor that remains after S4/S5 is in the program and the data model, not in the runtime. The 8-byte ints
(int64 semantics) make every temporary 2× the size of C's int32. The source algorithm rebuilds four columns, where the
C version relinks in place. The live set at the end of rebuild after S4 is
135 (tree + input) + 96 (`idx`, `cs`, `ord`, `ni`) + 35 + 72 = 338 MB.

## 4. Steps, code areas, proofs

All code is in AIL_CURRENT/python/pkg-v12/pyfunc.py (the typed path that compiles tree_fold), with runtime C in
cruntime.py. Line numbers are at 4f1245b1.

| step | file : function | change |
|---|---|---|
| S1 | pyfunc.py `_loop_local_release_points` (≈20150), `_loop_local_releases` (≈20200), `_last_use_frees` (≈20215), `_for` (≈25864) / `_expr` field-snapshot branch (≈13372) | generalise loop-local release from struct kinds to LIST/FLIST/SLIST, and from "first mention is a top-level statement of the loop body" to "every mention is inside one block nested in the loop": free at the end of that block. Free the `_numeric_snapshot`/`_slist_snapshot` temp a `for` loop iterates right after the loop |
| S2 | new AST pass (e.g. pyfunc.py near `_mark_borrowed_aliases` ≈28906, run before `sortkeys.rewrite` in `to_c` ≈35462/35606) | rewrite `x = o.f` (`list[int]`/`list[float]`/`list[str]` field) to read `o.f` directly over x's live range, when that range has no store to any attribute `.f`, no rebinding of `o` or `x`, no mutation of `x` or `o.f`, no `del`, no unsafe call (`_borrow_call_safe`), no escape of `x` (return, store, alias, user-call argument), and no lambda other than a sort `key=` |
| S3 | pyfunc.py `_for` / `_for_core` / `_for_inner_impl` (≈25864–26348) plus the append emitters (`ail_list_push` ≈18718, `ail_slist_push`, `ail_sfield_append`) | before a `for v in range(a, b)` / `for v in xs` loop whose body appends to a local list at most once per iteration, reserve min(trip count, 4194304) elements (the same cap `ail_slist_reserve` already uses for comprehensions) |
| S4 | cruntime.py near `ail_pslist_assign` (≈ generated line 4993) gets new `ail_pslist_move`; pyfunc.py local kind selection + `ail_obj_field_slist` emission + `nm.append(builder)` (`ail_bl_copy` → builder view) | a local `list[str]` whose only uses are `.append`, `len()` and one final whole store into a `list[str]` field becomes a dense `ail_pslist` local, and the store moves it |
| S5 | pyfunc.py call/param lowering (`_bind_call_args`, function signature emission) | owned-argument variant for a list parameter that is never stored or returned, used when every call site passes a local at its last use |

**Correctness risks and proofs (every step):**

- **S1, early free.** A freed buffer that is read again would be a use-after-free. The rule only fires when every
  mention of the name is inside one block, the first is a plain fresh assignment, nothing captures it, and the free
  zeroes the struct. `break`/`continue` paths keep today's behaviour: the buffer is freed later at clear or return,
  never twice.
- **S2, alias elision.** The risk is a behaviour change when the field changes during the range. The conditions are
  syntactic and whole-range, and any doubt keeps the copy. The pass runs before the sortkeys rewrite. If a rewritten
  function does not build on the typed path, it is rebuilt without the rewrite (keep the old route).
- **S3, reservation.** The risks are capacity only: OOM on a huge `range` that breaks early (hence the cap), and a
  reserve whose size expression has side effects (only reserve from pure `len()`, names and ints).
- **S4, packed local.** A view of a packed element dies on the next append; hence the eligibility rule: no element
  reads at all. The move frees the old field after the new one is in place. A local that is used after the store keeps
  the copy.
- **Proof per step:**
  - byte-identical stdout and exit code on all 10 lab/compare tasks (perf plus all public and hidden cases via
    run_task.py) and on lab/corpus (`check.py`, default path and `AIL_IR=1`) against CPython;
  - the typed or general path of every compare task and corpus program unchanged;
  - the generated C of the other nine compare tasks unchanged, or each diff explained;
  - the full suite via par_check at `-j 2`, plus all 20 CI shards;
  - ASan and UBSan builds of the 10 tasks on their public and hidden cases and on lab/corpus, with no new reports;
  - new negative tests for every "must not fire" case, each compared with CPython.

## 5. What makes us stop

- Any output difference, any typed→general flip, or any new ASan/UBSan report: stop that step and do not land it.
- A step that does not reach its own target on the laptop (default glibc, N = 3M, median of 3): report, do not land.
- Any compare task whose peak RSS rises by more than 2%, or whose wall rises beyond noise, on CI compare-lab after
  landing: revert the step.
- If S1–S3 together move CI tree_fold peak RSS by less than 15% (the laptop says about 22%): stop and find out why CI
  differs (glibc tuning, THP) before S4.
- After S4: if the CI peak is down by at least 25%, stop (S5 is not needed). If it is down by less than 25% and the
  peak is the rebuild end, run S5. Otherwise stop and write the residual attribution.

## Appendix: measurement recipe (laptop, under the cap)

    ulimit -v 1500000
    python3 -B AIL_CURRENT/ailc.py lab/compare/src/tree_fold/main.ail -o /tmp/tf_ail --debug-dir /tmp/tfdbg
    gcc -O2 -std=c11 -o /tmp/tf_c lab/compare/src/tree_fold/main.c -lm
    # input: gen.random_tree(random.Random(1), 3000000, chain=0.35) + the 17 perf ops (see gen.py `cases`)
    /usr/bin/time -f '%M KiB %e s sys %S faults %R' /tmp/tf_ail < in3m.txt > out.txt
    GLIBC_TUNABLES=glibc.malloc.mmap_threshold=131072 ...   # retention-free view (diagnosis only)

Phase-prefix script: `arena1-phases.sh`. Heap tracker: `arena1-heapsnap.c` (build with
`gcc -O2 -shared -fPIC -ldl`, run with `LD_PRELOAD`, map the stacks with `addr2line` on a `-g -no-pie` build of
`program.c`). N = 3M peaks at about 480 MB; keep N = 1M (about 175 MB) for quick loops.

````

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
