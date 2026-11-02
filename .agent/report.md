# job job-prog15-11021347  started 2026-11-02T04:48:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `82fce75`.

**What I found/fixed:** no review defects were named (review 1 skipped). Probing the pair-target comprehension path found a silent difference: `_listcomp_pair_into_temp` registered a str pair element in `ctx.onecp`/`len1_names`, so `_one_cp` claimed length 1 and `if v != "":` kept empty strings. Pair elements are full `ail_str` values, so the registration is gone; string inequality now uses `ail_str_eq`. Added `enum_nonempty`/`zip_nonempty` regression cases.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `p1_enum` enumerate int/float/str, slices, negatives, dataclass field, list item, dict value — match
- `p2_zip_items` zip int/float/str, unannotated int/str-keyed `.items()`, args/dict values — match
- `p3_big` near-int64 values — match; `p3_overflow` stops loudly (`OverflowError`, rc 1, no wrap)
- `p4_alias` aliasing/mutation — match
- `p5_strkey` zip str key/value — match
- `p6`/`p6b` bytes-keyed dict fallback — match CPython
- `p7`/`p7b` str keys/values, list item, attribute, dict value — match (p7 has unrelated annotation refusals)
- `p8_cond` the bug probe (empty-string conditions) — match after fix
- `p9_keycond` str/float/int key conditions and `.items()` — match
- `p10_nonzero` enumerate from nonzero range/slice — match

**Tests:** `test_ail_prog15`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_typedreach1`, `test_ail_typedreach2` all OK. `update_manifest.py --check` clean. AST scan of the 10 `lab/compare` sources showed the new pair path is not emitted there; `scar_life` is refused as before. Follow-ups in `lab/progfix/prog15.md` unchanged.
[cost $0.0000, opencode tokens {"total": 3112239, "input": 81509, "output": 13437, "reasoning": 15437, "cache.write": 0, "cache.read": 3001856}]
    tool time: bash 19.8 min, edit 0.0 min
        223s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tai
        178s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -15
        177s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -25
        125s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tai
        108s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_files.py 2>&1 | tail -25
         76s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/cmp10 && for t in ledger_bin scar_life term_rank; do echo 
         61s bash   cat > /tmp/probes/p3_big.py <<'EOF' def big(xs: list[int]) -> list[int]:     return [v * 2 for i, v in enumera
         46s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 AIL_CURRENT/test_ail_files.py 2>&1 | tail -15

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: prog15 fix (`82fce75`)

**What the change really does:** In `_listcomp_pair_into_temp`, stops registering the str element of an `enumerate`/`zip`/`.items()` pair target in `ctx.onecp`/`ctx.len1_names`, so full `ail_str` comparisons use `ail_str_eq`/`ail_str_cmp` instead of the one-code-point fast paths. Adds `enum_nonempty`/`zip_nonempty` regression cases. This matches the report.

**Probes** (typed-path flags verified by compiling without fallback; HEAD both builds vs CPython):
- `p8b_enum_typed` (11 conditions: `!= ""`, `== ""`, `== "a"`, `!= "ab"`, `== "ab"`, `< "b"`, `>= ""`, truthiness, literal-on-left) — TYPED, match; base differs on 7 of them. Verified.
- `p9_enum_direct` (result is the raw `v`, `!= ""`, `== "ab"`, `< "b"`, truthiness) — TYPED, match; base differs.
- `p2_zip_conds` (value/key conditions, multi-char, membership, empty/short zip) — TYPED, match; base differs.
- `p5_elt_ops` (upper/concat/`v[0]`/slice) — TYPED, match.
- `p1/p3/p4/p6/p7` (enum shifts, items keys, arg/field/item/slice paths, ord, flipped literals, alias-after) — match; these programs fall back to the general path, so they do not exercise the typed change.
- Worker probes `p1,p2,p3_big,p3_overflow,p4_alias,p5_strkey,p6,p6b,p7,p7b,p8,p9,p10` all match; `p3_overflow` exits 1 with `OverflowError` as the task requires.
- All 10 `lab/compare` sources: generated `program.c` byte-identical to base (only temp paths in `native_report.json` differ). Same for `g08_018`, `g02_000`, `g14_030` C; icount could not run (`perf_event_open: Permission denied`), but identical C rules out an instruction-count change there.

**Claims:** all verified except test_ail_files / test_ail_corpus_findings3 / typedreach1/2 (not re-run per review scope — unverified). `test_ail_prog15` + `test_ail_safetynet` pass; `update_manifest.py --check` clean.

**Pre-existing:** integer-overflow divergence from CPython is the task's intended loud-stop behaviour, unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1459540, "input": 55201, "output": 8899, "reasoning": 14448, "cache.write": 0, "cache.read": 1380992}]
    tool time: bash 7.9 min
        178s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pro
         85s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && ok=1; for t in berth_sim chain_relax echo_pa
         62s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p3_big p3_overflow p4_alias p5_strkey p6_bytesdict p6b_bytesite
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p8_cond p1_enum; do echo "===== BASE $p ====="; timeout 700 bas
         21s bash   cd /tmp/rprobes && python3 - <<'EOF' p='p1_enum_conds.py' s=open(p).read() s=s.replace('        ("nonempty_len
         21s bash   cd /home/runner/work/ail-ci/ail-ci && i=0; for p in /tmp/rprobes/*.py /tmp/probes/p8_cond.py /tmp/probes/p2_zi
         17s bash   cd /tmp && rm -rf gdh gdb && mkdir gdh gdb && for p in g08_018 g02_000 g14_030; do AIL_NO_CACHE=1 python3 /hom
         17s bash   cd /tmp && for p in g08_018 g02_000 g14_030; do src=$HOME/corpus/gdev/$p.py; AIL_NO_CACHE=1 python3 /home/runn

## full suite
test_ail_fuzz_findings

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `c5b7655`.

- Failure: `test_ail_fuzz_findings` expected `DICT_ALIAS_UNTYPED` to report the aliasing reason, but the typed path refused earlier with the str-keyed dict copy message.
- Fix: `aliasrefuse.refuse_instead` now treats the str/bytes-keyed copy refusal as a symptom when a real aliasing site exists, preserving the original refusal otherwise.
- Verified: `test_ail_fuzz_findings`, `test_ail_prog15`, `test_ail_refusal_messages`, `test_ail_ir_rulex`, `test_ail_str_find_alias`, and `test_ail_manifest_compiler` pass; manifest pins refreshed.
[cost $0.0000, opencode tokens {"total": 1072953, "input": 57178, "output": 3830, "reasoning": 3945, "cache.write": 0, "cache.read": 1008000}]
    tool time: bash 4.5 min
        136s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings 2>&1 | tail -100
         54s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings 2>&1 | tail -30
         40s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_refusal_messages test_ail_prog15 2>&1 | tail -30
         30s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_rulex 2>&1 | tail -30
          4s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings.FuzzFindings.test_refusal_reasons_are_the_real
          2s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_manifest_compiler 2>&1 | tail -20
          2s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_str_find_alias 2>&1 | tail -20
          1s bash   rm -rf /tmp/prev_ail && cp -a AIL_CURRENT /tmp/prev_ail && cd /home/runner/work/ail-ci/ail-ci && git show HEAD

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T07:58:17Z
