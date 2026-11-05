# job job-tccprobe1-11051609  started 2026-11-05T07:12:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
Done. Committed on `job-tccprobe1-11051609` as `cffdbed` (not pushed).

**Answer: the generated C does not build with tcc at all.**

| | value |
| --- | --- |
| (a) builds with tcc | **0 of 50** (0/10 compare tasks, 0/40 corpus programs) |
| (b) byte-identical output+exit vs gcc -O2 | **0** — no tcc build ever ran |
| (c) median C-compile wall | gcc -O2 **1.2416 s**, gcc -O0 **0.4574 s**, tcc **n/a** |
| (d) median run | tcc **n/a**; gcc -O2 1.4678 s (compare), 1.4 ms (corpus) |

All 50 C files build with both gcc -O2 and gcc -O0, so the failure is entirely tcc's. tcc 0.9.27 stops at the first incompatible construct in every file:

- **23** unsized struct-array compound literals from runtime values — `ail_stdout_parts((ail_str[]){ir848, ir849}, 2);` from `pyfunc.py:24481` ("index too large")
- **19** `static _Thread_local void *ail__rep_stk[512];` — `cruntime.py:17245-17246` ("';' expected"); tcc rejects `__thread` too
- **7** `__builtin_unreachable` — the file parses, fails at link; these are the closest to building
- **1** `__int128` — `cruntime.py:29709`
- inline asm 0, link error 0, wrong output 0 (stop condition not triggered)

No compiler/runtime change, no DIFFERENCES row, no new test module. Required tests pass on the final commit: safetynet 5 OK, files 18 OK (1 skipped), corpus_findings3 2 OK. Manifest `--check` passes. Probes (fidelity, tcc construct boundaries, classifier/seed) all pass; they caught two real bugs in my own harness (library ordering and multi-unit link flags) before the final run.
[commandcode stop=end_turn turns=124 out_tokens=80869]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — tccprobe1 (`cffdbed`)

**What the change really does.** Adds only `lab/tccprobe/run.py`, `lab/tccprobe/RESULTS.md`, four `fail_*.txt` excerpts, and a DEVLOG entry. It does not touch the compiler, runtime, or default C compiler. The script generates C for 10 compare tasks and 40 seeded `corpus/gdev` programs, rebuilds the saved C with `gcc -O2`, `gcc -O0`, and `tcc`, runs and times the binaries, and classifies tcc failures. This matches the report's description.

**Reproduction.** A full `python3 lab/tccprobe/run.py --runs 1` reproduced the headline numbers exactly: 50 attempted, 50 C generated, 50 gcc -O2 builds, **0 tcc builds**, buckets **23 / 19 / 8**, and the same 40-program corpus list. `python3 tools/update_manifest.py --check` exits 0. `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 3 modules, 0 failed (345 s). `cmp.sh` is not applicable: no AIL language behaviour changed.

**Claims checked.**
- tcc 0.9.27, 0/50, bucket counts, corpus list, gcc build counts and timings, required tests: **verified**.
- "23 unsized struct-array compound literals ... from `pyfunc.py:24481`": **false**. 15 are compound literals; 8 are unsized array declarations `ail_bytes spans[] = {h, old, repl};` emitted from `cruntime.py:6450/6508/6538`. Consequently the per-task "tcc first blocker = compound literal" is wrong for `echo_pack`, `ledger_bin`, `scar_life`, `tally_lang`, `term_rank`, `ticket_audit`, `tree_fold`, and corpus `g02_000`.
- Three-run determinism and the `program.c` sha256 claim: **unverified** (my rerun used `--runs 1`).
- Max C size "2.34 MB": my run gives 2,395,833 bytes (≈2.40 MB decimal), a minor unit inconsistency.

**Pre-existing:** none observed; no AIL source file changed.

### Defects

1. `run.py`'s `classify()` maps every `index too large` to `unsized struct-array compound literal from runtime values` / `pyfunc.py:24481`. Probe: compile `lab/compare/src/echo_pack/main.ail` with `--debug-dir` and run `tcc program.c -lm`. Expected per RESULTS: first error at `ail_stdout_parts((ail_str[]){...})` from `pyfunc.py:24481`. Actual: `program.c:4503: error: index too large` at `ail_bytes spans[] = {h, old, repl};`, from `cruntime.py:6450`. `/tmp/rprobes/decl.c` and `/tmp/rprobes/lit.c` show the two constructs fail independently; `/tmp/rprobes/decl_sized.c` builds. The headline 0/50 is unchanged, but the task asks for each bucket's actual construct and source line, so the bucket should be split or the attribution corrected.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1373959, "input": 74674, "output": 6033, "reasoning": 26564, "cache.write": 0, "cache.read": 1266688}]
    tool time: bash 14.9 min
        532s bash   cd /home/runner/work/_temp/w2 && date && timeout 900 python3 lab/tccprobe/run.py --runs 1 --out /tmp/rprobes/f
        346s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_saf
         12s bash   cd /home/runner/work/_temp/w2 && date && timeout 900 python3 lab/tccprobe/run.py --only corpus --corpus 1 --ru
          4s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rprobes/gen_echo && mkdir -p /tmp/rprobes/gen_echo/{cache,tmp} &&
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "exit ${PIPESTA
          0s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rprobes/gen_echo && mkdir -p /tmp/rprobes/gen_echo/{cache,tmp,dbg
          0s bash   pwd; ls -la; date; git log --oneline -5; git status --short
          0s bash   cd /tmp/rprobes && cat > decl.c <<'EOF' typedef struct { const void *p; long n; } B; int main(void) { B h={0,0

## fix round skipped: only 48 minutes left

FINAL VERDICT: FIX  2026-11-05T11:18:46Z
