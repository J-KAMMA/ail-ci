# job job-rbhybex1-11042105  started 2026-11-04T12:06:14Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done.

**What I applied:** the accepted `job-hybex1-11041922` change — `examples/hybrid/` (README + 6 examples), `AIL_CURRENT/test_ail_examples_hybrid.py`, its `tests.d` registration, and `guide.csv`. The `.github/workflows/agent-worker.yml` hunk was already present on this tree (GitHub Models token already removed), so no change there; the `manifest.d` hunks were regenerated, not hand-applied. `tools/diff_ids.py` does not exist on this tree (only `update_manifest.py` ran; `--check` exits 0). No new DIFFERENCES row (no language behavior change). DEVLOG entry added at top with today's date.

**Commit:** `c8e5474a`, 13 files, explicit `git add`; nothing pushed. `.agent/pipeline.md` left untracked.

**Tests (final tree):** `test_ail_examples_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (211 s, `-j 2`).

**Probes** (`/tmp/probes/`, both builds via `cmp.sh`):
- `p_hybrid_collatz` (3000, 0, 1, -5) — same stdout both builds
- `p_hybrid_mandel` (80×40, empty width, empty height, 1×1) — same
- `p_hybrid_prime` (800, 0, 1, -3) — same
- `p_hybrid_hash` (empty, 1 char, 5 chars, 900 chars, `ord` + constant `%`) — same
- `p_hybrid_sumsq_int` and `p_hybrid_sumsq_float` (empty, negative, zero) — same
- `p_hybrid_channels` (list item, dict value, attribute, negative) — same
- `p_hybrid_mod` (constant divisor, negative, zero) — same
- `p_hybrid_boundary` — refused by name: `int64 constant expression out of range: 9223372036854775809` (both builds); the hybrid fallback itself is covered by the new test module, which passes.
[commandcode stop=end_turn turns=44 out_tokens=11241]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does:** it re-applies the accepted `job-hybex1` documentation/examples job — `examples/hybrid/` (README + 6 programs), `test_ail_examples_hybrid.py` + `tests.d` registration, `guide.csv`, a DEVLOG entry and regenerated `manifest.d` lines. No compiler or runtime file is touched (`git diff --name-only` has zero `AIL_CURRENT/ail_*`/`.c`/`.h`), so generated C is unchanged by construction. Byte-compared against `FETCH_HEAD`: all 10 content files identical; `agent-worker.yml` already equal to the job's version (the removal of `GH_MODELS_TOKEN` is present); `update_manifest.py --check` rc 0.

**Probes** (`/tmp/rprobes`, `cmp.sh` + a `build --cpython` harness):
- 6 examples, default standalone on HEAD: 5 same stdout on both builds; `fallback_demo.py` refused by name (`int64 constant expression out of range: 9223372036854775809`) — same refusal on `/tmp/base`, so pre-existing.
- 6 examples, hybrid build vs CPython, 39 argument sets (default, 0, 1, negative, boundary `10000001`, `2**63+1`, `2**64+3`, empty/negative widths): all stdout, exit status and stderr identical.
- `build.json` matches the README table: accelerated `longest/mandel_checksum/prime_count/triple`, none for `rolling_hash`/`sum_squares`; rejected `rolling_hash` "a call can raise or have side effects".
- README findings reproduced exactly: `a % b` → "division or power can raise"; `list[float]` → acc []/rej {}; `list[int]` → acc; direct `f(2.5)` and literal `2**63+1` → acc []; `g = f; g(2.5)` → acc + CPython-identical result; `ord` loop → rejected.
- Source-level check of the install claims: `compile --cpython` prints exactly `ail_chatgpt.py: error: unrecognized arguments: --cpython`; exported SDK excludes `build` with the quoted message; wheel backend bundles `ail_lang/sdk`. Not tested by installing a wheel.
- Speed table: my medians CPython 1339/648/852/12.9/113/11.9 ms and hybrid 59/22/36/14/115/22 ms vs README 1500/717/912/16.3/123.8/12.8 and 79/27/44/17.9/127.6/24.0 — consistent.

**Tests:** `par_check -j 2 test_ail_examples_hybrid test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed, 201 s; hybrid module verbose run 2/2 ok in 11.5 s (not skipped: gcc + Python.h present).

**Report claims:** all checked claims verified (commit c8e5474a, 13 files, additions-only, explicit paths, `diff_ids.py` absent, 4 modules pass). The wheel-building claims are the only ones I checked at source level rather than by installing a wheel.

**Pre-existing:** `fallback_demo.py` (like the worker's `p_hybrid_boundary.py`) is refused by the default standalone build; identical on `/tmp/base`, and a named refusal is acceptable.

**Unverified:** installed-wheel behaviour (built/installed wheel not exercised); the exact millisecond figures in the README table (only order-of-magnitude).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=44 out_tokens=24350]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `61aa843a`.

**Root cause:** signature propagation (`_explicit_annotation_conflicts` in `AIL_CURRENT/python/pkg-v12/pyfunc.py`) raised *any* caller claim contradicting an annotation as a `signature_override` refusal at the callee's declaration. So `take("wrong")` reported `operation: "parameter"`, target `take`, at line 1 — instead of the call-site argument guard's `operation: "argument"`, target `main`, at the actual call. That one bug caused all four modules' failures (also the `slist`-vs-`str` refusal text in `test_ail_collections`).

**Fix (8 lines):** only numeric (int/float) claims raise a propagation conflict; text/bytes/list claims are dropped there and left to the call-site argument check. Numeric conflicts keep the declaration-scoped diagnostic, so the signature-override tests still pass. Regenerated the `pyfunc.py` manifest pin and added a DEVLOG entry.

**Tests:** the four reported modules pass (0 failed, 196 s), plus `test_ail_type_details`, `test_ail_owned_type_details`, `test_ail_float_argument_widening`, `test_ail_refusal_messages`, `test_ail_examples_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 12 modules, 0 failed. `update_manifest.py --check` rc 0.
[commandcode stop=end_turn turns=42 out_tokens=16982]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T15:03:40Z
