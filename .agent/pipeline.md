# job job-relnotice1_rr2-11090339  started 2026-11-08T18:40:19Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

## What I did

Recreated relnotice1 from scratch on the current tree (its `stdlib/`, `third_party/` and `THIRD_PARTY_NOTICES.md` are byte-identical to current `origin/integ`).

- **Inventory** — 77 files under `AIL_CURRENT/stdlib/` + `third_party/`:
  - 20 derived from CPython 3.12 (16 modules + `tomllib/*`): chunk, colorsys, copy, difflib, getopt, imghdr, keyword, linecache, netrc, quopri, sched, shlex, stat, timeit, token, xdrlib, tomllib (4)
  - 1 PyPy-derived (`marshal.py`, already noticed)
  - 50 typeshed (48 `.pyi` + `LICENSE` + `VERSION.md`)
  - 2 license texts, 4 AIL's own (`struct.py`, `zlib.py`, `zlib_glue.c/.h`)
  - **0 without a notice**
- **Notices** — added `AIL_CURRENT/stdlib/LICENSE-PSF.txt` (PSF License v2) and the one-line `Derived from CPython 3.12 Lib/...` docstring note to the 18 files that lacked it (docstring text only, no code). `copy.py`/`timeit.py` already had it.
- **Notices table** — added the missing `chunk.py` and `xdrlib.py` rows, corrected counts to the current tree.
- **Test** — `AIL_CURRENT/test_ail_third_party_notices.py` + `tests.d/test_ail_third_party_notices.txt`; registered via `tools/update_manifest.py` (`--check` clean).

## Wheel caveat (documented, not hidden)

`packaging/ail_wheel_backend.py` is owned by another lane and does **not** yet copy `LICENSE-PSF.txt` into the wheel, so the wheel genuinely lacks it. Per the brief I wrote the exact change under **Follow-ups** in `THIRD_PARTY_NOTICES.md` and made the wheel PSF test pass only while that paragraph exists (remove it without making the change → test fails). All derived stdlib files *are* in the wheel.

## Verification (final commit `b4efe242`)

- `test_ail_third_party_notices.py` — 7 tests **OK**
- `test_ail_packaging.py` — **OK**
- `test_ail_files.py` — **OK** (1 skip), `test_ail_safetynet.py` — **OK**, `test_ail_corpus_findings3.py` — **OK**
- All touched module tests **OK**: chunk, colorsys, difflib, getopt, imghdr, keyword, linecache, netrc, quopri, sched, shlex, stat, tomllib, xdrlib (each builds default + `AIL_UNIFIED_FORCE=1` and compares with `python3`).
- `tools/update_manifest.py --check` — clean.

No probe programs were needed: this change edits docstrings and adds files only; the module tests already assert identical output to CPython. `token.py` has no `test_ail_std_*` module in the repo, so its notice was not exercised by a dedicated test. Changes are confined to the allowed files plus `manifest.d/` (written by `update_manifest.py`). Committed on the branch; **not pushed**, per the run instructions.
[commandcode stop=end_turn turns=59 out_tokens=32732]

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 0
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

FINAL VERDICT: ERROR  2026-11-08T21:05:22Z
