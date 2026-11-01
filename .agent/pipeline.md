# job job-std_pprint-11011616  started 2026-11-01T07:17:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `df4ae79` on `job-std_pprint-11011616`.

- **Programs:** 12/12 in `lab/stdlib/pprint` build on the default general path and match CPython 3.12 stdout/exit; also under `AIL_IR=1`. Typed path still refuses `import pprint` (recorded as follow-up).
- **Tests:** `test_ail_std_pprint`, `test_ail_safetynet` (5), `test_ail_files` (18, 1 skipped), `test_ail_corpus_findings3` (2): all OK on the final commit.
- **Manifest:** `python3 tools/update_manifest.py --check` exits 0.
- **Probes:** `pp_types`, `pp_sources`, `pp_stream`, `pp_errors`, `pp_numbers`, `pp_strings`, `pp_sets_deterministic` match CPython on both builds; `pp_star_refused` is refused by name.
- **lab/compare:** 7/10 build and generate byte-identical C before/after; `scar_life`, `tally_lang`, `tree_fold` refuse identically at base and head, so no C change.
[cost $0.0202, opencode tokens {"total": 1332023, "input": 72725, "output": 4218, "reasoning": 5032, "cache.write": 0, "cache.read": 1250048}]
    tool time: bash 15.3 min
        394s bash   rm -rf /tmp/base /tmp/ccmp && mkdir -p /tmp/base /tmp/ccmp && git archive HEAD AIL_CURRENT | tar -x -C /tmp/ba
        227s bash   for m in test_ail_safetynet test_ail_files test_ail_corpus_findings3 test_ail_genlib; do echo "== $m"; python3
        205s bash   for m in test_ail_std_pprint test_ail_safetynet test_ail_files test_ail_corpus_findings3; do echo "== $m"; pyt
         70s bash   for p in /tmp/probes/pp_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -v '
          9s bash   python3 -m unittest -q test_ail_std_pprint 2>&1 | tail -40
          8s bash   rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/compar
          1s bash   for p in lab/stdlib/pprint/p01_nested.py lab/stdlib/pprint/p02_width_indent.py; do echo ===$p; python3 AIL_CUR
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo check=$?; git status --shor

## review 0
[model opencode-go/deepseek-v4.1-flash]
Reviewed `df4ae79` (`work..HEAD`): it adds `pprint` names to the general-path lowering (`genlib.py`) plus a 362-line Python-source emulation in `prelude_genlib.py`, 12 lab programs, `test_ail_std_pprint`, manifest/DEVLOG/DIFFERENCES entries. No compiler/runtime changes outside the general-path prelude.

**Claims checked**
- 12/12 build and match CPython (default + `AIL_IR=1`): **verified** — `test_ail_std_pprint` passed (156 s).
- `test_ail_safetynet`: **verified** (183 s).
- Typed path still refuses `import pprint`: **verified** (`p02 --strict`, rc=3).
- Manifest `--check`: **verified**, rc=0.
- lab/compare 7/10 build, C byte-identical, 3 refuse identically: **verified** with `--exact-int` (rail_transfer, chain_relax build; `program.c` identical to base; scar_life/tally_lang/tree_fold refusal text identical).
- “Probes cover the boundaries”: **false** — their probes omit recursion, long bytes, and positional arity; those fail below.

**Defects (probe source, expected vs actual)**
1. Recursive containers segfault instead of being handled/refused.
```python
a = []; a.append(a)
print(pprint.saferepr(a)); print(pprint.pformat(a)); print(pprint.isrecursive(a))
```
`/tmp/rprobes/r12_recur.py`: CPython prints `built`, `[<Recursion on list with id=...>]` twice, `isrec True isread False`, exit 0. Compiled: no stdout, exit 139 (SIGSEGV) on both builds. Base refused, so caused by this change. `saferepr` is specifically documented as handling recursive data; a crash is not the allowed “leave it refused” outcome.

2. Long `bytes`/`bytearray` are not wrapped.
```python
b = b'abcdefghijklmnopqrstuvwxyz0123456789'
print(pprint.pformat(b, width=20)); print(pprint.pformat(bytearray(b), width=20))
```
`/tmp/rprobes/r9_bytes.py`: CPython emits multi-line `(...)` / `bytearray(...)`; compiled emits one long line. Base refused. The limitation is documented, but it is a wrong built output, not a refusal.

