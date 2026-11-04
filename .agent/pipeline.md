# job job-rbguide1-11042159  started 2026-11-04T13:00:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Re-applied the guide on top of this tree and committed as `54ae252a`.

**What changed**
- `docs/guide/` (README + 4 chapters, 43 samples), `AIL_CURRENT/test_ail_guide.py`, `tests.d/test_ail_guide.txt`, and the `GH_MODELS_TOKEN`/`ghm.key` removal in `.github/workflows/agent-worker.yml`. The workflow matched the job's base, so the patch applied cleanly; `manifest.d` was regenerated.
- `tools/diff_ids.py` is absent on this tree (noted in prior DEVLOGs); `update_manifest.py` and `--check` both pass. No compiler/runtime change, so no DIFFERENCES row.
- DEVLOG entry added at top.

**Probes** (`/tmp/probes/`, 22 total)
- 14 run through `cmp.sh` match CPython stdout/exit on both the default and general builds: typed numbers, containers (empty/negative/aliased lists), dataclass fields, text/bytes boundaries, files/argv, errors (try/else/finally, KeyError/ZeroDivisionError/ValueError/custom class), `sys.exit(3)`, math, re, json, collections, heapq/bisect, statistics, `ail_ffi` cbrt.
- 4 int64-overflow provenances (argument, list item, attribute, dict value) stop with the documented `OverflowError: integer overflow in + ...`, exit 1.
- 4 direct compile checks: `eval` refused exit 3, `numpy` exit 2, general-path note present with `--strict` refusal exit 3, `--exact-int` matches CPython.
- One combined-modules probe exceeded a 240 s compile, so I split it per module; those all pass.

**Tests on the final commit**
- 70 tests: `test_ail_guide` (45) + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` (25 together, 1 skip) — OK.
- `update_manifest.py --check`: exit 0. Working tree clean except the pre-existing untracked `.agent/pipeline.md`.
[commandcode stop=end_turn turns=38 out_tokens=18131]

## review 0
[model commandcode/deepseek-v4.1-flash]
I've reviewed the re-application, compared it byte-for-byte with the accepted job, and run the targeted tests plus my own probes. Here is the report.

## What the change really does

Documentation + test only: adds `docs/guide/` (README + 4 chapters, 43 samples), `AIL_CURRENT/test_ail_guide.py` (builds/runs every sample, compares stdout+exit with CPython), registers `tests.d/test_ail_guide.txt`, removes the `GH_MODELS_TOKEN`/`ghm.key` plumbing from `.github/workflows/agent-worker.yml`, adds a DEVLOG entry, regenerates `manifest.d/51.txt`+`94.txt`. No compiler, runtime, or I/O change. This matches the report.

## Fidelity to the accepted change

All 8 changed content files (`docs/guide/*.md`, `test_ail_guide.py`, `tests.d/test_ail_guide.txt`, `agent-worker.yml`) are byte-identical to `b796a01..job-guide1-11041926`; both `manifest.d` files are identical too. The only extra file is the required DEVLOG entry. Manifest `--check` exits 0.

## Tests on HEAD (`-j 2`)

`test_ail_guide` + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3`: 4/4 OK, 0 failed (902 s). `test_ail_guide` alone: `Ran 45 tests ... OK`, `guide samples: 43`.

## My probes (`/tmp/rprobes/`, HEAD vs `/tmp/rbase` = `work`)

| probe | result |
|---|---|
| p1 provenance overflow (list item, attribute, dict value) | documented `OverflowError ... --exact-int gives exact ints`, exit 1; identical on base |
| p2 typed list/floor division (feature not used) | same stdout/exit as CPython, both builds |
| p3 uncaught ZeroDivisionError | same stdout, exit 1 as CPython |
| p4 argv IndexError (no args) | same stdout, exit 1 as CPython |
| p5 list/bytes slice then mutate source | same stdout as CPython |

Generated C for p2 is identical HEAD vs base after normalizing the temp-dir path in `AIL_DBG_SITE`.

## Report claims

- 43 samples / 45 guide tests / docs set — **verified**
- workflow patch applied cleanly, identical to accepted — **verified**
- `tools/diff_ids.py` absent — **verified**
- no DIFFERENCES row needed (no compiler/runtime change) — **verified**
- `update_manifest.py --check` passes — **verified**
- 4 modules pass — **verified**
- 22 probes — **partially verified**: 22 `p_*.py` exist in `/tmp/probes`; I did not re-run the worker's probes. Note the DEVLOG entry says "Probes (17 ...)", which contradicts the report's 22.

Not checked: individual test counts of the three non-guide modules; the worker's probe outputs.

**Pre-existing:** none affecting the compiler. `p1` divergence from CPython is the documented int64-stop behaviour and is identical on the base. `.agent/pipeline.sh` still mentions `ghm.key` (dead branch, outside the diff scope and present in the accepted change).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=33 out_tokens=12922]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## suite fix skipped: only 127 minutes left

FINAL VERDICT: FIX  2026-11-04T15:47:06Z
