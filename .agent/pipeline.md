# job job-shparse2-11091931  started 2026-11-09T10:33:10Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The review was skipped, so I checked the job against its own done-check and probes rather than a defect list.

**State before my work:** stage 1 already matched 376/376 S376 files, and the test module + safetynet passed. Nothing named in the review needed redoing.

**One remaining silent difference I found and fixed:** `ailparse` accepted non-ASCII identifier characters that CPython either NFKC-normalizes (`café`, `Ⅷ` → `VIII`, `a\u0301` → `á`) or rejects (BOM `\ufeff`, zero-width space `\u200b`, emoji). AIL does not build `unicodedata.normalize`, so exactness isn't possible — per the task rule I made it a named refusal: `ailparse: non-ASCII identifiers are not supported` (raises `SyntaxError` on CPython). `tokenize` over CORPUS.txt shows **0** non-ASCII NAME tokens, so the number is unaffected.

**Probes (all pass):**
- 54 valid constructs (assign chains, star/tuple targets, aug/annotated assignment with `simple`, `del`, `raise from`, imports, `if/for/while else`, defs with all param kinds, async, class bases/kw/decorators, try/except/else/finally, `except*`, multi/parenthesized `with`, lambda defaults, docstrings, `match=`/`type=` as names) — byte-identical to `ast.dump`.
- 17 invalid snippets — same error/no-error as `ast.parse`.
- 5 zero-occurrence constructs (`match`, `type X=`, generic def/class) — refused by name.
- 23 edge cases (empty, CRLF, BOM, zero-width, emoji, `café`, `Ⅷ`, combining marks) — match CPython or named refusal.

**Verification:**
- Stage 0 vs stage 1 over S376: `identical 376, different 0, refused 0`.
- `test_ail_selfhost_parse.py`: 9 tests OK (includes 30 files stage 1 and stage 2 build).
- `test_ail_safetynet.py`: 5 OK; `test_ail_files.py`: 18 OK (1 skip); `test_ail_corpus_findings3.py`: 2 OK.
- `update_manifest.py --check`: OK.

Committed as `0db2788` (4 files: `ailtok.py`, the test module, `PARSE.md`, `manifest.d/41.txt`). Not pushed, per the rules.
[commandcode stop=end_turn turns=41 out_tokens=27718]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change does:** it makes the self-hosted tokenizer (`selfhost/src/ailtok.py`) raise `TokError("ailparse: non-ASCII identifiers are not supported")` for any non-ASCII character in identifier position, and adds matching cases to `test_ail_selfhost_parse.py` (2 refused, 4 invalid), a PARSE.md section, and the manifest hash.

**Verified**
- Stage 0 vs stage 1 over S376: `identical 376, different 0, refused 0`.
- `tokenize` over CORPUS.txt: 0 non-ASCII NAME tokens; so the number is unaffected.
- `test_ail_selfhost_parse` and `test_ail_safetynet` pass (`par_check -j 2`).
- `update_manifest.py --check` passes.
- Probes: non-ASCII only in strings/comments/docstrings/f-string text/format spec/dict key → dump identical to `ast`. BOM / ZWSP / emoji / NBSP-indent / non-ASCII digit/operator → both reject. `café = 1`, `Ⅷ = 1`, `a\u0301 = 1` → named refusal.
- 3 compiler probes (fib/list/dict, Unicode string/comment program, class/try): both builds match CPython; generated `program.c` byte-identical HEAD vs `/tmp/base` (change is not on the compiler path).
- Commit `0db2788` touches exactly the 4 files the report says.

**Defect 1 — regression in an existing, CI-registered module.** `AIL_CURRENT/test_ail_selfhost_tok.py::TokTest::test_edge_cases_stage1`, subTest `non_ascii`, fails on HEAD. Probe source (the test's own `EDGE["non_ascii"]`):
```
été = '日本'
変数 = 1  # コメント
class Ça: pass
```
- Expected: CPython `tokenize` / base `ailtok.tokenize` → 15 tokens (base: `ok, tokens 15`).
- Actual HEAD: `ailtok.TokError: ailparse: non-ASCII identifiers are not supported`.
- `cd AIL_CURRENT && python3 -m unittest test_ail_selfhost_tok.TokTest.test_edge_cases_stage1` → `FAILED (errors=1)`; the same test is `OK` on `/tmp/base`. The whole module fails 1/4 tests. `tests.d/test_ail_selfhost_tok.txt` registers it, so CI breaks.
- Cause: the refusal is placed in the tokenizer, whose contract (module docstring) is to match CPython's `tokenize` on valid source. Fix: put the refusal in `ailparse.parse` (it still satisfies the parse-level `BOUNDARY_REFUSED` cases) and leave `ailtok.tokenize` matching CPython.

**Defect 2 — file scope.** The diff edits `selfhost/src/ailtok.py`, which is not in the task's "Files you may create or edit, and no others" list; the done-check says "the diff shows only the listed files". Moving the refusal into `selfhost/src/ailparse.py` (defect 1's fix) also restores scope.

**Pre-existing (identical on base):** `x = b'é'` — CPython rejects ("bytes can only contain ASCII"), `ailparse` accepts; base does the same. Not blocking.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not run, per instructions); instruction counts (compiler C is byte-identical, so no hot-path change).

