# job job-std_shlex-11011956  started 2026-11-01T10:57:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects in `AIL_CURRENT/stdlib/shlex.py`:

- `split(None)` now raises `ValueError: s argument must not be None`.
- `quote` uses truthiness, so `quote(None)`, `quote(0)`, and `join([None])` return `''`.
- `lex.source` is now `None`.

Probes (`/tmp/probes/shlex_none_split.py`, `shlex_none_quote.py`, `shlex_source.py`, `shlex_quote_edges.py`) all match CPython on both builds.

Tests on final commit `d398187`: `test_ail_std_shlex`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` exits 0. No compiler/runtime changes, so `lab/compare` C output is unaffected.
[cost $0.0000, opencode tokens {"total": 352702, "input": 26544, "output": 2930, "reasoning": 2716, "cache.write": 0, "cache.read": 320512}]
    tool time: bash 15.0 min, edit 0.0 min
        424s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_std_shlex test_ail_safetynet test_a
        262s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3
        167s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_std_shlex test_ail_safetynet && cd 
         44s bash   mkdir -p /tmp/probes && cat > /tmp/probes/shlex_none_split.py <<'PY' import shlex try:     print(shlex.split(N
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "check exit $?"; git status
          0s bash   git status && git log --oneline -10 && ls
          0s bash   sed -n '1,40p' DEVLOG.md; echo ---; git show --stat --oneline HEAD; echo ---; git log --oneline -5
          0s bash   git add AIL_CURRENT/stdlib/shlex.py DEVLOG.md && git commit -m "shlex: match CPython for None args and source 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2 — `work..HEAD` (d398187)

**What the change really does:** in `AIL_CURRENT/stdlib/shlex.py`, `quote()` now uses `if not s`, the lexer's `source` starts as `None`, and `split()` rejects `None` with CPython's `ValueError`. Plus a DEVLOG entry. Matches the report exactly.

**Claims checked**
- `split(None)` → `ValueError: s argument must not be None`: verified (p1, both builds).
- `quote(None)`, `quote(0)`, `join([None])` → `''`: verified (p2, worker's `shlex_none_quote`, `shlex_quote_edges`, both builds).
- `lex.source is None` (with and without `infile`, and across push/pop): verified (p3, p5, worker's `shlex_source`, both builds).
- No compiler/runtime change; `lab/compare` C unaffected: verified (`git diff --stat` is only `shlex.py` + `DEVLOG.md`).
- Tests + manifest: verified — `test_ail_std_shlex`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (4/4, 347s); `update_manifest.py --check` exits 0.

**My probes (all match CPython on both builds)**
`p1_split_none`, `p2_quote_none` (None/0/0.0/False/[]/strings, join variants), `p3_source` (push/pop), `p4_quote_unicode`, `p5_lex_source_attr`. `p6b_split_types` also matches on the cases that matter; the non-str `split(0)`/`split([])` TypeErrors are identical on the base (pre-existing).

**Pre-existing (not caused):** `split(<non-str>)` error type/message differs from CPython; debug-mode `push_source`/`pop_source`/`raw token=EOF` wording; `iter(user_obj) is user_obj` false. All identical on base.

**Unverified:** full suite (by instruction); `quote([1])`-style truthy non-str input.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 289119, "input": 18903, "output": 3341, "reasoning": 3835, "cache.write": 0, "cache.read": 263040}]
    tool time: bash 8.4 min
        348s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         42s bash   cd /tmp/probes; for p in shlex_none_split shlex_none_quote shlex_source shlex_quote_edges; do echo "===== $p";
         31s bash   cd /tmp/rprobes; for p in p1_split_none p2_quote_none p3_source; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/
         28s bash   cd /tmp/rprobes cat > p4_quote_unicode.py <<'PY' import shlex vals = ["\u00e9", "\u00df", "a\u00e9", "a\nb", "
         26s bash   cd /tmp/rprobes; echo BASE; bash ~/tools/cmp.sh /tmp/rprobes/p6b_split_types.py /tmp/base
         25s bash   cd /tmp/rprobes cat > p6b_split_types.py <<'PY' import shlex for v in [0, 1, False, True, [], [""], b"a b"]:  
          3s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/ccmp && mkdir -p /tmp/ccmp/head /tmp/ccmp/base; ok=1; for f in
          0s bash   git worktree add /tmp/base work 2>&1 | tail -2; ls ~/tools

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T12:38:13Z
