# job job-rbreex24-11020723  started 2026-11-01T22:28:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining defect.

**Fix:** `_literal_value` no longer trusts any `_AilT_*` name. It accepts the spelling only for module-level classes matching the tuple pass's record shape (`__init__` storing `f0, f1, ...`), and `_effect_free_annotation` uses the same set. User defs/classes named `_AilT_*` are now treated as ordinary code, so the module builds as a program and both builds match CPython.

**Probes** (`cmp.sh`, both builds, all match CPython):
- `p_ailt_def` (review probe: user `_AilT_evil` def + top-level call) — now prints `evil called 1`
- `p_ailt_class` (user `_AilT_evil` class with effectful `__init__`) — matches
- `p_ailt_def_i` (code-shaped user name `_AilT_i`) — matches
- `p_tuple_default`, `p_tuple_ann`, `p_tuple_const`, `p_empty_tuple` (legitimate surface records) — match

**Tests on final commit `f4c3605`:**
- `test_ail_reex24` 5 OK (added `ailt_user_names` regression case)
- `test_ail_safetynet` 5 OK
- `test_ail_files` 18 OK, 1 skipped
- `test_ail_corpus_findings3` 2 OK

`python3 tools/update_manifest.py --check` rc 0. Working tree clean except untracked `.agent/pipeline.md`. `tools/diff_ids.py` does not exist in this tree.
[cost $0.0000, opencode tokens {"total": 2350986, "input": 44298, "output": 10026, "reasoning": 13270, "cache.write": 0, "cache.read": 2283392}]
    tool time: bash 11.0 min, edit 0.0 min, read 0.0 min
        296s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -20 && echo "=== c
        172s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -6 && echo '=== co
        102s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_reex24.py 2>&1 | tail -20 && echo "=== file
         49s bash   cd /tmp/probes && for p in p_ailt_def p_ailt_class p_ailt_def_i p_tuple_default p_tuple_ann p_tuple_const p_em
         28s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_reex24.py 2>&1 | tail -20
         10s bash   cd /tmp/probes && for p in p_ailt_def p_ailt_class p_ailt_def_i p_tuple_default p_tuple_ann p_tuple_const p_em
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; git sta

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change really does (one line):** `_literal_value` and `_effect_free_annotation` no longer trust any `_AilT_*` spelling; they accept it only for module-level classes matching the surface's tuple-record shape (`__init__` that only stores `f0/fb0...`), and that set is threaded through the definitions-only/effect-free checks; adds the `ailt_user_names` regression case and a DEVLOG entry.

### Last review's defect
1. **`_literal_value` trusts any `_AilT_*` name — fixed.** Probe `p_ailt_def` (review probe):
   - HEAD: `g exit 0 / d exit 0`, both `same stdout`, CPython `evil called 1`.
   - Base (`/tmp/base`, work f7df35c): general prints, **default drops it** (`1d0 < evil called 1`) — reproduces the defect; HEAD fixes it.
   - `p_ailt_class` (effectful user class) likewise: HEAD both match, base default drops.

### Probes (all `cmp.sh`, both builds)
Match CPython: `p_ailt_def`, `p_ailt_class`, `p_ailt_def_i`, `p_ailt_record_user`, `p_ailt_record_nonliteral`, `p_ailt_empty_record`, `p_tuple_default`, `p_tuple_ann`, `p_tuple_const`, `p_empty_tuple`, `p_tup_bool`, `p_tup_nested`, `p_tup_bytes`, `p_tup_return`, `p_tup_many`, `p_tup_alias`.
Named refusal: `p_ailt_ann`, `p_ailt_default_call` (change-caused; base matched — acceptable named refusal), `p_ailt_record_evil_ann`, `p_ailt_collision`, `p_tup_class`, `p_tup_dict`, `p_tup_opt` (last four identical on base → pre-existing).
No-feature C: `p_no_feature` `--debug-dir` `program.c` byte-identical HEAD vs base (4363 lines).

### Claim checks
- Fix description (record-shape set, annotation uses same set) — **verified** (diff + `python_surface` output + probes).
- Probe list in report — **verified** (re-ran equivalents; all match or named-refuse).
- Tests on f4c3605: `test_ail_reex24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **verified** (`par_check -j 2`, all ok, 0 failed).
- `update_manifest.py --check` rc 0 — **verified**.
- Tree clean except untracked `.agent/pipeline.md` — **verified**.
- `tools/diff_ids.py` absent — **verified**.

### Change-caused but acceptable
- `p_ailt_ann` (user `_AilT_tag` class as annotation) and `p_ailt_default_call` (user `_AilT_*` def as a default) now get the named "runs code at load time" refusal where base matched. Named refusals are permitted; no crash or silent difference.

### Unverified
- The other 5 modules listed in the earlier report; full corpus; gdev instruction counts (compile-time AST-only change, no runtime hot path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2356667, "input": 44536, "output": 7422, "reasoning": 21445, "cache.write": 0, "cache.read": 2283264}]
    tool time: bash 5.7 min
        149s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_files test
        145s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_reex24 tes
         16s bash   cd /tmp/rprobes cat > p_tup_bool.py <<'EOF' def f(t: tuple[bool, int] = (True, 1)) -> int:     return 0 EOF ca
         14s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/*.py; do echo "===== $p ====="; timeout 30
          8s bash   cd /tmp/base && date && for p in p_ailt_def p_ailt_class p_ailt_ann p_ailt_default_call p_ailt_record_evil_ann
          2s bash   cd /tmp/rprobes cat > p_tup_alias.py <<'EOF' Pair = tuple[int, int]  def first(p: Pair) -> int:     return p[0
          2s bash   cd /tmp/base && bash ~/tools/cmp.sh /tmp/rprobes/p_ailt_default_call.py "$PWD" 2>&1 | tail -20
          2s bash   cd /tmp/base && date && for p in p_tup_dict p_tup_opt; do echo "===== $p ====="; timeout 300 bash ~/tools/cmp.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T00:08:35Z
