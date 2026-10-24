# job job-pre52-10241239  started 2026-10-24T03:40:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Reproduced the first still-differing case on HEAD: `try: import html ... except ImportError` was refused without a location. Fixed in `pyboxed2.py`; the second case (`import math, html` unused) already matches CPython and was left alone.

Commit: `e01bd0a` (6 files, +150/−9). Manifest `--check` exit 0.

**Probes** (`/tmp/probes/pre52_*.py`, both builds):
- Named and located (`2:5`, `3:9`, `4:13`): `try_import`, `try_module_not_found`, `try_from_import`, `try_two_modules`, `try_alias`, `try_tuple_handler`, `try_import_math`, `try_nested_func`, `try_import_in_if`, `try_import_in_loop` — refused by name as intended.
- Generic caught-type located at `1:1`: `try_no_import`, `try_other_type`, `try_import_in_handler`, `try_import_in_else`, `try_import_in_finally` — refused by name as intended.
- Accepted and CPython-identical: `try_except_exception`, `try_math_zero`, `try_value_error`, `plain_two_unused`, `plain_html_unused`.
- Pre-existing, unchanged: `plain_html_used`, `two_used` (`html.escape` not published).

**Tests:** `test_ail_pre52`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (268 s).
[cost $0.0000, opencode tokens {"total": 2785078, "input": 137304, "output": 9614, "reasoning": 11344, "cache.write": 0, "cache.read": 2626816}]
    tool time: bash 8.1 min, edit 0.0 min, write 0.0 min
        270s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre52 test_ail_safetynet test_ail_files test_ail
        120s bash   find / -name 'test_ail_pre27.py' 2>/dev/null | head; grep -rn "pre27\|errmsg3\|math, html\|html, math" AIL_CUR
         76s bash   for p in /tmp/probes/pre52_*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-
         11s bash   mkdir -p /tmp/probes && printf 'try:\n    import html\nexcept ImportError:\n    print("no")\n' > /tmp/probes/p
          3s bash   cat > /tmp/probes/pre52_try_import.py <<'EOF' try:     import html except ImportError:     print("no") EOF bas
          1s bash   git fetch -q origin refs/heads/job-pre27-10240859:refs/remotes/origin/job-pre27-10240859 && git log --oneline 
          1s bash   cd /tmp/probes && cat > pre52_try_module_not_found.py <<'EOF' try:     import html except ModuleNotFoundError:
          0s bash   timeout 30 git ls-remote origin 'refs/heads/*pre27*' 'refs/heads/*pre5*' 2>&1 | head -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Only compile-time refusal diagnostics change. For an unsupported caught type (`ImportError`/`ModuleNotFoundError`) with any import in the `try` body, the general emitter now refuses at the import's line/col and names it; otherwise the generic caught-type refusal is located at the `try`. No emitted C or runtime semantics change.

**Probes** (`/tmp/rprobes`, head vs `/tmp/base`, both g and d builds):
- `p1,p2,p3,p6,p8,p9,p10,p11,p12,q1,q3,r3`: refused by name and located at the import; base refused with the old unlocated message. Acceptable named refusals.
- `p4,p5,p7,q2,q10,r2,s2`: same named refusal / same output as base (local-import, TryStar, class-body, generic-type paths unchanged).
- `q4,q5`: import only in `else`/`finally` and `import math` guarded: generic located refusal, as intended.
- `p5,q10,r2,r4,t1`: accepted programs (imports under `except Exception`/`OSError`, plain imports) identical to CPython on both builds; values through arg, attribute, dict and list verified.
- `q7,q8,q6`: plain `import math, html`, `html.escape`, `except*` identical to base (pre-existing).
- `r1`: nested generic caught-type located at `2:5`.
- For `r4`, `--debug-dir` `program.c` is byte-identical to base (only temp paths in `native_report.json` differ).
- No speed check needed: no emitted C or hot-path code changed.

**Tests:** `test_ail_pre52`, `test_ail_safetynet` — 2 modules, 0 failed (98 s); also `test_ail_files`, `test_ail_corpus_findings3` — 0 failed (163 s). `update_manifest.py --check` exit 0; commit trailer correct.

**Report claims:** first unlocated refusal reproduced and fixed — verified; import named/located at 2:5/3:9/4:13 — verified; `ModuleNotFoundError` same — verified; generic caught type located — verified; "second case (`import math, html` unused) already matches" — verified; manifest/tests/trailer — verified.

**Pre-existing (identical on base):** `html.escape` not published; `except*`; class-body `try`; local module imported in a `try`; plain two-module imports.

**Unverified:** exact original errmsg3 program (`import of 'math, html'` single-string wording no longer exists; new output quotes names separately); full suite (not run by design).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1001643, "input": 44301, "output": 5260, "reasoning": 12306, "cache.write": 0, "cache.read": 939776}]
    tool time: bash 7.0 min
        165s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_fin
        100s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_safetynet 
         36s bash   date; cd /tmp/rprobes; for p in p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | grep -E 'cp
         36s bash   date; cd /tmp/rprobes; for p in p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail
         29s bash   date; cd /tmp/rprobes; for p in q*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail
         20s bash   cd /tmp/rprobes; for p in q3.py q6.py q8.py; do echo "===== $p HEAD"; bash ~/tools/cmp.sh "$p" /home/runner/wo
         13s bash   cd /tmp/rprobes && cat > s1.py <<'EOF' def main():     try:         import html     except ImportError:       
          9s bash   cd /tmp/rprobes && cat > r1.py <<'EOF' def f():     try:         x = 1     except ImportError:         return 

FINAL VERDICT: ACCEPT  2026-10-24T04:04:21Z
