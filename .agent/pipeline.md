# job job-fz208-11010638  started 2026-10-31T21:38:59Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `7b4c450` on `job-fz208-11010638`.

- Cause: negative NaN reached `snprintf("%.*f")` in `ail_fmt_spec_float` (`cruntime.py:9003`) and both `ail_obj_format` paths (`:10823`, `:17688`); glibc emitted `-nan`. All now pad literal `nan`.
- Probes: `p_min.py`, `p_nanfmt.py`, `p_nanfmt_args.py`, `p_nanfmt_bound.py` — all match CPython on default/general builds and cover both NaN signs, widths, fill/alignment, argument/list/attribute/dict values, infinity, and `-0.0`.
- Original `fz208.py`: line 29 `NAN` mismatch is gone. Remaining separate difference starts at line 42: AIL stops at the later `h0`/`h2` subtraction with `OverflowError: integer overflow in - (ints are 64-bit; --exact-int gives exact ints)`, while CPython continues. No other differences observed.
- Final-commit tests all pass: `test_ail_fz208` 3, `test_ail_fuzz46` 1, `test_ail_pre132` 4, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skip), `test_ail_corpus_findings3` 2.
- Manifest check passed; only unrelated untracked `.agent/pipeline.md` remains. No push performed.
[cost $0.0000, opencode tokens {"total": 6551834, "input": 226209, "output": 14611, "reasoning": 22118, "cache.write": 0, "cache.read": 6288896}]
    tool time: bash 16.5 min
        559s bash   set -o pipefail for m in test_ail_fuzz46 test_ail_pre132 test_ail_safetynet test_ail_files test_ail_corpus_fin
        263s bash   set -o pipefail for m in test_ail_fz208 test_ail_fuzz46 test_ail_pre132 test_ail_safetynet test_ail_files test
         29s bash   mkdir -p /tmp/probes && python3 - <<'PY' from pathlib import Path t=Path('/home/runner/work/_temp/t1/work0.md'
         28s bash   set -o pipefail bash ~/tools/cmp.sh /tmp/probes/fz208.py "$PWD" > /tmp/probes/final_cmp_fz208.log 2>&1; rc=$? 
         28s bash   bash ~/tools/cmp.sh /tmp/probes/fz208.py $PWD > /tmp/probes/fz208.after 2>&1; grep -E "cpython exit|same stdou
         22s bash   python3 -B AIL_CURRENT/test_ail_fz208.py -v
         19s bash   cat > /tmp/probes/p_nanfmt_bound.py <<'PY' class S:     def __init__(self, v):         self.v = v   def mk(): 
         19s bash   for f in /tmp/probes/p_min.py /tmp/probes/p_nanfmt.py /tmp/probes/p_nanfmt_args.py /tmp/probes/p_nanfmt_bound.

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a `v != v` early return that pads the literal `nan` in `ail_fmt_spec_float` (cruntime.py:9003) and both `ail_obj_format` paths (cruntime.py:10823, :17688); adds `test_ail_fz208.py`, DEVLOG/DIFFERENCES rows.

**Claims**
- fz208 line 29 `-NAN` is fixed: verified (HEAD diff now starts at line 42).
- Remaining fz208 int64 `-` overflow is pre-existing: verified (base stops at the same line 41 with the same `int_overflow`).
- `test_ail_fz208` (3) and `test_ail_safetynet` (5) pass on HEAD: verified. fuzz46/pre132/files/corpus claims and manifest check: unverified.
- Probes cover both NaN signs, widths, fill/alignment, arg/list/attr/dict, inf, `-0.0`: verified with `p_nanpad.py`/`p_vals.py`; they do not cover explicit sign flags.

**Defects**
1. The new general-path early return bypasses `f.sign`/`ail__apply_sign`, so an explicit `+`/space flag on NaN is lost. Base general build was correct for positive NaN; HEAD regresses.
   Probe `/tmp/rprobes/p_min_sign.py`:
   ```python
   p = float('nan')
   print(f'{p:+f}|{p: f}|{p:+08.2f}|{p:+8.2f}')
   print(f'{-p:+f}|{-p: f}')
   ```
   CPython and HEAD default build: `+nan| nan|+0000nan|    +nan` / `+nan| nan`
   HEAD general build (`AIL_UNIFIED_FORCE=1`): `nan|nan|00000nan|     nan` / `nan|nan`
   Base general build: first line matched CPython (regression is new); second line was `-nan|-nan` (pre-existing wrong).

**Pre-existing:** `format(float('nan'), ' 08.2f')` gives `0000 nan` on base vs CPython ` 0000nan`; fz208 later int64 overflow.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 800246, "input": 75950, "output": 3637, "reasoning": 9107, "cache.write": 0, "cache.read": 711552}]
    tool time: bash 4.4 min
        170s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz208 test_ail_safetynet 2>&1 | tail -30
         28s bash   bash ~/tools/cmp.sh /tmp/probes/fz208.py $PWD 2>&1 | tail -40; date
         28s bash   bash ~/tools/cmp.sh /tmp/probes/fz208.py /tmp/base > /tmp/fz208_base.log 2>&1; d=$(grep -o '/tmp/cmp.*' /tmp/f
         15s bash   for p in p_sign p_nanpad p_vals p_plain; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py $PWD;
         10s bash   cat > /tmp/rprobes/p_pos_sign.py <<'PY' p = float('nan') m = -float('nan') print(f'{p:+f}|{p: f}|{p:+08.2f}|{p
          9s bash   for p in p_sign p_vals; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base; done 2>&1 |
          5s bash   cat > /tmp/rprobes/p_min_sign.py <<'PY' p = float('nan') print(f'{p:+f}|{p: f}|{p:+08.2f}|{p:+8.2f}') print(f'
          3s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_min_sign.py $PWD 2>&1 | tail -30

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect and committed as `54a1295`.

- General-path `ail_obj_format` NaN arm now applies `f.sign` via `ail__apply_sign` before padding; `ail__pad` treats a leading space as a sign under `=` zero padding.
- `p_min_sign` now matches CPython on both builds. Also matched: `p_nansign`, `p_nansign_widths`, `p_nansign_upper` (both NaN signs, `+`/space, widths 0–9, fill/alignment/zero, f-string/`format()`/`%`, inf, `-0.0`, via arg/list/attr/dict).
- fz208 line 29 `-NAN` is fixed; remaining diff starts at line 42, the pre-existing int64 `-` overflow.
- Added `test_explicit_sign_flags` to `test_ail_fz208.py`.
- Final tests: `test_ail_fz208`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes.

Other differences: none observed beyond the pre-existing fz208 int64 overflow.
[cost $0.0000, opencode tokens {"total": 1494901, "input": 108618, "output": 6176, "reasoning": 7051, "cache.write": 0, "cache.read": 1373056}]
    tool time: bash 7.6 min, edit 0.0 min
        370s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz208 test_ail_safetynet test_ail_files test_ail
         36s bash   cd AIL_CURRENT && python3 -B test_ail_fz208.py 2>&1 | tail -60
         28s bash   bash ~/tools/cmp.sh /tmp/probes/fz208.py $PWD 2>&1 | tail -30
         15s bash   cat > /tmp/probes/p_nansign.py <<'PY' p = float('nan') n = float('-nan')  def show(tag, v):     print(tag, f'{
          3s bash   cat > /tmp/probes/p_min_sign.py <<'PY' p = float('nan') print(f'{p:+f}|{p: f}|{p:+08.2f}|{p:+8.2f}') print(f'{
          3s bash   bash ~/tools/cmp.sh /tmp/probes/p_min_sign.py $PWD 2>&1 | tail -40
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo rc=$?; git status --short
          0s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz208 2>&1 | tail -40

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the diff does:** adds a NaN early-return to the fixed-point formatters so `nan`/`NAN` never carries glibc's `-` sign, applies the parsed `+`/space sign in the general path's `ail_obj_format` NaN arm, and treats a leading space as a sign under `=` zero padding.

**Verified claims**
- `ail_obj_format` NaN arm now applies `f.sign` via `ail__apply_sign`; `ail__pad` space-sign change present in diff — verified.
- `p_min_sign`, `p_nansign`, `p_nansign_widths`, `p_nansign_upper`, `p_nanfmt_args`, `p_nanfmt_bound` all match CPython on default and general builds; base fails the corresponding NaN cases.
- fz208: lines 29/35 now match CPython on both builds; base still prints `-NAN`. Remaining output stops at line 42 with the pre-existing int64 `-` overflow; base stops there identically.
- Added `test_explicit_sign_flags`; registration via `tests.d/`; manifest `--check` rc=0 — verified.

**My probes (HEAD, default + general)**
- `p_signs`, `p_typed_nan`, `p_nan_nosign`, `p_dotformat`, `p_finite`, `p_ints`, `p_plain`, `p_nonetype`: all match CPython. Base fails the NaN sign/space cases in `p_signs` and `p_typed_nan`.
- `p_plain`: generated `program.c` via `--debug-dir` is byte-identical to base.
- `p_group`: NaN/inf with grouping+zero differ from CPython, but base output is identical, so pre-existing.

**Tests:** `test_ail_fz208`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.

**Pre-existing**
- fz208 int64 `-` overflow after line 41 (identical on base).
- Grouping + zero padding on NaN/inf (`format(v, '08,.2f')` etc.) gives grouped zeros in AIL vs plain zeros in CPython; identical on base.

**Unverified**
- Instruction counts: `tools/icount.c` builds, but `perf_event_open` is denied in this runner. No hot formatting loop was changed materially; g25_032 binary size is identical before/after.
- Legacy `AIL_GENERAL=v1` signed-NaN path was not required by the task; its no-sign NaN case is fixed on HEAD, signed cases were not separately assessed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3840181, "input": 66030, "output": 11770, "reasoning": 23629, "cache.write": 0, "cache.read": 3738752}]
    tool time: bash 10.3 min, write 0.0 min
        260s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 2>&1 | tai
        170s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz208 test_ail_safetynet 2>&1 | tail -30
         55s bash   date; echo "=== HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/fz208.py $PWD 2>&1 | grep -v '^dir '; echo "=== BASE";
         37s bash   date; for p in p_min p_min_sign p_nansign p_nansign_widths p_nansign_upper p_nanfmt p_nanfmt_args p_nanfmt_bou
         22s bash   date; for p in p_signs p_group p_finite p_ints p_plain; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rpro
         19s bash   date; for wt in "$PWD" /tmp/base; do echo "===== $wt"; bash ~/tools/cmp.sh /tmp/rprobes/p_dotformat.py $wt 2>&
         16s bash   date; for p in p_typed_nan p_nan_nosign; do for wt in "$PWD" /tmp/base; do echo "===== $p $wt"; bash ~/tools/c
         11s bash   date; for p in p_group p_signs; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base 2>&1

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-31T23:47:00Z
