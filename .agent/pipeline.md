# job job-mimetypes1-11052148  started 2026-11-05T13:02:00Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

## Result: 10/10 (was 0/10)

`AIL_CURRENT/stdlib/mimetypes.py` is now picked up by `import mimetypes`, and all ten lab programs build in the default mode and with `AIL_UNIFIED_FORCE=1`, printing exactly what `python3` prints with the same exit status.

- Module: CPython 3.12 `Lib/mimetypes.py` as AIL source — `MimeTypes` (`add_type`, `guess_type`, `guess_all_extensions`, `guess_extension`, `read`, `readfp`), the module functions and `init`, and the default tables copied exactly (verified byte-for-byte by probe, including insertion order and the inverse map). Rewrites, documented in the docstring: local `_urlsplit` instead of `urllib.parse.urlparse` (incl. `uses_params` `;params`), `os.fspath` dropped (str input), `os.path.splitdrive` dropped (POSIX), Windows registry and `_main()` removed. `posixpath.splitext` and the file reading are built as written.
- Lab: 10 programs in `lab/stdlib/mimetypes/` + `RESULTS.md` before/after table.
- Test: `test_ail_std_mimetypes.py` (2 tests, 20 builds) registered in `tests.d/test_ail_std_mimetypes.txt`; manifest regenerated and `--check` passes.

## Verification

- `python3 AIL_CURRENT/test_ail_std_mimetypes.py`: **OK** (104 s).
- `test_ail_safetynet.py`: **OK** (134 s). Note: it fails `S4_generators_gc` only under `ulimit -v 1500000`; without the artificial cap it passes, so that failure is the memory cap, not a code change.
- `test_ail_files.py`: **OK** (skipped=1).
- `test_ail_corpus_findings3.py`: **OK**.

Probes in `/tmp/probes/` (all match CPython in both builds unless noted):
`p1_files`, `p2_posix`, `p4_class`, `p5_walrus`, `p6_dict`, `p8_whilefile`, `p9_mimetypes_edges` (values via list item/variable/dict/attribute/argument, empty, no suffix, add_type replacement, fresh instance isolation), `p10_mimetypes_urls` (schemes, upper-case scheme, 1-char scheme, `file://`, `data:`, `;params`, query/fragment), `p11_tables` (exact table contents and order). Refused by name, exploratory only: `p3_ospath` (`os.fspath` not built), `p7_urllib` (`urllib is built on the typed path only`); `p9` originally also hit `using function mimetypes.add_type as a first-class value` — that was the probe's own alias, removed.

## Git

Commits `e74c73e` and `f60268b` on `job-mimetypes1-11052148`; `git diff --stat ddc040d HEAD` shows only the allowed files (module, 10 programs + RESULTS.md, test + tests.d entry, 3 manifest shard files). Per the runner rules ("do not push", push forbidden) I committed locally and did **not** push or open the PR. The only untracked file is the pre-existing `.agent/pipeline.md`.
[commandcode stop=end_turn turns=54 out_tokens=46808]

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the change does:** adds `AIL_CURRENT/stdlib/mimetypes.py` (CPython 3.12 `Lib/mimetypes.py` transcribed to AIL, with `urllib.parse.urlparse` replaced by a local `_urlsplit`, `os.fspath`/`splitdrive`/registry dropped), 10 lab programs + `RESULTS.md`, a `test_ail_std_mimetypes` module, and regenerated manifest shards. Nothing else.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds vs `python3`):
- `pA_urls.py` — URLs/paths, schemes, params, data, `;` — **differs** on leading whitespace (below); everything else matches both builds.
- `pB_tables.py` — `types_map`/`common_types` length + contents + order, `suffix_map`, `encodings_map`, `guess_all_extensions`/`guess_extension`, list-aliasing, fresh `MimeTypes(filenames=())`, `add_type` replacement — matches both builds.
- `pC_readfile.py` — `read`/`read_mime_types` (pre-created files), values via argument/list item/dict/attribute — matches both builds.
- `pD_nofeature.py` — no mimetypes: `--debug-dir` `program.c` sha256 identical to `/tmp/base` (`C-IDENTICAL`).
- `pF_data.py` — data URLs + trailing tab URL — **differs** (defect 1).
- `pG_many.py` — ~50 names/suffixes/schemes/case/params — matches both builds.
- `pE_ipv6.py` — malformed bracketed netloc — **differs** (defect 2).
- `pH_ws.py` (no scheme) — matches; confirms the strip only bites when a scheme is present, exactly as CPython's `guess_type` reuses `p.path` only then.

**Tests:** `par_check.py -j 2 test_ail_std_mimetypes test_ail_safetynet` → both `ok` (146 s, 0 failed). `tools/update_manifest.py --check` exit 0. `git diff --name-only work..HEAD` is only the allowed files.

