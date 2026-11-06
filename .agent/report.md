# job job-rbmailcap1-11061259  started 2026-11-06T04:00:21Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Re-applied the accepted `mailcap1` change on `job-rbmailcap1-11061259` and committed as `0a1e6731`.

- Files: bundled `AIL_CURRENT/stdlib/mailcap.py`, 10 `lab/stdlib/mailcap` programs, `test_ail_std_mailcap.py`, its `tests.d/` registration, DIFFERENCES row, DEVLOG entry, manifest entries.
- Conflicts: kept both sides' intent — the accepted removal of the `agent`/`opus` workflow input and Claude token handling (the current CR/LF strip belonged to that removed feature), and kept the current tree's newer DEVLOG entries alongside the mailcap entry.
- `tools/diff_ids.py` does not exist on this tree; `tools/update_manifest.py` ran and `--check` exits 0.
- Tests on the committed tree: `test_ail_std_mailcap` 2 OK (264 s), `test_ail_safetynet` 5 OK (183 s), `test_ail_files` OK (106 s), `test_ail_corpus_findings3` OK (238 s) — 4/4 modules, 0 failed.
- Probes with `~/tools/cmp.sh` on default and forced-general builds: `p1_find_unsafe.py`, `p2_findmatch.py`, `p3_subst.py`, `p4_values_via.py` — all matched CPython stdout and exit status (4/4).
- No push; untracked `.agent/pipeline.md` left alone.
[cost $0.0000, opencode tokens {"total": 1365918, "input": 77427, "output": 6425, "reasoning": 5650, "cache.write": 0, "cache.read": 1276416}]
    tool time: bash 9.8 min
        503s bash   python3 tools/par_check.py -j 2 test_ail_std_mailcap test_ail_safetynet test_ail_files test_ail_corpus_finding
         76s bash   for p in /tmp/probes/p1_find_unsafe.py /tmp/probes/p2_findmatch.py /tmp/probes/p3_subst.py /tmp/probes/p4_valu
          8s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-mailcap1-11060850 2>&1 | tail -20
          0s bash   python3 tools/update_manifest.py 2>&1 | tail -30; echo "exit=$?"; git status --short | head -40
          0s bash   python3 tools/update_manifest.py --check && git commit -q -m "job rbmailcap1: re-apply accepted mailcap1 chang
          0s bash   grep -rn "DEVLOG.md\|DIFFERENCES.md\|agent-worker.yml" AIL_CURRENT/manifest.d | head; echo ====; git diff AIL_
          0s bash   git diff --stat AIL_CURRENT/manifest.d; echo ====; python3 tools/update_manifest.py --check 2>&1 | tail -20; e
          0s bash   pwd && git status && git log --oneline -5 && ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Re-applies the accepted `mailcap1` change: adds bundled `AIL_CURRENT/stdlib/mailcap.py` (CPython 3.12 `mailcap` rewritten with an `re`-free `_find_unsafe`), 10 `lab/stdlib/mailcap` programs, `test_ail_std_mailcap.py` + `tests.d` registration, a DIFFERENCES row, DEVLOG entry, manifest entries, and removes the `agent`/`opus` input and Claude-token handling from `agent-worker.yml`. All source/test/lab/workflow files are byte-identical to `FETCH_HEAD` of `job-mailcap1-11060850`; only the DEVLOG entry and DIFFERENCES id/text are adapted.

**Probes** (`/tmp/rprobes`, default + forced-general):
- `p1b_chars.py` (codes 0..0xaf plus BMP samples via `subst %t`): both builds match CPython.
- `p2_sources.py` (filename/parameter through arg, dict, attribute, list item; safe/unsafe): match.
- `p3_edges.py` (CRLF, no trailing newline, EOF continuation, spaced keys, wildcard lookup, missing type, escapes): match.
- `p4_notest.py`: entry with `test=` — bundled raises `OSError`, CPython runs it. Declared in DIFFERENCES.
- `p5b_testnone.py`: CPython skips a `test=` entry whose `%t` substitution is unsafe and uses the next entry; bundled raises `OSError`. Covered by the declared “a `test=` field raises OSError”, but the module docstring’s line “a `test=` field that substitutes to None is skipped on both” is false (documentation nit only).
- Worker’s `/tmp/probes/p1..p4`: all 4 match CPython on both builds (claim verified).
- `p_nonbmp.py`: general-path `chr` non-BMP limit; same failure on base (`/tmp/base`), so pre-existing.
- Non-feature program compiled with `--debug-dir` on HEAD vs base: `program.c` byte-identical.

**Tests** on HEAD: `test_ail_std_mailcap` 262.5s ok, `test_ail_safetynet` 187.1s ok, `test_ail_files` 106.4s ok, `test_ail_corpus_findings3` 242.0s ok — 4/4, 0 failed.

**Claim check:** byte-identical re-apply verified; conflicts (Claude input removal, DEVLOG merge) verified; `tools/diff_ids.py` absent verified; `update_manifest.py --check` exits 0 verified; 4/4 tests and 4/4 probes verified; only untracked `.agent/pipeline.md` remains. “No push” unverified. `.agent/pipeline.sh` still mentions `claude.key`/`AIL_WORKER` but that file is outside the accepted diff and the branch is dead (`AIL_WORKER` unset → `auto`), so harmless.

Speed: not applicable — no compiler/runtime hot path touched.

Unverified: no push confirmation; no wider-suite run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1546015, "input": 72090, "output": 6713, "reasoning": 14924, "cache.write": 0, "cache.read": 1452288}]
    tool time: bash 12.2 min
        264s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_std_mailcap test_ail_safetyne
        243s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_finding
         85s bash   for p in /tmp/rprobes/p1_chars.py /tmp/rprobes/p2_sources.py /tmp/rprobes/p3_edges.py /tmp/rprobes/p4_notest.p
         75s bash   date; for p in /tmp/probes/p1_find_unsafe.py /tmp/probes/p2_findmatch.py /tmp/probes/p3_subst.py /tmp/probes/p
         20s bash   cat > /tmp/rprobes/p5_testnone.py <<'EOF' import mailcap caps = {"text/plain": [     {"view": "first %s", "tes
         19s bash   cat > /tmp/rprobes/p5b_testnone.py <<'EOF' import mailcap caps = {"text/plain;rm": [     {"view": "first %s", 
         19s bash   sed 's/, 0x10ffff//' /tmp/rprobes/p1_chars.py > /tmp/rprobes/p1b_chars.py; date; timeout 600 bash ~/tools/cmp.
          2s bash   mkdir -p /tmp/nomc; cat > /tmp/nomc/n.py <<'EOF' import sys def f(xs):     d = {"a": 1}     total = 0     for 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T05:55:42Z
