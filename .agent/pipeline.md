# job job-rbfuzz4-10240913  started 2026-10-24T00:13:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied fuzz4 on top of the current tree (commit `9755ff2`), keeping both sides' fixes: `pop`/`setdefault` one-hash plus stored-hash `update`/`copy`/`popitem`/`dict(d)`, and two-phase dict/set literal evaluation.

- `tools/diff_ids.py` does not exist in this snapshot; `tools/update_manifest.py` ran and `--check` exits 0.
- Tests: `test_ail_fuzz4`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (4 modules, 0 failed); extra targeted `test_ail_builtin_maps`, `test_ail_dict_delete`, `test_ail_dict_upsert`, `test_ail_int_dict_set`, `test_ail_sets_general` (0 failed).
- Probes (all matched CPython stdout/exit on both `g` and `d` builds): `hash_methods`, `empty_pop`, `literal_order`, `dict_literals`, `set_literals`, `boundary_keys`, `indirect_keys`.
- Updated `DEVLOG.md` (2026-10-24) and `DIFFERENCES.md` with `C?-job-rbfuzz4-10240913-{1..5}`. No push.
[cost $0.0000, opencode tokens {"total": 1332194, "input": 98899, "output": 9757, "reasoning": 4338, "cache.write": 0, "cache.read": 1219200}]
    tool time: bash 11.3 min
        369s bash   timeout 1200 python3 tools/par_check.py -j 2 test_ail_fuzz4 test_ail_safetynet test_ail_files test_ail_corpus_
        191s bash   timeout 1200 python3 tools/par_check.py -j 2 test_ail_builtin_maps test_ail_dict_delete test_ail_dict_upsert t
         48s bash   for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; timeout 600 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | 
         33s bash   for p in /tmp/probes/*.py; do echo "===== $p"; timeout 600 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E "cpy
         20s bash   cat > /tmp/probes/boundary_keys.py <<'PY' def main():     d = {7: 1, -1: 2, 2**62: 3}     print(d.pop(-1), d.s
          6s bash   cat > /tmp/probes/boundary_keys.py <<'PY' def through_arg(x, d):     return d.pop(x, "miss")  class Holder:   
          6s bash   cat > /tmp/probes/boundary_keys.py <<'PY' def through_arg(x, d):     return d.pop(x, "miss")  class Holder:   
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-fuzz4-10220602 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `job-rbfuzz4-10240913` (HEAD `9755ff2`, base worktree `0275b48` at `/tmp/base`)

**Diff fidelity.** Compared `work..HEAD` against the fetched accepted diff (`00067cf..FETCH_HEAD`). The only differences are the expected conflict adaptations: `ail_raise(...)` replaced by this tree's `ail_raise_key_arg(...)`, plus DEVLOG/DIFFERENCES appended to existing files and MANIFEST regenerated. Re-application is faithful.

**Probes** (HEAD, both `g` and `d`, stdout+exit vs CPython 3.12):
- `hash_methods`, `literal_phase`, `set_starred`, `struct_maps` (40–55 colliding user keys, deletes, copy/update/dict/pop/popitem/setdefault), `mut_iter`, `pop_alias`: all match.
- Worker's 7 probes (`hash_methods`, `empty_pop`, `literal_order`, `dict_literals`, `set_literals`, `boundary_keys`, `indirect_keys`): all match.
- `key_errors`: named compile refusal on both HEAD and base (mixed-type inference), acceptable.
- `no_feature`: generated `program.c` is byte-identical to base (0 diff lines).
- `stored_hash` / `edge_maps`: values, order, hashes and exit match; only extra user `__eq__` calls remain in update/update-self/dict(d). Base differs in the same area too (with extra `__hash__` calls as well); this is the open, documented DIFFERENCES row #4 carried from the accepted change, not a regression of the re-application.

**Tests on final commit:** `test_ail_fuzz4 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 0 failed (286s). Extra: `test_ail_builtin_maps test_ail_dict_delete test_ail_dict_upsert test_ail_int_dict_set test_ail_sets_general` → 0 failed (177s).

**Claim checks.** Faithful re-apply: verified. `tools/diff_ids.py` absent: verified (only `codegen_diff.py`, `update_manifest.py`). `update_manifest.py --check` exits 0: verified. Test results: verified. Seven probes match: verified. DEVLOG/DIFFERENCES IDs `C?-job-rbfuzz4-10240913-{1..5}` and no push: verified. The DEVLOG's inherited "240 generated programs / 8 probes" claim is not evidenced here (7 probe files exist): unverified.

**Speed.** `perf_event_open` is denied in this runner, so `icount` could not run. As a fallback, 300 runs of `g25_020` and `g14_026` (`d` and `g`) gave 0.24–0.28s on HEAD vs 0.24–0.27s on base: no measurable change.

**Pre-existing/documented.** Reserved-hash `__eq__` call-count differences (DIFFERENCES #4) and the declared mutation-during-iteration rules (#3) remain; both are carried by the accepted change and also differ on base.

**Unverified.** Instruction counts; the inherited 240-program fuzz claim.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1653442, "input": 60593, "output": 24386, "reasoning": 2511, "cache.write": 0, "cache.read": 1565952}]
    tool time: bash 9.0 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_buil
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         47s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; timeout 300 b
         41s bash   cd /tmp && rm -rf perf && mkdir perf && cd perf && for f in g25_020 g14_026 g14_040; do cp ~/corpus/gdev/$f.py
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) HEAD"; timeout
         16s bash   cat > /tmp/rprobes/edge_maps.py <<'PY' class K:     def __init__(self, v):         self.v = v     def __hash__
         15s bash   cd /tmp && python3 - <<'PY' p='/tmp/rprobes/edge_maps.py' s=open(p).read() s=s.replace('print("pop", c.pop(ks[
         15s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/edge_maps.py "$PWD" 2>&1 | tail -30 > /

FINAL VERDICT: ACCEPT  2026-10-24T00:42:51Z
