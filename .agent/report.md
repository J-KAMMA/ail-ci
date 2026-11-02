# job job-decexact2-11020914  started 2026-11-02T00:17:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `918fa9a` on `job-decexact2-11020914`.

**What broke:** `test_documented_differences` still expected CPython’s exact `int("9" * 30)`. Ints are int64 by default (exact mode opt-in), so the test now checks the declared stop: both builds exit 1, print nothing, and report `OverflowError: integer overflow in int() … --exact-int`. Non-BMP handling unchanged.

**Tests:** 5/5 modules pass in 847s: `test_ail_hostile_input`, `test_ail_int64_default`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Probes (`/tmp/probes`):**
- `hostile_int64_parse`, `_arg`, `_list`, `_attr`, `_dict`: both builds stop by name with the int64 `OverflowError`.
- `hostile_int64_boundary`: matches CPython on both builds.
- Exact mode: `_arg`, `_attr`, `_dict`, `_boundary` match CPython; `_parse`/`_list` still stop by name on the direct typed route (pre-existing, compiler unchanged).

`tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2626922, "input": 108186, "output": 6748, "reasoning": 10996, "cache.write": 0, "cache.read": 2500992}]
    tool time: bash 21.0 min
        849s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_hostile_input test_ail_int64_de
        341s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_hostile_input 2>&1 | tail -80
         25s bash   cd /tmp/probes && export AIL_EXACT_INT=1; for p in hostile_int64_parse hostile_int64_arg hostile_int64_list ho
         18s bash   cd /tmp/probes && printf '%s\n' '999999999999999999999999999999' > big.txt && cat > hostile_int64_parse.py <<'
          9s bash   cd /tmp/probes && for p in hostile_int64_parse hostile_int64_arg hostile_int64_list hostile_int64_attr hostile
          7s bash   cd /tmp/probes && for p in hostile_int64_parse hostile_int64_arg hostile_int64_list hostile_int64_attr hostile
          7s bash   cd /tmp/probes && for i in 1 2; do echo run$i; AIL_EXACT_INT=1 bash ~/tools/cmp.sh /tmp/probes/hostile_int64_p
          1s bash   git show --stat HEAD && echo === && git show HEAD -- AIL_CURRENT | head -300

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Edits `AIL_CURRENT/test_ail_hostile_input.py:316-325` so `test_documented_differences` expects the declared int64 stop for `int("9"*30)` on both builds (exit 1, empty stdout, `OverflowError: integer overflow in int()` + `--exact-int`) instead of comparing with CPython's exact bigint. Adds a DEVLOG entry and updates the manifest hash. No compiler/runtime code changed.

**Probes** (`/tmp/rprobes`, plus the worker's `/tmp/probes` re-run):
- `safe_dynamic.py`: dynamic 30 nines through `int()` inside `try/except`; both builds exit 1, stdout empty, stderr has the declared `OverflowError ... --exact-int`; CPython exits 0 printing the number. This is the declared int64 difference and matches the edited test.
- `boundary.py`: int64 min/max, `+7`, `1_000` match CPython on both builds.
- `arg.py`, `list_item.py`, `attr_dict.py` (dynamic values): both builds exit 1 with the declared message; literal forms are refused by name. Allowed.
- Worker's `hostile_int64_{parse,arg,list,attr,dict}`: same as above; `hostile_int64_boundary`: matches CPython on both.
- Exact mode (`AIL_EXACT_INT=1`): `arg`/`attr`/`dict`/`boundary` match CPython on both; `parse`/`list` match on the general path but the **default typed build** exits 1 with the runtime `OverflowError`. Pre-existing relative to `work`; the report's "stop by name" is imprecise (it is a run-time stop, not a compile-time refusal).

**Tests on HEAD (`-j 2`):**
- `test_ail_hostile_input` ok 340.1s, `test_ail_safetynet` ok 179.9s.
- `test_ail_int64_default` ok, `test_ail_files` ok, `test_ail_corpus_findings3` ok (575s batch).
- `tools/update_manifest.py --check` exit 0.

**Claims:** all verified: the edited test passes, the compiler is untouched, 5/5 required modules pass, probes show the declared stop and boundary parity, non-BMP handling still passes, manifest check passes.

**Pre-existing:** typed exact-mode `int()` of dynamic out-of-int64 text still stops (identical on `work`; unrelated to this test-only diff). No C-identity comparison needed because no compiler/runtime file is touched.

**Unverified:** none material.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 917690, "input": 65579, "output": 3405, "reasoning": 13378, "cache.write": 0, "cache.read": 835328}]
    tool time: bash 16.4 min
        577s bash   date; python3 tools/par_check.py -j 2 test_ail_int64_default test_ail_files test_ail_corpus_findings3 2>&1 | t
        341s bash   date; python3 tools/par_check.py -j 2 test_ail_hostile_input test_ail_safetynet 2>&1 | tail -40; date
         25s bash   for p in hostile_int64_parse hostile_int64_arg hostile_int64_list hostile_int64_attr hostile_int64_dict hostil
         20s bash   for p in /tmp/probes/hostile_int64_parse /tmp/probes/hostile_int64_arg /tmp/probes/hostile_int64_list /tmp/pro
         17s bash   cat > /tmp/rprobes/safe_dynamic.py <<'EOF' import sys  def safe(label, fn):     try:         print(label, repr
          5s bash   mkdir -p /tmp/rprobes; cat > /tmp/rprobes/safe_wrap.py <<'EOF' def safe(label, fn):     try:         print(lab
          0s bash   python3 tools/update_manifest.py --check; echo "manifest exit $?"
          0s bash   git branch -a; echo ===; git tag | head; echo ===; git rev-parse work HEAD; git log --oneline work..HEAD; echo

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T02:15:12Z
