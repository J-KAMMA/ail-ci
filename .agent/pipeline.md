# job job-pre27-10240859  started 2026-10-24T00:00:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Fixed the first still-differing case on this tree: `try: import html ... except ImportError` is now refused **by name and located** at the import (`2:5` for module level, `3:9` inside a function), with a rewrite hint; `ModuleNotFoundError` gets the same treatment. The second case (`import math, html`) already matched CPython on both builds, so it was untouched.

Commit: `1dfb77a`

**Probes** (`cmp.sh`, both builds):
- `import_html_try`, `import_html_use`, `import_from_html`, `import_two`, `import_module_not_found`, `import_tuple`, `import_alias`, `import_nested_func` — named refusals, located, both builds.
- `import_no_import`, `import_other_type` — generic caught-type refusal now located at `1:1`, both builds.
- `import_comma`, `import_html_exc` — stdout and exit status match CPython on both builds.
- Pre-existing, unchanged: `import_bad_exc` (`try: import unknown ... except Exception`) still silently succeeds; unrelated to this change.

**Tests on final commit:** `test_ail_pre27`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (321 s). Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 5745921, "input": 128911, "output": 9970, "reasoning": 15780, "cache.write": 0, "cache.read": 5591260}]
    tool time: bash 8.8 min, edit 0.0 min
        323s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre27 test_ail_safetynet test_ail_files test_ail
         48s bash   for p in import_html_try import_html_use import_from_html import_two import_module_not_found import_no_import 
         41s bash   git add AIL_CURRENT/test_ail_pre27.py && python3 tools/update_manifest.py && git add AIL_CURRENT/MANIFEST.json
         39s bash   git add AIL_CURRENT/MANIFEST.json && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre27 2>&1 
         29s bash   for p in import_from_html import_two import_module_not_found import_no_import import_tuple import_alias import
         19s bash   for p in /tmp/probes/import_html_try.py /tmp/probes/import_html_use.py /tmp/probes/import_html_exc.py /tmp/pro
         12s bash   for p in /tmp/probes/*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | head -20; done
         11s bash   printf 'import html\nprint(html.escape("<a>"))\n' > /tmp/probes/import_html_top.py; printf 'try:\n    import h

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job pre27 (`1dfb77a`)

**Change:** `pyboxed2.py` try/except check now names a guarded import for `except ImportError`/`ModuleNotFoundError`, points at the import, and locates other unsupported caught types at the `try`. New `test_ail_pre27.py`; DEVLOG/DIFFERENCES/MANIFEST updated.

**Probes (my own, `/tmp/rprobes`, both builds, base `/tmp/base`):**
- `try: import html` / `import math, html` / `from html import escape` / `import html as h` / `except ModuleNotFoundError` / `except (ValueError, ImportError)` / nested-in-function → named refusal at `2:5` (or `3:9`, `4:13`), HEAD and base both refuse. Verified.
- `try: x=1 except ImportError` / `except KeyboardInterrupt` → now located (`1:1`); base same refusal unlocated. Verified.
- `import math, html` (html unused) → matches CPython on HEAD and base (p5, p13).
- `import math, html` with html retained (`html.escape`, `html` as value, `html.__name__`) → other refusals, byte-identical on base. Pre-existing.
- Import only in `except`/`else`/`finally` body, or nested try handler (p1–p4): refused on both HEAD and base; HEAD's text now over-broadly calls it "guarded", but the program was already refused, so no new acceptance difference.

**Pre-existing (unchanged on base):** `import_bad_exc` (`try: import nosuchmodule ... except Exception`) silently prints `ok` (CPython `no`); html-used import refusals; over-broad handler/finally import refusals.

**Tests on HEAD:** `test_ail_pre27`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (244 s). `update_manifest.py --check` exit 0. Commit trailer correct.

**Report claims:** first case fixed and located — verified; `ModuleNotFoundError` same — verified; generic caught type located — verified; "second case already matched" — only partly: the exact recorded `import of 'math, html'` message could not be reproduced, but `import math, html` (unused) matches and html-retained variants are identical on base. Not a regression.

**Not applicable:** speed (compile-time-only check; no emitted C changed).

Unverified: full suite (not run by design); exact original errmsg3 program for the second case.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1060068, "input": 45210, "output": 4721, "reasoning": 12761, "cache.write": 0, "cache.read": 997376}]
    tool time: bash 6.0 min, read 0.0 min
        246s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre27 test_ail_safetynet test_ail_files te
         27s bash   for p in /tmp/rprobes/*.py; do echo "=== BASE $(basename $p)"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | sed -
         27s bash   for p in /tmp/rprobes/*.py; do echo "=== HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | sed -n '
         26s bash   for p in p8_plain_two_used p9_plain_html_used p10_plain_two_ref p11_plain_two_from p12_func_use p13_math_use_h
         12s bash   cat > /tmp/rprobes/p12_func_use.py <<'EOF' import math, html  def f(s):     return html.escape(s)  print(f("<a
          8s bash   for t in "$PWD" /tmp/base; do echo "=== $t"; bash ~/tools/cmp.sh /tmp/probes/import_bad_exc.py "$t" 2>&1 | sed
          7s bash   cat > /tmp/rprobes/p8_plain_two_used.py <<'EOF' import math, html print(html.escape("<a>")) EOF cat > /tmp/rpr
          7s bash   cat > /tmp/rprobes/p10_plain_two_ref.py <<'EOF' import math, html x = html print(math.floor(2.5), type(x).__na

FINAL VERDICT: ACCEPT  2026-10-24T00:24:24Z