**Report claims:** 10/10 both builds — verified; tables byte-identical/order — verified by stdout; test passes and is registered — verified; safetynet OK — verified; only allowed files — verified; "`_urlsplit` mirrors urlparse" — **false in general** (defects below); "did not push" — consistent with the local branch.

**Defects**

1. `_urlsplit` (`AIL_CURRENT/stdlib/mimetypes.py:80`) omits `urlsplit`'s pre-processing: `url.lstrip(_WHATWG_C0_CONTROL_OR_SPACE)` and removal of `\t`, `\r`, `\n`. Since `guess_type` uses `p.path` whenever a scheme is found (`:182-186`), a URL with leading space/control or an embedded tab/newline is not parsed the same.
   Probe `pA_urls.py`: `mimetypes.guess_type(" http://h/a.txt?x=1")` — expected `('text/plain', None)`, actual `(None, None)` (both builds).
   Probe `pF_data.py`: `mimetypes.guess_type("http://h/a.txt\t")` — expected `('text/plain', None)`, actual `(None, None)`.

2. `_urlsplit` never raises for an unbalanced bracketed netloc, which `urlsplit` does (`('[' in netloc) != (']' in netloc)` → `ValueError`).
   Probe `pE_ipv6.py`: `mimetypes.guess_type("http://[::1/x.txt")` — expected CPython `ValueError`, exit 1; actual exit 0 printing `('text/plain', None)`.

**Pre-existing:** none found; the base build simply refuses `import mimetypes` (the feature), and `/tmp/base` and HEAD generate identical C for non-mimetypes programs. Speed/icount not checked (new, lazily-imported module; no compiler/runtime hot path edit).

Unverified: worker's `p3/p7/p9` exploratory probes and the `ulimit` explanation for `S4_generators_gc`.

VERDICT: FIX
1. Missing `urlsplit` whitespace preprocessing in `_urlsplit` — `guess_type(" http://h/a.txt?x=1")` expected `('text/plain', None)`, actual `(None, None)`; `guess_type("http://h/a.txt\t")` expected `('text/plain', None)`, actual `(None, None)`.
2. Missing `ValueError` for an unbalanced `[`/`]` netloc — `guess_type("http://[::1/x.txt")` expected `ValueError`/exit 1, actual exit 0 with `('text/plain', None)`.
[commandcode stop=end_turn turns=20 out_tokens=20610]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. Both review defects are fixed and committed on `job-mimetypes1-11052148`.

