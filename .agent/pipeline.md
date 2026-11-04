# job job-toml1-11042158  started 2026-11-04T12:58:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed the one blocking defect from the review.

## What I found
- The review's only blocking defect was real and reproduced: `q_nul2.py` gave `Cannot declare ('a\x00b',) twice` / `Cannot mutate immutable namespace` in both builds, while CPython printed two distinct tables.
- Cause: `_join_prefix` joined key parts with `\u0000`, so `["a","b"]` and `["a\u0000b"]` encoded identically.

## Fix
- `AIL_CURRENT/stdlib/tomllib/_parser.py`: encode each part as `"<len>:<part>"` (self-delimiting, no two distinct key lists collide) and make `_flag_unset_all` match descendants by that prefix.

## Verification
- `q_nul2.py` — both builds now print `ok {'a': {'b': {}}, 'a\x00b': {'c': 2}}` and `... {'c': 1}`, matching CPython.
- `q_flags.py` (17 cases: tables, dotted keys, `[[x]]`, frozen/inline, NUL keys) — same stdout as CPython in `g` and `d`.
- `test_ail_std_tomllib.py` — `Ran 2 tests ... OK`.
- `test_ail_safetynet.py` — only pre-existing `S4_generators_gc` fails (as documented by the prior review).
- `tools/update_manifest.py` then `--check` — rc=0.
- Committed as `bb73b5c` on `job-toml1-11042158` (no push).
[commandcode stop=end_turn turns=15 out_tokens=5560]

## review 0
[model commandcode/deepseek-v4.1-flash]
Everything checks out. Here's my review.

## Review

**What the change really does:** In the bundled `stdlib/tomllib/_parser.py`, it replaces the `"\u0000"`-joined flag keys with a self-delimiting `"<len>:<part>"` encoding (`_join_prefix`), and simplifies `_flag_unset_all` to delete every entry whose encoded key starts with the target key. Plus the regenerated `manifest.d/53.txt` hash. No compiler/runtime files touched.

**Probes** (`/tmp/rprobes`, both builds `g`/`d`, compared with CPython):

| Probe | Coverage | Result |
|---|---|---|
| `r_nul2.py` | review's defect: NUL key vs `a.b` (declare + dotted) | same stdout, exit 0, both builds |
| `r_enc.py` | empty key parts, `["1:a"]` vs `[a]`, prefix keys, NUL at both ends, colon/digit keys, `[[a]]` reset, frozen+cross-section | same |
| `r_aot.py` | array-of-table `unset_all` across nested tables, dotted names, inline-list items, repeated `[a.b]` | same |
| `r_enc2.py` | 10-char / `0:`-prefixed key pairs, non-ASCII 3-char key vs `"3:eee"`, NUL key + `[[a\u0000]]`, `[[a.b.c]]`, inline-table then dotted reuse | same |
| `r_plain.py` | program not using the feature | `--debug-dir/program.c` byte-identical HEAD vs `/tmp/base` (md5 `4f97535f…`) |

I also brute-forced the encoding over a hostile alphabet `{a,b,1,:,NUL,ab,"1:a","",10}` for sequences up to length 3: **0 collisions and 0 prefix-property mismatches** — so `_join_prefix` is injective and prefix-order-preserving, which is exactly what `_flag_is`/`_flag_unset_all` need. `_flag_unset_all` collects into `doomed` before deleting, so no mutation-during-iteration issue.

Causation confirmed: `r_nul2.py` on `/tmp/base` (`work`) still prints `Cannot declare ('a\x00b',) twice` / `Cannot mutate immutable namespace`, while HEAD matches CPython.

**Tests on HEAD:** `test_ail_std_tomllib` OK (408s). `test_ail_safetynet` fails only `S4_generators_gc` (123s) — a GC test untouched by this stdlib-only diff; pre-existing, as recorded by the prior review. `python3 tools/update_manifest.py --check` rc=0.

**Claims in the report:**
- Review defect reproduced on base and fixed on HEAD — **verified**.
- Cause (`_join_prefix` used `\u0000`) and fix (`len:part`, prefix-unset) — **verified** against the diff.
- `q_flags.py` 17 cases match — **not independently reproduced** (file not in repo), but my four probes cover the same categories and match.
- `test_ail_std_tomllib` OK; safetynet only `S4_generators_gc`; manifest rc=0; commit `bb73b5c` — **verified**.

**Pre-existing:** `S4_generators_gc` (unrelated, compiler/runtime GC). Not caused by this change.

**Unverified:** worker's exact `q_flags.py` contents; speed — not applicable (stdlib-only, no benchmark program or hot compiler/runtime code edited; identical C for unrelated programs).

**Verdict rationale:** the sole blocking defect is fixed, the new encoding is collision-free/prefix-preserving under brute force, all flag-path probes match CPython in both builds, and unrelated C is unchanged.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=23 out_tokens=16507]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed.

The four failures all came from one defect in `python/pkg-v12/pyfunc.py`: signature propagation treated a `str` call-site claim as an "explicit annotation conflict" and refused the callee, so `take("wrong")` was reported at `take`'s declaration as a `parameter`/`signature_override` error. The intended split — documented in `_plan_clones` — is that `str` claims are owned by the per-call argument guard (`_infer_strparam_pass`), not propagation. I excluded `STR` claims in `_explicit_annotation_conflicts` so the call guard reports the real `argument` diagnostic at the caller.

Verification:
- `test_ail_argument_type_details`, `test_ail_check_repair_context`, `test_ail_source_check`: OK
- `test_ail_collections`: OK (348s)
- `test_ail_std_tomllib` (my tomllib fix): OK (410s); `test_ail_refusal_messages`, `test_ail_type_details`: OK
- `tools/update_manifest.py --check`: rc=0

Committed as `2d89439` with the manifest hash update.
[commandcode stop=end_turn turns=51 out_tokens=26758]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T16:18:21Z
