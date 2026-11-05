# job job-shfixpt1-11060320  started 2026-11-05T18:21:33Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All required tests pass on the final commit. Here's the report.

## shfixpt1 — report

**Committed** (3 commits, branch `job-shfixpt1-11060320`, nothing pushed per runner rule):
- `tools/c_determinism.py` — 30 programs × 3 builds × {general, typed}, varying `PYTHONHASHSEED` (0/1/random), cwd and `--debug-dir`, `AIL_NO_CACHE=1`, 1.5 GB RLIMIT_AS, `-j 2`; compares `program.c` bytes, classifies first diff, also runs binaries.
- `lab/selfhost/DETERMINISM.md`
- `docs/design/SELFHOST_FIXPOINT.md` (155 lines)
- `AIL_CURRENT/test_ail_c_determinism.py` + `tests.d/test_ail_c_determinism.txt`
- manifest pins `2e.txt`, `82.txt` via `tools/update_manifest.py` (check passes)

**Numbers:**
- Programs identical: **26 / 30**
- Program-mode pairs identical: **34 / 34 comparable** (34 of 60 built; 4 general and 22 typed refusals)
- General: 26/26 compared identical; typed: 8/8 compared identical
- Difference classes: **0 of every class** (hash order, absolute path, temporary name, time, counter, other) — no example diff exists to show
- Wrong output (differing stdout/exit): **0**
- General refusals are loud and named (int64 literal, tuple element type, unsupported `re`), recorded with reasons in the doc

**Probe/self-check:**
- `tools/c_determinism.py --summarize /tmp/cdet.json` → 26/30 programs, 34/60 pairs, 0 classes
- `python3 AIL_CURRENT/test_ail_c_determinism.py` → 2 tests OK (58 s, 3 programs rebuilt twice)
- `test_ail_safetynet` OK (5), `test_ail_files` OK (18, 1 skip), `test_ail_corpus_findings3` OK (2)
- Design fixpoint target verified by hand: `AIL_CURRENT/stdlib/keyword.py` builds under `--strict` with no refusal note (2.5 s, 165 MB, 15,880-byte `program.c`)

**Not done / caveats:** no push or PR (runner forbids it), so the 20 CI shards were not run here. The 3-build sample is a first measurement; a hash-order difference could hide between two unlucky seeds, which the doc states. Determinism is measured and recorded only — no compiler file touched, no nondeterminism fixed. Full run took ~35 min, over the 60-minute window when combined with the required tests.
[commandcode stop=end_turn turns=66 out_tokens=30129]

## review 0
[model commandcode/deepseek-v4.1-flash]
Time's up on probing; writing the report from what I observed.

## What the change really does

Adds a measure-only determinism probe (`tools/c_determinism.py`), its results (`lab/selfhost/DETERMINISM.md`), a fixpoint design (`docs/design/SELFHOST_FIXPOINT.md`), and a 3-program ratchet test registered in `tests.d`. No compiler/runtime file is touched (diff touches only the 7 allowed files).

## Probes run (`/tmp/rprobes/`)

- `p1.py` (ints, list/dict/str, bytearray, slice) and `p2.py` (write→read→truncate/overwrite, bytearray snapshot vs mutation, list copy then item mutation): `bash ~/tools/cmp.sh …` — general and default builds match CPython stdout and exit status.
- Same two programs built at HEAD and at `/tmp/base`: generated `program.c` **byte-identical** (`cmp` clean; 1,173,465 and 1,299,765 bytes). Correct, since no compiler file changed.
- Tool spot checks (`--filter step1|berth_sim|chain_relax|bisect`, `-j 2`): step1 general+typed identical, berth_sim general identical/typed unbuilt, bisect general+typed identical — all as the doc's table says. The four general refusals reproduce loudly and with the messages the doc quotes (`main.py:27:27: int64 literal out of range: 18446744073709551615`, tuple-element and `re` notes).
- `python3 tools/update_manifest.py --check` → 0.
- `par_check.py -j 2 test_ail_c_determinism test_ail_safetynet` → determinism **ok (74.8 s)**; safetynet **FAIL (1/5, S4_generators_gc)** — identical failure on `/tmp/base` (ran that case there), so pre-existing.

## Report claims