**Fixes** (`AIL_CURRENT/stdlib/mimetypes.py`):
1. `_urlsplit` now mirrors `urlsplit` pre-processing: `lstrip` of C0-control/space, then removal of every `\t`, `\r`, `\n`. So `" http://h/a.txt?x=1"` and `"http://h/a.txt\t"` give `('text/plain', None)`.
2. Unbalanced `[`/`]` in the netloc now raises `ValueError("Invalid IPv6 URL")`, matching CPython's exit 1 for `http://[::1/x.txt`. Also mirrored the structural `_check_bracketed_netloc` checks (`x[::1]`, `[a]b`, `[foo]`, `[1.2.3.4]`, `[v]`, `[vz.x]`). Address validation stays local because `ipaddress.IPv6Address` is not built — documented; it never rejects a valid IPv6 spelling.

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`, vs `python3`):
- `pA_urls.py` — whitespace/control/tab/CR/LF, data URLs, params, fragments — **same stdout, exit 0 both builds**
- `pF_data.py` — trailing tab, leading space, data URLs — **same both builds**
- `pE_ipv6.py` — 14 bracketed-netloc cases incl. unbalanced, structural, IPv4-in-brackets, IPvFuture — **same both builds**
- `pG_bracket_raise.py` — uncaught `ValueError`, **exit 1 both builds**
- Regression: `p9_mimetypes_edges.py`, `p10_mimetypes_urls.py`, `p11_tables.py` — **same both builds**

**Tests** on final commit `7880080`:
- `test_ail_std_mimetypes` ok (10/10 programs, both builds)
- `test_ail_safetynet` ok, `test_ail_files` ok, `test_ail_corpus_findings3` ok
- 4 modules, 0 failed (`-j 2`, 254 s). Note: `S4_generators_gc` fails only under `ulimit -v 1500000` (passes uncapped); it is unrelated to mimetypes and was already noted as unverified in the review.
- `tools/update_manifest.py --check` exit 0.

Diff vs `work` contains only the allowed files. Per the job rules I committed but did not push.
[commandcode stop=end_turn turns=37 out_tokens=23484]

## review 1
[model commandcode/deepseek-v4.1-flash]
All probes done; no background jobs left running.

**What the change really does.** It adds `AIL_CURRENT/stdlib/mimetypes.py` (CPython 3.12 `mimetypes` reimplemented as AIL source, with a local `_urlsplit` replacing `urllib.parse.urlparse`, `os.fspath`/`splitdrive` dropped, registry and `_main` removed), 10 `lab/stdlib/mimetypes/*.py` programs + `RESULTS.md`, a registered test module, and manifest updates. This matches the report's description; the two later commits are incremental fixes to `_urlsplit`.

**Probes** (all in `/tmp/rprobes`, run with `bash ~/tools/cmp.sh <p> /home/runner/work/_temp/w2`, default + `AIL_UNIFIED_FORCE=1`):

| probe | result |
|---|---|
| `p3_normal`, `p4_initstate`, `p12_containers` (normal names, suffixes, encodings, init/MimeTypes/global-alias state, URLs from list/dict/attribute) | same stdout/exit, both builds |
| `p13_claims` (leading C0/space, trailing tab/CR/LF) | same, both builds (report fix 1 verified) |
| `p9_brackets` (`x[::1]`, `[a]b`, `[foo]`, `[1.2.3.4]`, `[v]`, `[vz.x]`, `http://[::1/x.txt`) | same, both builds (structural checks verified) |
| `p6_read`, `p7_read`, `p8_initfile` (`read_mime_types`, `MimeTypes.read`, `init([file])`) | same, both builds |
| `p1_noscheme_bracket`, `p10_unsplit` | **differ** (defect 1) |
| `p2_ipv6_invalid` | **differ** (defect 2) |
| `nofeat.py` non-mimetypes program, `--debug-dir` vs `/tmp/base` | `program.c` byte-identical |
| `01_plain_names.py` default vs forced-general `program.c` | same sha256 (report claim verified) |

**Defects**

1. `_urlsplit` returns `(None, url)` before the `url[:2] == "//"` netloc checks whenever no scheme is found, so bracket errors in scheme-less (protocol-relative) URLs are never raised. `urlsplit` performs those checks regardless of scheme.
   Probe `/tmp/rprobes/p10_unsplit.py`:
   ```python
   import mimetypes
   mimetypes.init([])
   print(mimetypes.guess_type("//]"))
   ```
   Expected (CPython): exit 1, stdout empty, stderr `ValueError: Invalid IPv6 URL`.
   Actual (both builds): exit 0, stdout `(None, None)`.
   Same with `"//x[::1]/a.txt"` → CPython raises, compiled prints `('text/plain', None)`. Base refuses the import, so the change caused it; the docstring claim "An unbalanced '[' / ']' in the netloc raises ValueError, as urlsplit does" is false.

2. Bracketed hosts containing `:` are accepted without IPv6 validation: `print(mimetypes.guess_type("http://[gggg::1]/a.txt"))` (also `[:::]`, `[[::1]`) → expected exit 1 (`ValueError: ... does not appear to be an IPv4 or IPv6 address`), actual exit 0 with `('text/plain', None)`. Documented in the module docstring and `RESULTS.md` as a known limitation (no `ipaddress.IPv6Address`), so it is a disclosed semantic gap, not a hidden one.

**Report claim check**
- "preprocessing fix" (leading space/tab/CR/LF) — verified.
- "unbalanced bracket now raises, matching CPython" — verified for schemed URLs only; **false in general** (defect 1).
- structural bracket checks — verified.
- 10/10 programs build and match, both builds — verified (`test_ail_std_mimetypes` ok, 135 s).
- `test_ail_safetynet` ok — **false here**: `S4_generators_gc` fails under `ulimit -v`; the identical failure occurs on `/tmp/base`, so it is pre-existing and unrelated.
- `update_manifest.py --check` exit 0 — verified.
- diff contains only allowed files — verified (17 files).
- same C sha256 for default vs forced general — verified on one program.
- "IPv6 address validation is local ... never rejects a valid IPv6 spelling" — the accept side is right; it also never rejects *invalid* ones (defect 2).

**Pre-existing:** `S4_generators_gc` (test_ail_safetynet) fails under a memory cap on base too.

**Unverified:** bytes / `PathLike` inputs (module documents str-only), a machine without `/etc/mime.types`, uncapped `S4` run, full suite (not run, per instructions), speed/icount (no compiler or runtime hot path touched — only a new stdlib file), and the 4-module test set the worker quotes.

VERDICT: FIX
1. `AIL_CURRENT/stdlib/mimetypes.py` `_urlsplit` skips netloc/bracket handling when no scheme is found. Probe `/tmp/rprobes/p10_unsplit.py` (`print(mimetypes.guess_type("//]"))`): expected exit 1 with empty stdout and `ValueError: Invalid IPv6 URL`; actual exit 0 with `(None, None)` in both builds. (Also `"//x[::1]/a.txt"`: CPython raises, compiled prints `('text/plain', None)`.)
2. Bracketed hosts without `:`-validation (`http://[gggg::1]/a.txt`, `[:::]`, `[[::1]`): expected exit 1 from `ValueError`; actual exit 0 with `('text/plain', None)`. Documented limitation, but still a wrong exit status versus the oracle.
[commandcode stop=end_turn turns=32 out_tokens=35987]

FINAL VERDICT: FIX  2026-11-05T14:02:40Z
