# job job-arena1s2c-11041017  started 2026-11-04T01:18:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
I'll start by checking the current state and whether the work already landed.
[commandcode stop=permission_denied turns=40 out_tokens=14910]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Reviewer report

**What the change does.** Adds an AST pass `_elide_readonly_field_aliases` (plus `_alias_*` helpers) that rewrites read-only `x = o.f` list-field aliases to direct `o.f` reads and drops the assignment, with a no-rewrite retry on `Unsupported`, and registers `test_ail_readonly_field_alias`.

**Probes (`cmp.sh` HEAD vs `/tmp/base` at `work`).**
- `p1_sort.py` (do_sort shape, int+str, negative values): CPython/base/HEAD same; HEAD C has no `ail_pslist_snapshot`/`ail_list_snapshot` for `nm`/`par`.
- `p8_float_empty.py` (list[float], empty, negative): same on both builds.
- `p3_field_mut.py` (`t.par.append`), `p10_nofeature.py`, `p11_nofeature2.py`: same output; for the two no-feature programs the `--debug-dir` `program.c` hashes are byte-identical base vs HEAD.
- `p5/p6` lambda-parameter shadow variants: same output (the rewrite fails to build and the fallback keeps the copy).
- `p7` (below): **wrong output on the default build**, CPython and base correct.

**New tests.** `test_ail_readonly_field_alias` and `test_ail_safetynet` pass on HEAD (`par_check -j 2`, 130 s). The module compares against an explicit `.copy()` reference build, not CPython as the task asked, and does not cover a lambda parameter that shadows the struct name.

**tree_fold (N=3M, `/tmp/in3m.txt`, median of 3).** Base 414,284 KiB / 1.00 s / 149,713 faults; HEAD 367,424 KiB / 1.05 s / 153,594 faults; stdout identical. RSS target met and wall within noise; faults did not fall (the DEVLOG says this honestly).

**Claims.** DEVLOG numbers (RSS, wall, no snapshots for `do_sort`, non-trivial C diff) verified. "Elides only when all listed conditions hold" is **false**: shadowing of `o` by a sort-key lambda parameter is not checked. Full 10-task/corpus runs, ASan/UBSan, 20 shards and the twelve worker probes are **unverified**. No pre-existing output differences found.

**Defect**

1. Lambda parameter `o` shadows the struct `o`; the pass still substitutes `o.par` inside the lambda, so the key reads the element's field. Repro:

```python
class T:
    par: list[int]
    idx: int
    def __init__(self, par: list[int], idx: int) -> None:
        self.par = par
        self.idx = idx

def f(o: T, xs: list[T]) -> list[int]:
    p = o.par
    n = len(p)
    ys = sorted(xs, key=lambda o: p[o.idx])
    out: list[int] = []
    for y in ys:
        out.append(y.idx)
    return out

def main() -> int:
    o = T([10, 20, 30], 9)
    xs = [T([100, 0, 0], 2), T([0, 200, 0], 0), T([0, 0, 300], 1)]
    for v in f(o, xs):
        print(v)
    return 0
main()
```