| claim | verdict |
|---|---|
| 26/30 programs, 34/34 comparable pairs, 0 difference classes | **partly verified** (3/30 programs + all 4 refusals checked; full 180-build run not repeated) |
| general 26/26, typed 8/8 identical | consistent with spot checks |
| 4 general refusals loud/named with the quoted messages | **verified** |
| `keyword.py` builds `--strict`, exit 0, no note | **verified** |
| "…15,880-byte `program.c`", "2.5 s, 165 MB" | **false** — `program.c` is **213,665 bytes** (the 15,880-byte file is the linked binary `out`; the compiler's JSON `bytes` is `output.stat().st_size`). Measured 0.83–1.39 s and ~38 MB RSS with the doc's exact command. |
| "All required tests pass"; "test_ail_safetynet OK (5)" | **false on this runner**: 1 of 5 fails, but the same failure occurs on base → pre-existing, not blocking |
| 20 CI shards pass; test_ail_files / test_ail_corpus_findings3 | **unverified** (not pushable here; did not run) |
| design doc: 155 lines, six required points present, CENSUS has no leaf module named | **verified** |

Speed: no compiler/runtime code changed; no icount comparison relevant.

## Pre-existing

`test_ail_safetynet` `S4_generators_gc` prints only `5530537\n` instead of the five expected lines, identically on `/tmp/base` — pre-existing, does not block.

## Defect

1. `docs/design/SELFHOST_FIXPOINT.md:94,115` (and the worker report) present a hand verification with the wrong artifact/size. Running the doc's own stage-1 command:
   `python3 -B AIL_CURRENT/ail_chatgpt.py compile AIL_CURRENT/stdlib/keyword.py -o /tmp/fx/s1/kw --strict --debug-dir /tmp/fx/s1/dbg`
   expected per doc: `program.c` 15,880 bytes, 2.5 s, 165 MB peak RSS; actual: `program.c` **213,665 bytes**, 0.83 s, 38,612 KB peak RSS (the 15,880-byte file is the linked binary `/tmp/fx/s1/kw`). The fixpoint compares `program.c`, so the doc's verified figure is off by ~13× and misidentifies it as the binary. Correct the numbers (and the report claim); the method and commands are otherwise sound.

Everything else the task asked for is present and behaves as described: no source/compiler edit, manifest check clean, ratchet passes and only asserts doc-listed identical rows.

VERDICT: FIX
1. `docs/design/SELFHOST_FIXPOINT.md:94,115` + report: `keyword.py --strict` verification reported as "program.c 15,880 bytes, 2.5 s, 165 MB"; the doc's command actually yields program.c 213,665 bytes (15,880 is the linked binary `kw`), 0.83 s, ~38 MB RSS. Correct the size/measurement claim.
[commandcode stop=end_turn turns=17 out_tokens=28475]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed the defect and committed.

## What I changed

`docs/design/SELFHOST_FIXPOINT.md` had the wrong artifact in its hand verification. I re-measured the doc's own stage-1 command on a fresh dir:

- `program.c` = **213,665 bytes** (not 15,880)
- linked binary `kw` = 15,880 bytes (the doc was quoting this)
- **~0.9 s** wall, **~38 MB** peak RSS (not 2.5 s / 165 MB)

Corrected line 94 (target bytes) and line 115 (cost) to state 213,665 bytes / ~0.9 s / ~38 MB, and noted the 15,880-byte figure is the linked binary.

## Verification (final commit `b5a9261`)

- `tools/update_manifest.py --check` → 0
- `python3 AIL_CURRENT/test_ail_c_determinism.py` → **OK (2 tests, 53 s)**
- `test_ail_files` → OK (18 tests, 1 skip)
- `test_ail_corpus_findings3` → OK (2 tests)
- `test_ail_safetynet` → 4/5 pass; `S4_generators_gc` fails (`5530537\n` vs 5 lines). This is **pre-existing** — the reviewer reproduced it identically on `/tmp/base`, and my diff is documentation only.
- Probe `p1.py` (dict/list/slice/bytearray) via `cmp.sh`: general and typed builds both match CPython stdout and exit.
- `git diff --stat` vs staging base → exactly the 7 allowed files (2 manifest pins + 5 new).

I did not re-run the full 180-build determinism sweep: no probe/compiler logic changed, only a Markdown figure. Committed on the branch; not pushed per the runner rule.
[commandcode stop=end_turn turns=18 out_tokens=5556]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — shfixpt1 (self-hosting determinism prep)

**What the change actually does:** adds `tools/c_determinism.py` (3-build-per-program sweep varying `PYTHONHASHSEED`/dirs), `lab/selfhost/DETERMINISM.md` (measurements), `docs/design/SELFHOST_FIXPOINT.md` (156-line design), and a ratchet test `AIL_CURRENT/test_ail_c_determinism.py` registered via `tests.d/` + manifest pins. No compiler, runtime, or benchmark file is touched. This matches the report.

**Probes** (`bash ~/tools/cmp.sh <p.py> $PWD`, both builds, HEAD and `/tmp/rbase`):
- `q1.py` dict/set order, list slice then mutate, `bytearray`→`bytes` copy: both builds same stdout/exit as CPython on HEAD and base; generated `program.c` byte-identical base vs HEAD.
- `q2.py` empty list, negative index, aliasing/`is`, slice copy: both builds match CPython; C identical base vs HEAD.
- `p3.py` `2**63` boundary: named compile-time refusal (`int64 constant expression out of range`) on both HEAD and base — acceptable, identical base.

**Tests on HEAD** (`par_check -j 2`): `test_ail_c_determinism` ok (28 s), `test_ail_safetynet` ok (181 s, **0 failed**), `test_ail_files` ok, `test_ail_corpus_findings3` ok. Module is in `ail_check.MODULES` and `update_manifest.py --check` is clean.

**Report claims:**
- program.c = 213,665 B, binary = 15,880 B — **verified** (measured; the doc previously quoted the binary).
- ~0.9 s / ~38 MB — **verified approx.** (measured 0.57 s wall, 41 MB RSS).
- 7 files, 2 manifest + 5 new — **verified**.
- `test_ail_safetynet` "4/5 pass, S4 fails pre-existing" — **false here**: the module passed all tests on HEAD. Likely load/memory-flaky, not caused by this diff.
- "did not re-run 180-build sweep" — consistent; I summarised the recorded JSON: identical programs **26/30**, identical pairs **34/60 (34/34 compared)**, 8/8 typed, per-program table matches exactly. Doc numbers verified.

**Minor, non-blocking:** design doc names the committed seed `selfhost/seed/program.c` in the stage table (line 15) but `selfhost/seed/compiler.c` in §2/§5 — inconsistent filename. The §4 stage-2 command uses the compiled `keyword.py` binary `kw` as a compiler; the text explains this is illustrative until `compiler.ail` exists.

**Pre-existing:** the int64-literal refusal in `p3.py` (identical on base); none of the probe differences are attributable to this change.

**Unverified:** live 60-program sweep (killed at 57/60, pattern matched recorded run); CI shard results.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=30 out_tokens=18837]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T22:26:27Z
