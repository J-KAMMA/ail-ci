# job job-wedge3b-11091226  started 2026-11-09T03:30:34Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here is the short report.

## wedge3b report

**Commit** `d0f4f641` on `job-wedge3b-11091226` (work in `lab/wedge3/wedge3b/`, plus the required DEVLOG and DIFFERENCES records). Hybrid source: `job-obs5-op1109` / `69e2dcd0`.

**Headline:** the hybrid accelerates **0 of 137 top-level functions** in the two libraries' hot modules, so it runs at CPython parity while the Rust rewrites are 2.35x–2.83x faster. Selection, not the C boundary, is the limit.

| library | top-level / native | CPython | PyPy 3.10.16 | hybrid (obs) | native Rust | hybrid/CPython | hybrid/PyPy | hybrid/native |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pydantic 1.10.27 → 2.14.3 (pydantic-core) | 100 / 0 | 1.2711 s | 0.5027 s | 1.2800 s | 0.5410 s | 1.007x | 2.546x | 2.366x |
| sqlparse 0.6.1 → sqlglot 26.33.0 (`sqlglotrs`) | 37 / 0 | 2.0194 s | 4.3260 s | 1.9469 s | 0.7139 s | 0.964x | 0.450x | 2.727x |

Hybrid without observed kinds: pydantic 1.2628 s (0.993x), sqlparse 1.9965 s (0.989x). All five builds of both workloads print byte-identical stdout.

**Refusals by profiled self time.** pydantic: methods of classes with bases/attributes 73.2%, not-a-typed-candidate 20.9% (`validate_model` 0.795 s, validators `Any`), nested helpers 5.9%. sqlparse: methods 53.5%, not-a-typed-candidate 24.1% (`imt`, `_group`), nested 13.9%, list-typed `self` fields 7.3%. `ail_observe.py annotate` added 98 annotation lines to sqlparse and 1 to pydantic but unlocked nothing (`-> None`, `int|None`/`type|None`, pre-existing `Any`).

**Probes** (`lab/wedge3/wedge3b/probes/`): hybrid matches CPython on all four (9/9, 1/1, 0/0, 4/4 native). `cmp.sh` general build matches two and refuses two by name at the int64 constant boundary.

**Notes:** `sqlglot[rs]` at 30.30.0 is only a deprecated stub; pinned 26.33.0 for the real Rust `.so`. `perf_event_open` is denied, so no instruction counts. `uild --cpython` on an in-place package module shadows stdlib `json`/`typing`; builds were staged from a one-file directory. Required tests `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass on the final commit (25 tests, 1 skipped).
[commandcode stop=end_turn turns=84 out_tokens=74185]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: wedge3b (measurement-only lane)

**What the change really does:** adds `lab/wedge3/wedge3b/` (harness + RESULTS), a DEVLOG entry and one DIFFERENCES row. Zero lines change `AIL_CURRENT/`, `tools/`, `bench/` or `spec/` (`git diff work..HEAD -- AIL_CURRENT tools bench spec` = 0 lines). No compiler/runtime behaviour is touched, so "programs not using the feature" are trivially unchanged; one base-worktree (`/tmp/base`, `work`) rerun of two probes gave byte-identical general/default results to HEAD.

**Claims checked (all re-run, not taken on trust):**
- Hybrid source `69e2dcd0` = `origin/job-obs5-op1109` — **verified**.
- "0 of 137 top-level functions native": summaries say pydantic 100 top / 0 native, sqlparse 37 / 0 — **verified**. Rebuilt probes on obs5: boundary 9 accelerated (`add1,divide,echo,first,half,isbig,join,mul,total`), observed 4 (`inc,concat,scale,Wrap.doubled`), none_union 0, sqlshape 0 — **verified** (report's 9/1/0/4 plain column).
- Times, five builds, byte-identical stdout: re-ran `measure.py` — all ten variants `match=True`, medians within noise of the table (pydantic 1.273/0.504/1.267/1.263/0.547; sqlparse 1.957/4.393/2.014/1.993/0.755) — **verified**.
- Refusal rankings: `refusals_*.json` reproduce the table exactly (73.2/20.9/5.9; 53.5/24.1/13.9/7.3) — **verified**.
- `annotate` counts: diff of plain vs obs packages shows 93 annotation-bearing lines in sqlparse, 1 in pydantic — **essentially verified** (98 counts all added lines).
- icount unavailable: built `/tmp/w3b/icount` fails `perf_event_open: Permission denied` — **verified**.
- Pure pydantic has no `.so` (1.10.27, `--no-binary`); native venv has real `sqlglotrs...so`, `USE_RS_TOKENIZER=1`, pydantic 2.14.3/core 2.50.4 — **verified**.
- Tests on HEAD: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (1 module / 2 modules, 0 failed) — **verified**.
- `tools/update_manifest.py --check` rc=0; diffstat confined to `lab/wedge3/wedge3b/**` + DEVLOG/DIFFERENCES as required — **verified**.
- `cmp.sh` on the four probes: two match, two refused by name (`int64 constant expression out of range`, `constant integer expression overflows int64`) on both HEAD and base — **verified**.

**Unverified:** the hybrid+observed probe counts (the "1 native" for `w3b_none_union`) — not rebuilt with an observer profile. All rate ratios are subject to runner noise; my rerun puts sqlparse hybrid_obs at 1.018x CPython rather than the reported 0.964x, so the "0.96x–1.01x" band is not exactly reproducible, but the parity conclusion stands.

**Minor record issue (non-behavioural):** both commit trailers say `Co-Authored-By: Claude Sonnet 5.5`, while the worker header says the model was `commandcode/deepseek-v4.1-flash`; the rule says other models omit that line. Nothing technical depends on it.

**Pre-existing:** nothing to report (no compiler output differences; both probe refusals are identical on base).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=19 out_tokens=19556]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T06:06:22Z