Expected (CPython and base, both builds): `0 1 2`. Actual (HEAD default): `2 0 1` (HEAD `AIL_UNIFIED_FORCE=1` still `0 1 2`). The generated C indexes `v__t4->f_par` where `v__t4` is the list element, not the outer `o`. Fix: reject any lambda in the range whose parameters bind `o` (or alpha-rename the struct before substitution), and add this as a negative test.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 3850924, "input": 108651, "output": 11174, "reasoning": 47643, "cache.write": 0, "cache.read": 3683456}]
    tool time: bash 3.4 min
        131s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_readonly_field_alias test_ail_safety
          8s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, random, subprocess, sys, os spe
          7s bash   for wt in /tmp/base /home/runner/work/ail-ci/ail-ci; do tag=$(basename $wt); [ "$tag" = "ail-ci" ] && tag=head
          7s bash   for exe in /tmp/tf_base/exe /tmp/tf_head/exe; do echo "== $exe"; for i in 1 2 3; do /usr/bin/time -f '%M KiB %
          5s bash   cat > /tmp/rprobes/p4_passfield.py <<'EOF' class T:     par: list[int]     def __init__(self, par: list[int]) 
          5s bash   cat > /tmp/rprobes/p12_enumerate.py <<'EOF' class T:     par: list[int]     def __init__(self, par: list[int])
          4s bash   cat > /tmp/rprobes/p6_lambda_shadow_o.py <<'EOF' class T:     nm: list[str]     par: list[int]     def __init_
          4s bash   cat > /tmp/rprobes/p5_lambda_shadow.py <<'EOF' class T:     nm: list[str]     par: list[int]     def __init__(

## worker report 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Report

**Defect fixed.** The read-only field-alias pass substituted `o.f` inside a sort-key lambda whose parameter shadowed the struct name (or the alias name), making the key read the element. `_elide_readonly_field_alias_in_function` now rejects any lambda in the alias's live range whose parameters bind `o` or `x` (positional, keyword, `*args`, `**kw`); the copy is kept. Added negative tests for a lambda shadowing the struct, a lambda shadowing the alias, and a comprehension target shadowing the struct, all compared with CPython. Registered in `tests.d`; DEVLOG entry added.

**Probes** (`bash ~/tools/cmp.sh`, default and forced builds unless noted):
- Reviewer repro `p_shadow_o` → same as CPython (was wrong before); generated C keeps `ail_list_snapshot`.
- `p_shadow_x`, `p_comp_shadow`, `p7_lambda_shadow_o` → same as CPython, copy kept.
- `p01`–`p06`, `p_field_pass*`, `p_listparam_*` (12 earlier probes) → same as CPython.
- `p_vararg_shadow`, `p_kwarg_shadow`, `p_default_shadow`, `p_posonly_shadow` → refused by name (compiler rejects those lambda shapes).
- `p_match_shadow_o*` → same as CPython (`o` rebound by a match capture; the typed rewrite falls back and keeps the copy).
- `do_sort` still elides both snapshots (no `ail_list_snapshot`/`ail_pslist_snapshot` calls in it).

**Tests** (`par_check -j 2`, final commit `3d3766e9`): `test_ail_readonly_field_alias`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (197 s).

**tree_fold, N=3M, 3 runs:** fix median 367,376 KiB (367.4 MB), wall 0.99 s, ~153k faults; base 414,280 KiB, 0.98 s, ~149k faults; stdout identical. The fixed build is byte-identical to the pre-fix HEAD binary (sha `9dcb9ce4…`), so the target ≤415 MB still holds and wall is within noise.

Committed as `3d3766e9`; working tree clean except the untracked `.agent/pipeline.md` runner artifact. Not pushed.
[commandcode stop=end_turn turns=34 out_tokens=17025]

## review 1 failed to run: [model commandcode/deepseek-v4.1-flash] Now I'll write a batch of probes targeting mutation-through-aliases, parameter passing, evaluation routes (argument/list item/attribute/dict), match captures, and boundaries. [commandcode stop=permission_denied turns=7 out_tokens=22124] 

## review 1
[model commandcode/deepseek-v4.1-flash]
I have enough evidence. Writing the report.

## What the change really does

Adds `_elide_readonly_field_aliases` in `pyfunc.py` — an AST pass run in `_to_c_once` before `sortkeys.rewrite` (and on the staged probes) that replaces every load of a single-assignment `x = o.f` (`list[int|float|str]` field) with `o.f` and deletes the assignment when a syntactic read-only/escape analysis holds, plus a lambda-parameter-shadow guard and an `Unsupported`-only recompile-without-rewrite fallback. This matches the report (the report describes only the last sub-fix; the diff is the whole S2 feature).

## Probes (`bash ~/tools/cmp.sh <p> $PWD`, both builds; base = `/tmp/base` at `work`)

| probe | HEAD | base | note |
|---|---|---|---|
| p01 dead alias in an `if` (empty block after removal) | same | same | no crash |
| p02 `match` capture rebinds `o` | same | same | copy kept (`v_x` snapshot in C) |
| p03 mutation via another alias `y = t.par` | same | same | |
| p04 user fn mutating the list arg | same | same | |
| p05 sort key `(par[i], nm[i], i)`, empty/negative | same | same | C reads `f_par`/`f_nm` in place |
| p06 dict value / list item / slice / user-call escape | same | same | |
| p07 `sum/min/max/sorted/count/index` | same | same | |
| p08 no feature used | same | same | generated C **byte-identical** to base |
| p09/p09b nested `def` reads `x` (after/before) | same | same | |
| p10 `global g; g = t.par` then read in `main` | **DIFF** | same | see defect |
| p11 nested def default captures `x` | same | same | |
| p12 nested def mutates `t.par` | same | same | |
| p13 `y = x; y.append` | same | same | |
| p14 sort key lambda param shadows `o` | same | same | copy kept (`ail_list_snapshot`) |
| p15/p16 `Bag(t.par)` / `ident(t.par)` moves | same | same | |
| p17 `nonlocal x` store | same | same | |

No "pre-existing" differences found.

## Measurements

- tree_fold N=3M, default build, same input (`gen.cases(Random(1))` perf), stdout identical (md5 `c8788eee…`): peak RSS HEAD 367,404 KiB median (367,328–367,508; 5 runs) vs base 415,468 KiB (414,248–415,940). **≤415 MB target met** (−11.6%).
- Wall (5 interleaved pairs): HEAD 0.97–0.99 s (median 0.98) vs base 0.94–0.96 s (median 0.95); minor faults HEAD ~152k vs base ~149k. Small (≈3%) but consistently in the wrong direction on this runner; the DEVLOG's own fault numbers also rose.
- Tests `-j 2` on HEAD: `test_ail_readonly_field_alias`, `test_ail_safetynet` — 0 failed (127 s).

## Claims

1. Lambda-shadow defect fixed; copy kept — **verified** (code guard, test module, p14 C keeps `ail_list_snapshot`).
2. Three negative shadow tests compared with CPython — **verified** (present in `SHADOW_NEGATIVES`/negatives, tests pass).
3. `tests.d` registration + DEVLOG + manifest — **verified** (`update_manifest.py --check` clean).
4. Worker's named probes (`p01`–`p06`, `p_shadow_*`, `p_listparam_*`) — **unverified** (not in the tree; equivalent shapes I wrote pass).
5. vararg/kwarg/default/posonly-shadow probes refused by name — **unverified**.
6. `match`-shadow probe matches CPython, copy kept — **verified** (p02).
7. `do_sort` still elides both snapshots — **verified** (no snapshot call in `do_sort`; reads `f_nm`/`f_par`).
8. Four test modules 0 failed — **partially verified** (I reran the changed module + safetynet).
9. tree_fold RSS 367.4 vs 414.3 MB, identical stdout — **verified**; "wall within noise" — **not reproduced** (see above).
10. "Fixed build byte-identical to pre-fix HEAD binary (sha 9dcb9ce4…)" — **unverified**.

VERDICT: FIX

1. **A store to a `global` name is elided, so the global is never updated.** The pass checks `Global`/`Nonlocal` declarations only for `o` and only inside the alias's live range; the declaration normally sits *before* the first statement of the range, so the single `x = o.f` store to a global is removed. `/tmp/rprobes/p10_global.py`:
   ```python
   class T:
       nm: list[str]
       par: list[int]
       def __init__(self, nm: list[str], par: list[int]) -> None:
           self.nm = nm; self.par = par
   g: list[int] = [1]
   def f(t: T) -> int:
       global g
       g = t.par
       return len(g)
   def main() -> int:
       print(f(T(["a"], [1, 2]))); print(len(g)); return 0
   main()
   ```
   CPython and base default build: `2\n2`. HEAD default build: `2\n1` (generated `f` is `return span_len((v_t)->f_par);` with no store to the global slot; `AIL_UNIFIED_FORCE=1` is correct). Expected fix: treat any `global`/`nonlocal`-declared name as ineligible for the elision (or scan those declarations function-wide).
[commandcode stop=end_turn turns=52 out_tokens=71808]

FINAL VERDICT: FIX  2026-11-04T04:53:15Z
