# job job-mailcap1-11060850  started 2026-11-05T23:54:04Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done.

**What was wrong:** `test_ail_std_mailcap` was the outlier among the five modules. Every one of its 20 builds takes the general path, and the bundled `mailcap` imported `re` solely for `_find_unsafe`, pulling the whole relib prelude into each general compile: ~65 s per build under load, ~18 min for the module (it reached program 07 of 20 at 12 min). The other four modules passed unchanged.

**Fix:** `AIL_CURRENT/stdlib/mailcap.py` no longer imports `re`; `_find_unsafe` scans for CPython's pattern `[^\xa1-\U0010FFFF\w@+=:,./-]` by code point and returns the first unsafe character or `None` (only truthiness is used). I verified the character set matches CPython's regex over all 0..0x10FFFF code points (0 mismatches). A build dropped to ~12–15 s.

**Records:** DEVLOG entry at top; DIFFERENCES row `C?-job-mailcap1-11060850-1`; manifest pin updated via `tools/update_manifest.py` (`--check` passes). Commit `9dadf33`.

**Tests on the final commit** (`par_check -j 2`, 0 failed):
`obj_refs` 11.3s, `safetynet` 178.7s, `std_mailcap` 255.5s, `virtual_dispatch` 56.4s, `files` 104.6s, `unified` 348.3s, `corpus_findings3` 236.4s.

**Probes** (`bash ~/tools/cmp.sh`, default and `AIL_UNIFIED_FORCE=1`, all "same stdout" vs CPython):
- `p1_find_unsafe.py` — every ASCII punctuation/control class, `\x7f`–`\xa1`, Latin-1, CJK, `\uffff`
- `p2_findmatch.py` — safe/unsafe filename, wildcard, missing type, unsafe MIME/plist, defaults, empty caps
- `p3_subst.py` — `%s`, `%t`, `%{...}`, `%%`, escapes, empty field, trailing `%`, unsafe MIME/param
- `p4_values_via.py` — values through an argument, list items, an attribute and dict values

Not verified: I could not reproduce failures for `obj_refs`, `safetynet`, `unified`, `virtual_dispatch`; they pass here, so their listing on the gate remains unexplained by this tree.
[commandcode stop=end_turn turns=100 out_tokens=43501]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: `9dadf33` (mailcap1 suite fix)

**What the change really does:** `stdlib/mailcap.py` stops importing `re`; `_find_unsafe` becomes a per-character scan returning the first unsafe character or `None` (all call sites only test truthiness). Plus DEVLOG, one DIFFERENCES row, manifest pin. It matches the report.

**Probes** (`/tmp/rprobes`, both builds, `cmp.sh`; HEAD unless noted):
- `p1_unsafe_chars.py` — every code point 1..0xa1, é, 中, U+FFFF, empty and a safe filename through `findmatch`: same stdout, exit 0. (My first version added `chr(0x10000)`; both builds refuse `AIL limit: chr_non_bmp` — compiler-wide 16-bit limit, not this change.)
- `p2_subst.py` — `%s %t %{…} %%`, escapes, `%n%F%q`, unsafe MIME/param: same stdout, exit 0.
- `p3_values_via.py` — filename via argument, list item, attribute, dict value: same stdout.
- `p4_mime_and_private.py` — unicode MIME through `%t`, filenames with `\x01`, `\xa1`, `\x7f`: same stdout.
- `p8_mailcap_re.py` — program importing both `mailcap` and `re`: same stdout (removing `re` doesn't disturb programs that import it themselves).
- `p7_nonbmp.py` — non-BMP literal: named refusal (`not in the subset: a non-BMP string literal in the 16-bit v2 runtime`) on both builds.
- `p6_plain.py` — non-mailcap program: `--debug-dir` `program.c` byte-identical to a base (`/tmp/base`) build; `native_report.json` differs only in temp paths.
- `p5_private.py` — `hasattr(mailcap,'re')` refused by name ("module used as a value"), acceptable.

Character-set equivalence re-checked independently over 0..0x10FFFF against CPython's regex: **0 mismatches**.

**Tests on HEAD** (`par_check -j 2`): std_mailcap **288.2s ok**, safetynet **203.9s ok**, obj_refs 11.3s ok, virtual_dispatch 56.7s ok, unified 340.8s ok.

**Claims:** all verified — base general build 41s vs HEAD **10s**; the gate runs each module under `timeout 900` (`culprit.yml`), so the base module (~20 builds) exceeding 15 min and HEAD at 288s is consistent with the report's diagnosis. `update_manifest.py --check` rc=0; DEVLOG at top; DIFFERENCES id `C?-job-mailcap1-11060850-1` matches the branch.

**Non-blocking note:** `_find_unsafe` now returns a character where CPython returns a `re.Match`, and `mailcap.re` no longer exists. Both are declared in the new DIFFERENCES row and only truthiness is observed by the module's public callers; no probe of the public API differs.

**Pre-existing:** `chr()`/literal non-BMP refusals (compiler limit, identical without this change).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not run; the diff does not touch their subject).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=50 out_tokens=30952]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T02:25:08Z