VERDICT: FIX
1. `AIL_CURRENT/test_ail_selfhost_tok.py::TokTest::test_edge_cases_stage1[non_ascii]` fails on HEAD (`TokError: ailparse: non-ASCII identifiers are not supported`); expected CPython tokenize's 15 tokens (base passes). Move the non-ASCII refusal from `selfhost/src/ailtok.py` into `ailparse.parse`.
2. The diff edits `selfhost/src/ailtok.py`, outside the task's permitted file list (and the done-check's "diff shows only the listed files"); same fix (refusal in `ailparse.py`) restores scope.
[commandcode stop=end_turn turns=40 out_tokens=26603]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. Both reviewer defects are fixed and verified.

**Defects**
1. **Tok regression** — moved the non-ASCII refusal out of `ailtok.is_name_start`/`is_name_char` and into `ailparse.Parser.__init__` (scans NAME tokens). `ailtok.tokenize` again matches CPython: the `non_ascii` edge case gives `True 15` (the test's expected 15 tokens).
2. **Out-of-scope file** — `ailtok.py` is restored exactly to its pre-defect content (`git diff f5f4d1a -- selfhost/src/ailtok.py` is empty), so the branch's cumulative diff no longer touches it.

I also made the AIL-side `_parse_syntax_error` placeholder raise `ParseError` instead of returning `None`, so stage 2 refusals print the same `!! refused: ailparse: ...` line as stage 1 rather than `expected AST, got None`.

**Verification (all on the final commit)**
- S376 stage 0 vs stage 1: `identical 376, different 0, refused 0`.
- `test_ail_selfhost_parse` 9/9 OK; `test_ail_selfhost_tok` 4/4 OK; `test_ail_safetynet` 5/5 OK; `test_ail_files` 18 OK (1 skipped); `test_ail_corpus_findings3` 2/2 OK.
- Probes: `nonascii_text.py` and `control.py` match CPython in both the default and `AIL_UNIFIED_FORCE=1` builds; `parse_drv` stage 1 vs stage 2 is byte-identical on valid, non-ASCII-identifier-refused, and BOM-invalid sources.
- `python3 tools/update_manifest.py --check` passes.
- Commit `2577202` touches `ailparse.py`, the `ailtok.py` revert, and `PARSE.md`.

Known pre-existing, unchanged (per review): `x = b'é'` — CPython rejects, `ailparse` accepts. Not blocking.
[commandcode stop=end_turn turns=42 out_tokens=30559]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does (matches the report):** it moves the non-ASCII-identifier refusal out of `ailtok.is_name_start/char` (which broke `ailtok.tokenize`'s contract) into `ailparse.Parser.__init__`, where it scans NAME tokens and raises `ParseError('ailparse: non-ASCII identifiers are not supported')`; and it makes the AIL-side `_parse_syntax_error` placeholder raise `ParseError(message)` instead of returning `None`. Cumulative diff touches only `selfhost/src/ailparse.py`, `lab/selfhost/PARSE.md`, `AIL_CURRENT/test_ail_selfhost_parse.py`, `manifest.d/41.txt`. `git diff f5f4d1a -- selfhost/src/ailtok.py` is empty, and no compiler/runtime file is touched.

**Probes (`/tmp/rprobes`, base = `/tmp/base` at `work`)**
- `ailparse_probe.py` (23 module sources + 4 expressions): base **8 MISMATCH**, HEAD **0**. Non-ASCII in comments/strings/docstrings/f-string text/BOM-start/end, empty, plain: MATCH or BOTH-ERROR. Non-ASCII identifiers (`café`, decomposed `cafe\́`, `Ⅷ`, fullwidth `ｘ`, `obj.café`, `f(café=1)`, `def café`, `import café`, class attr): named refusal. `ailparse.parse_expr` same.
- `mini.py`: base silently differs on decomposed café, `Ⅷ`, fullwidth `ｘ`; HEAD refuses each by name. Identical on all non-identifier text.
- `extra.py`: non-ASCII in dict values/format specs/nested f-string/`**kw`/list+attr MATCH; values unaffected by aliasing because nothing is retained from the source.
- `p1_nonascii_text.py`, `p_unicode_lit.py`, `p_ascii.py`, `p2_plain.py` via `cmp.sh` on HEAD **and** base: g and d builds exit 0, same stdout as CPython, same on base (C unchanged).
- Stage 2: built `parse_drv`, stage1 vs stage2 **byte-identical** over valid, non-ASCII-identifier, decomposed, BOM-start and BOM-end files and non-ASCII text; refusal line identical `!! refused: ailparse: non-ASCII identifiers are not supported` (the placeholder change works on both the ParseError and TokError paths).

**Tests run on HEAD:** `par_check -j 2 test_ail_selfhost_parse test_ail_safetynet` → both ok (89 s); `test_ail_selfhost_tok` ok (12 s); `tools/update_manifest.py --check` exit 0. S376 stage0 vs stage1: **identical 376, different 0, refused 0**; independent `tokenize` scan of CORPUS.txt: 376 entries, **0** non-ASCII NAME tokens, so the refusal cannot lower the number.

**Claims:** tok regression fixed (15 tokens, tok test passes) ✔; `ailtok.py` restored (empty diff) ✔; S376 376/376 ✔; parser/tok/safetynet tests pass ✔; stage1=stage2 incl. refusals ✔; manifest check ✔. `test_ail_files` and `test_ail_corpus_findings3` were not re-run (out of review scope).

**Pre-existing (identical on base, does not block):** `x = b'é'` — CPython rejects, `ailparse` accepts; lone-surrogate literal `x='\ud800'` — CPython `ast.parse` raises `UnicodeEncodeError`, `ailparse` accepts.

**Unverified:** the worker's `test_ail_files`/`test_ail_corpus_findings3` results; instruction counts (not applicable — no compiler/runtime file changed).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=36 out_tokens=32447]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T12:25:05Z
