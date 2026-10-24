# job job-rbfuzz28-10240912  started 2026-10-24T00:12:41Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `5c1ab4c` on `job-rbfuzz28-10240912`.

- Ported fuzz28: class attributes are still evaluated once into shared slots, and readable computed attributes still work; a class-attribute read through the class is refused by name only when its value cannot be evaluated.
- Added `test_ail_fuzz28.py`, registered it, updated DIFFERENCES/DEVLOG, refreshed and checked `MANIFEST.json`.
- `tools/diff_ids.py` does not exist in this tree (also absent from the fetched branch), so it could not be run.

Tests on the final commit: 51 run, 50 passed, 1 skipped (fuzz28, fuzz29, dunders, check, safetynet, files, corpus_findings3). `update_manifest.py --check` passes.

Probes (`g`/`d`):
- Match CPython both builds: `class_types`, `class_comp_const`, `class_literal`, `class_computed`, `class_instance`, `class_shadow`, `class_inherited`, `class_contexts`, `class_comp_module`.
- Refused by name both builds: `class_read`, `class_arith`, `class_comp_unread`, `class_comp_set_dict_classvar`.
[cost $0.0000, opencode tokens {"total": 2249791, "input": 55708, "output": 8147, "reasoning": 13776, "cache.write": 0, "cache.read": 2172160}]
    tool time: bash 16.7 min, edit 0.0 min
        455s bash   cd AIL_CURRENT && python3 -m unittest test_ail_fuzz28 test_ail_fuzz29 test_ail_dunders test_ail_check test_ail
        404s bash   cd AIL_CURRENT && python3 -m unittest test_ail_fuzz28 test_ail_fuzz29 test_ail_dunders test_ail_check test_ail
         50s bash   cat > /tmp/probes/class_types.py <<'EOF' class C:     bs = b"ab"     empty = ""     t = ()     lst = []     d 
         28s bash   cat > /tmp/probes/class_instance.py <<'EOF' class C:     x = 3     ys = [i for i in range(3)]     zs = {i: i f
         20s bash   for p in class_read class_def_only class_comp_const class_literal class_computed class_arith; do echo "=== $p"
         14s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_fuzz28 2>&1 | tail -40
         10s bash   cat > /tmp/probes/class_arith.py <<'EOF' class C:     x = 3     y = x + 1     s = "a" + "b" print(C.y, C.s) EO
          4s bash   mkdir -p /tmp/probes && cat > /tmp/probes/class_read.py <<'EOF' class C:     x = 3     ys = [i for i in range(

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Review of `5c1ab4c` (job-rbfuzz28-10240912)**

Diff: 6 files. Ports fuzz28 by adding `_class_attr_through_class_refusal`, refusing a non-literal class-attribute read through the class only when evaluation fails, and mapping class-definition evaluation failures to that refusal. Test file is byte-identical to `FETCH_HEAD`; registered in `ail_check.MODULES`; DIFFERENCES/DEVLOG/MANIFEST updated.

Checks run:
- `par_check.py -j 2 test_ail_fuzz28 test_ail_fuzz29 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 5 modules, 0 failed (233s).
- `test_ail_check` → ok; `update_manifest.py --check` → RC 0; `git diff --check` clean.
- `tools/diff_ids.py` genuinely absent from both this tree and `FETCH_HEAD` (verified with `git ls-tree`).
- No-feature C unchanged: `program.c` for `p5_class_no_feature` and `p3_class_comp_listitem` is identical HEAD vs `/tmp/base` (only temp paths in `native_report.json` differ).

Report claims: all verified. Probes `class_types/comp_const/literal/computed/instance/shadow/inherited/contexts/comp_module` match CPython on both builds; `class_read/arith/comp_unread/comp_comp_set_dict_classvar` are refused by name on both. Report does not overclaim.

My probes beyond the worker's:
- Match CPython (g+d): `p3` (list item), `p4` (dict value), `p7` (module-name comprehension), `p9` (other class attr), `p10` (empty/negative), `p11` (mutation after class def; shared list), `p13` (attribute chain), `p14` (tuple/bytes/negative literals).
- Pre-existing (identical outcome on base, not caused by this change): `p15` class attr `y = x + 1` with class `x = 3` and module `x = 10` gives CPython `3 4`, both HEAD and base `3 11`; `p6`/`p8` instance-side comprehension using class-scope name are refused on both (HEAD names the read, base says `name 'x' is not defined`); `p12` class alias `D = C; D.ys` raises `AttributeError` on both; `p1`/`p2` refused on both (CPython NameError / nested class).
- Speed: generated C is identical on the changed success paths, so no runtime cost; icount was not run.

Unverified: none material. Verdict follows the rule that base-identical differences do not block.

VERDICT: ACCEPT
[cost $0.0288, opencode tokens {"total": 828797, "input": 88289, "output": 5457, "reasoning": 16843, "cache.write": 0, "cache.read": 718208}]
    tool time: bash 7.2 min
        234s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test
         56s bash   cd /tmp/rprobes && cat > p9_class_attr_source.py <<'EOF' class D:     n = 3     m = 2 class C:     ys = [i * D
         53s bash   cd /tmp/probes && for p in *.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ail
         34s bash   cd /tmp/rprobes && for p in p1_class_comp_scope p2_class_comp_arg p3_class_comp_listitem p4_class_comp_dict p5
         24s bash   cd /tmp/rprobes && cat > p15_shadow_global_arith.py <<'EOF' x = 10 class C:     x = 3     y = x + 1 print(C.x,
         19s bash   cd /tmp/rprobes && cat > p6_instance_classname.py <<'EOF' class C:     x = 3     ys = [i for i in range(x)] o 
          7s bash   cd /tmp && rm -rf cdh cdb && mkdir -p cdh cdb && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=c
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p5_class_no_feature.py /home/runner/work/ail-ci/ail-ci >/d

FINAL VERDICT: ACCEPT  2026-10-24T00:55:01Z
