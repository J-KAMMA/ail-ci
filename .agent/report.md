# job job-relnotice1_rr1-11060319  started 2026-11-05T18:20:05Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `368fecd`.

**Cause:** `test_ail_third_party_notices`'s wheel check (`test_psf_license_is_in_the_wheel`) expects the PSF notice, but the notices change only documented that as a follow-up — `packaging/ail_wheel_backend.py` copied just `LICENSE-APACHE`/`LICENSE-MIT`. The other four listed modules were already green here.

**Fix:** `collect()` and `prepare_metadata_for_build_wheel()` now copy `AIL_CURRENT/stdlib/LICENSE-PSF.txt` to `.dist-info/licenses/LICENSE-PSF.txt`; `test_ail_packaging`'s exact member list and byte check include it; notices docstring/follow-ups updated; DIFFERENCES row `C?-job-relnotice1_rr1-11060319-1` and DEVLOG entry added; `tools/update_manifest.py` refreshed pins and `--check` passes.

**Tests on the final tree:**
- `test_ail_third_party_notices` 7 OK (in a 27-test run with files/corpus_findings3, 1 skip)
- `test_ail_safetynet` 5 OK, `test_ail_unified` 14 OK
- `test_ail_obj_refs` + `test_ail_virtual_dispatch` 9 OK
- `test_ail_packaging` 21 OK (run after the code edits, before the docs/manifest-only commit)

**Probes** (`bash ~/tools/cmp.sh ... $PWD` unless noted):
- `p1_psf_stdlib_a.py` (colorsys, keyword, quopri, stat, token): CPython exit 0, both builds exit 0, same stdout.
- `p2_psf_stdlib_b.py` (difflib, getopt, shlex, tomllib): same stdout, both builds (first run diffed only a generator's `repr`; the probe now lists it).
- `p3_wheel_psf.py` (run with `python3`): one PSF member, 2715 bytes byte-equal, RECORD covers all 555 members, prepared-metadata copy byte-equal.
[commandcode stop=end_turn turns=39 out_tokens=18759]

## review 0
[model commandcode/deepseek-v4.1-flash]
Reviewed the change and ran my own probes and the affected modules.

**What the change really does:** packaging only — `packaging/ail_wheel_backend.py` now copies `AIL_CURRENT/stdlib/LICENSE-PSF.txt` into `.dist-info/licenses/` in both `collect()` (hence `build_wheel`) and `prepare_metadata_for_build_wheel()`; `test_ail_packaging`'s exact member set and a byte-equality check were extended; notices docstring/Follow-ups, DIFFERENCES, DEVLOG and manifest pins updated. Matches the report; no compiler/runtime touched.

**Probes** (`/tmp/rprobes/p_wheel.py`, run against HEAD): exactly one PSF member `ailc-0.1.0.dev0.dist-info/licenses/LICENSE-PSF.txt`, 2715 bytes, byte-equal to source; RECORD covers all 555 members with correct sha256/size including the new row; `prepare_metadata_for_build_wheel` writes a byte-equal copy. `hello.ail` compiled with `--debug-dir` on HEAD vs `/tmp/base` (`work`): `program.c` identical, only temp-path strings differ in `native_report.json`. `python3 tools/update_manifest.py --check` → exit 0.

**Tests (HEAD):** `test_ail_packaging` ok, `test_ail_third_party_notices` ok (7 tests), `test_ail_safetynet` ok, `test_ail_obj_refs` ok, `test_ail_unified` ok, `test_ail_virtual_dispatch` ok, `test_ail_files` ok — 0 failures with `-j 2`.

**Claim check:**
- fixed & committed as 368fecd — verified.
- notices wheel check failed because backend copied only root licenses — verified from the diff.
- other four listed modules already green here — verified: all pass on HEAD; I cannot reproduce the integ branch's reported failures from this worktree.
- test_ail_packaging 21 OK / notices 7 OK — verified.
- p3 wheel claims (one PSF member, 2715 bytes, RECORD 555, prepared copy) — independently reproduced.
- p1/p2 stdlib probes and test_ail_corpus_findings3 — not re-run; the change touches no compiler/runtime code, so they cannot be affected. Unverified.

**Pre-existing:** none found; no compiler output differs from base.

Minor (non-blocking): the wheel's `METADATA` lists only `License-File: LICENSE-APACHE`/`LICENSE-MIT`, so the added `.dist-info/licenses/LICENSE-PSF.txt` is not declared as a `License-File` header. The task and tests do not require it, and pyproject's `license-files` deliberately lists only the two root licenses.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=25 out_tokens=8700]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T20:05:44Z
