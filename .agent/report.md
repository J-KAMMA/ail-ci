# job job-tccprobe1-11052026  started 2026-11-05T11:27:15Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `7270c92`.

**Defect confirmed and fixed.** On the committed tree, `echo_pack`'s first tcc error is `program.c:4503: ail_bytes spans[] = {h, old, repl};` → now `unsized struct-array variable declaration` (cruntime.py:6450), while `berth_sim` is `6539: ail_stdout_parts((ail_str[]){...})` → `unsized struct-array compound literal` (pyfunc.py:24481). The 23 are 15 literals + 8 declarations; the 8 declaration programs are `echo_pack, ledger_bin, scar_life, tally_lang, term_rank, ticket_audit, tree_fold, g02_000`.

**Other changes:** multi-unit attribution now prefers the file tcc names; a tcc build that runs but differs is labelled `wrong output` (stop condition) instead of a parse failure; `__int128`/builtin excerpts cite their emitter lines. RESULTS.md and the DEVLOG now carry the split attribution and the max C size in exact bytes (2,395,833 for `g13_038`).

**Re-measured, 3 repetitions:** 0/50 tcc builds, buckets 19 `_Thread_local` / 23 unsized aggregates / 8 builtins; medians gcc -O2 **1.2092 s**, gcc -O0 **0.4434 s**, tcc n/a; gcc -O2 runs **1.4422 s** compare / **1.4 ms** corpus. 3-run determinism confirmed 50/50, and the `program.c` sha256 re-verified (`facf9d98…` both ways via a PIPE_CC shim). Corpus list and the 45-candidate selection unchanged.

**Probes:** `tcc_limits.py` 15/15, `measure_logic.py` 11/11, `measure_fidelity.py` 2/2, plus direct tcc runs on the echo/berth C. No `cmp.sh` probe applies (no language/runtime change).

**Tests:** `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 3 modules, 0 failed (335 s). No job-specific test module exists. `python3 tools/update_manifest.py` and `--check` pass.
[commandcode stop=end_turn turns=66 out_tokens=49917]

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review — tccprobe1 (`7270c92`)

**What the change really does.** Only the measurement script and docs change: `classify()` now splits tcc's `index too large` into compound-literal vs unsized-array-declaration by the C line tcc points at, `diagnose()` prefers the translation unit tcc names, a tcc binary that runs but differs is bucketed `wrong output`, plus new emitter citations and a regenerated `fail_3` excerpt. No compiler/runtime/benchmark file is touched (diff touches only `DEVLOG.md` and `lab/tccprobe/*`). This matches the report.

**Defect from review 0 — confirmed fixed.** Real tcc runs on the generated C (`/tmp/rprobes/probe_attr2.py`): `echo_pack` → `program.c:4503 ail_bytes spans[] = {h, old, repl};` → *unsized array declaration*; `berth_sim` → `6539 ail_stdout_parts((ail_str[]){…})` → *compound literal*; `ledger_bin`, `rail_transfer`, `g02_000` also correct. Boundary probes `/tmp/rprobes/{decl,decl_sized,lit,lit_sized}.c`: both unsized forms fail `index too large` independently, both sized forms build.

**Full re-measurement** (`--runs 1`, 9 min): 50 attempted, 0 tcc builds, buckets **19 attribute / 23 other / 8 builtin**; 23 = **15 literals + 8 declarations**; the 8 declarations are exactly `echo_pack, ledger_bin, scar_life, tally_lang, term_rank, ticket_audit, tree_fold, g02_000`; corpus split 19/13/6/1/1; corpus list and `45` candidates identical; C bytes total 23,019,540, max 2,395,833 (`g13_038`), median 329,896.5. Multi-unit `g02_002`/`g13_038` attribute the unit tcc names. `--from-json` regenerated all five excerpts byte-identically (modulo temp paths).

**Claims checked.**
- Split attribution, 8 named declaration programs, per-task first-blocker table, multi-unit attribution, emitter file:line citations, exact max-C bytes, corpus list/45 candidates: **verified**.
- `PIPE_CC` shim sha256 `facf9d98…` for `g01_010`: **verified exactly** (both files identical).
- `wrong output` label: code path correct but **unexercised** (no tcc build ran).
- "Re-measured, 3 repetitions" medians and "3-run determinism 50/50": **unverified** — I ran one repetition; counts reproduce, wall times naturally differ.
- Worker's `/tmp/probes` files (15/15, 11/11, 2/2): **unverified** (not committed); their substance re-verified independently above.
- Tests: `test_ail_safetynet` **verified** (1 module, 0 failed, 191 s). `test_ail_files`/`test_ail_corpus_findings3` not re-run (not added/edited by the change). `update_manifest.py --check` exits 0; no job test module exists.

**Pre-existing:** none (no AIL source or benchmark file changed; `cmp.sh` / `icount` not applicable).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=40 out_tokens=25575]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T13:42:45Z