3. `pprint`/`pformat`/`pp`/`PrettyPrinter` accept extra positional arguments CPython rejects.
```python
pprint.pprint({'a': 1}, None, 2, 10, 2, True, False)
pprint.pformat({'a': 1}, 2, 10, 2, True, False)
pprint.PrettyPrinter(2, 10, 2, None, True, False)
```
`/tmp/rprobes/r8c_pos.py`: CPython raises `TypeError: pprint() takes from 1 to 5 positional arguments...`, etc.; compiled accepts and prints the dict / constructs the printer. Base refused. This is an undocumented argument-form mismatch (the `KEYWORDS` guard checks keywords only, not arity/keyword-only status).

**Pre-existing** (identical on base, not blocking): short non-empty `set`/`frozenset` repr order differs from CPython (`repr({3,1,2})`), which leaks into short-set `pprint` output; base has the same set repr.

**Unverified:** instruction-count/speed (pprint is not hot code and there is no relevant gdev workload); `test_ail_files`/`test_ail_corpus_findings3` (not rerun per the review rule; worker reports them passing).

VERDICT: FIX
[cost $0.0463, opencode tokens {"total": 2504898, "input": 95045, "output": 10122, "reasoning": 31475, "cache.write": 0, "cache.read": 2368256}]
    tool time: bash 13.3 min
        407s bash   rm -rf /tmp/ccmp && mkdir -p /tmp/ccmp/h /tmp/ccmp/b; for t in ticket_audit tree_fold rail_transfer scar_life 
        184s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_pprint test_ail_safetynet 2>&1 | tail 
         40s bash   for p in /tmp/rprobes/r*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail -40; 
         39s bash   cat > /tmp/rprobes/r6_imports.py <<'EOF' from pprint import pprint, pformat, PrettyPrinter, saferepr, isreadab
         38s bash   cat > /tmp/rprobes/r8b_errors.py <<'EOF' import pprint  def run(f):     try:         print('ok', f())     exce
         28s bash   for t in rail_transfer chain_relax; do for side in h b; do if [ $side = h ]; then wt=$PWD; else wt=/tmp/base; 
         20s bash   cat > /tmp/rprobes/r12_recur.py <<'EOF' import pprint a = [] a.append(a) print('built') try:     s = pprint.sa
         15s bash   cat > /tmp/rprobes/r1c_types.py <<'EOF' import pprint print('int', pprint.pformat(0), pprint.saferepr(0), ppri

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Done, committed `bca6634`.

- **Fixes:** recursive dict/list/tuple now print `<Recursion on ... with id=N>` instead of segfaulting; long `bytes`/`bytearray` wrap like CPython; `pprint`/`pformat`/`pp`/`PrettyPrinter` signatures now enforce CPython arity and keyword-only arguments.
- **Tests on final commit:** `test_ail_std_pprint`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_genlib` — 5/5 passed (467 s).
- **Probes (both cmp builds):** `pp_bytes`, `pp_bytes_extra`, `pp_arity_ok` exact; `pp_arity_bad_{pprint,pformat,printer,pp}`, `pp_pos`, `pp_kwonly` refused by name; `pp_rec`, `pp_rec_extra` handled and match after normalising only the process-specific `id=` digits.
- **lab/compare:** 7/10 build with byte-identical `program.c`; 3 refuse identically.
- **Manifest:** `update_manifest.py --check` exits 0. Working tree clean except untracked `.agent/pipeline.md`.
[cost $0.0680, opencode tokens {"total": 7017051, "input": 145830, "output": 19409, "reasoning": 23268, "cache.write": 0, "cache.read": 6828544}]
    tool time: bash 20.5 min
        468s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_std_pprint test_ail_safetynet test_
        232s bash   rm -rf /tmp/base_compiler /tmp/ccmp && mkdir -p /tmp/base_compiler /tmp/ccmp && git archive df4ae79 AIL_CURREN
        134s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_std_pprint 2>&1 | tail -40
         99s bash   for p in /tmp/probes/pp_rec.py /tmp/probes/pp_rec_extra.py /tmp/probes/pp_bytes.py /tmp/probes/pp_bytes_extra.
         52s bash   python3 - <<'EOF' p='AIL_CURRENT/python/pkg-v12/prelude_genlib.py' s=open(p).read() old='''def _ail_pp(object,
         50s bash   cat > /tmp/probes/pp_rec_extra.py <<'EOF' import pprint   def mark(value):     return pprint.isrecursive(value
         39s bash   python3 - <<'EOF' p='AIL_CURRENT/test_ail_std_pprint.py' s=open(p).read() s=s.replace('import subprocess\nimpo
         36s bash   python3 - <<'EOF' p='AIL_CURRENT/python/pkg-v12/prelude_genlib.py' s=open(p).read() old='''def _ail_pp_wrap_by

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: stdlib `pprint` coverage

**What the change does:** adds a general-path `pprint` implementation to `prelude_genlib.py`/`genlib.py` (plus a `ppid` runtime identity fragment), with recursion handling, long `bytes`/`bytearray` wrapping, CPython signatures; adds 12 lab programs, a test module, and records.

**Probes (all in `/tmp/rprobes`, both `cmp.sh` builds unless stated):**
- `pp_bytes_r`, `pp_edge2_r` — short/long `bytes`/`bytearray`, widths 1/3/-1, indent 80, nested in list/dict/tuple, `pp`/`pprint` streams, `ValueError`s: **same stdout + exit**.
- `pp_rec_r`, `pp_recdepth_r` — self-recursive list/dict/tuple, alias sharing, depth limits, `saferepr`/`isreadable`/`isrecursive`: **same apart from process-specific `id=` digits** (documented).
- `pp_kw_r`, `pp_mix2_r`, `pp_sort2_r` — `sort_dicts`, `compact`, `underscore_numbers`, `indent=0/2`, tuple/empty cases: **same**.
- `pp_mut_r` — mutate list/dict/bytearray after `pformat`: snapshot strings **unchanged, same**.
- `pp_set_r` — wrapped sets fine; short non-empty set order differs, but identical on base (pre-existing set `repr` order).
- `pp_pos_r`, `pp_arity_pp_r`, `pp_unknown_kw_r`, `pp_kwonly_r` — extra positional / unknown keyword **refused by name** (allowed); valid keyword-only form **same**.
- `setrepr.py` on base = same difference (pre-existing).
- `plain_r.py` (typed) and `gen_plain.py` (general-path json): `program.c` **byte-identical** to base.
- `lab/compare`: `main.ail` **10/10 identical C**; `main.py` 5 build identical, 5 identical refusals (only absolute path prefix differs).

**Tests on HEAD:** `test_ail_std_pprint` + `test_ail_safetynet` 2/2 passed (263 s); `test_ail_genlib` passed (61 s). `update_manifest.py --check` exits 0; tree clean except untracked `.agent/pipeline.md`.

**Claims:** recursion fix **verified**; long bytes/bytearray wrapping **verified**; signature/arity enforcement **verified**; manifest/test claims **verified for the modules I ran**; "lab/compare 7/10 build, 3 refuse" **not reproduced** (measured 10/10 `main.ail` identical; 5/5 `main.py`), but the required C-identity invariant holds; probe claims consistent with my equivalents.

**Pre-existing (not blocking):** short non-empty `set`/`frozenset` output uses the runtime's insertion-order `repr` instead of CPython hash order (same on base). Recursion `id=` digits differ by design.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, the worker's exact `/tmp/probes` files; instruction-count speed check (unneeded: non-pprint generated C is byte-identical).

VERDICT: ACCEPT
[cost $0.0458, opencode tokens {"total": 2816066, "input": 95695, "output": 11703, "reasoning": 27324, "cache.write": 0, "cache.read": 2681344}]
    tool time: bash 20.6 min
        227s bash   cd /home/runner/work/ail-ci/ail-ci; for t in tree_fold rail_transfer scar_life echo_pack tally_lang chain_rela
        140s bash   cd /home/runner/work/ail-ci/ail-ci; b=0; r=0; for t in ticket_audit tree_fold rail_transfer scar_life echo_pac
        139s bash   cd /home/runner/work/ail-ci/ail-ci; for t in ticket_audit tree_fold rail_transfer scar_life echo_pack tally_la
        120s bash   cd AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std_pprint test_ail_safetynet > /tmp/rtest
        120s bash   cd AIL_CURRENT && setsid bash -c 'python3 ../tools/par_check.py -j 2 test_ail_std_pprint test_ail_safetynet > 
         82s bash   cd /home/runner/work/ail-ci/ail-ci; for t in tree_fold rail_transfer scar_life tally_lang; do src=$PWD/lab/com
         63s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_genl
         61s bash   cd /home/runner/work/ail-ci/ail-ci; n=0; for t in ticket_audit tree_fold rail_transfer scar_life echo_pack tal

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T10:22:02Z
