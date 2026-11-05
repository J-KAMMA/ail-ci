# job job-bces4-11051444  started 2026-11-05T05:46:40Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed bce s4 on `job-bces4-11051444` as `5785192`.

- Added `AIL_CURRENT/python/pkg-v12/fieldfacts.py`; wired facts through `ir/driver.py` and `pyfunc.py`, with `AIL_BCE_FACTS` JSON dump.
- Verified tally/ledger expected groups and non-negative fields; C census reports all 20 task/syntax pairs `same C` (exit 0).
- Added dump-reading probes to `test_ail_bce.py`; all 7 required test modules pass, including `test_ail_ir_s3` run without the incompatible `ulimit -v` cap.
- Compile medians stayed at 0.12 s total for tally_lang, ticket_audit, tree_fold.
- Not pushed, per job instructions. Only `.agent/pipeline.md` remains untracked.
[cost $0.0000, opencode tokens {"total": 11470779, "input": 341021, "output": 40257, "reasoning": 45789, "cache.write": 0, "cache.read": 11043712}]
    tool time: bash 33.8 min, write 0.0 min
        748s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 lab/beatc/bce_census.py check --base /tmp/bas
        560s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_bce test_ail_ir_s3 test_ail_mod
        247s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_bce test_ail
        200s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; for t in tally_lang ticket_audit tree_fold; do echo "
        146s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 1 test_ail_ir_s3
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "=== $(basename "$p") ==="; bash ~/to
          8s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/factsprobe/tally_stats.jsonl /tmp/factsprobe/tally2.bin; AIL_
          8s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/facts_tally.json /tmp/facts_ledger.json && AIL_NO_CACHE=1 AIL

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds `fieldfacts.py`, a whole-program AST pass computing parallel-list-group and non-negative-int-field facts, plumbs them via `ir/driver.py` `facts_for()['fields']` keyed by `ctx.funcs`, and dumps them under `AIL_BCE_FACTS`. Nothing consumes them; generated C is unchanged.

**Defect**

1. False parallel group: the pass identifies "the same object" by `ast.dump` of the receiver expression (`fieldfacts.py:178`, `_collect_runs` at `:225`), so a receiver containing a side-effecting call is treated as stable. Two successive calls can return different objects and leave unequal lengths while the fact is still reported.

   Probe `/tmp/rprobes/pick_side2.ail`:
   ```
   struct P { a: list[int]; b: list[int]; }
   struct S { sel: list[int]; }
   fn pick(items: list[P], s: S) -> P {
       let i = s.sel[0];
       s.sel[0] += 1;
       return items[i];
   }
   fn main() {
       let items: list[P] = [P([], []), P([], [])];
       let s = S([0]);
       pick(items, s).a.append(1);
       pick(items, s).b.append(2);
       print(len(items[0].a), len(items[0].b), len(items[1].a), len(items[1].b));
   }
   ```
   Expected `AIL_BCE_FACTS` `groups: []` (the two appends run on `items[0]` and `items[1]`, not one object). Actual:
   `{"groups":[{"fn":null,"grow_only":true,"members":["a","b"],"struct":"P"}],"nonneg":[]}`.
   The program prints `1 0 0 1`, so the reported invariant `len(a)==len(b)` is false for both persistent objects. Any s5/s6 consumer trusting this fact would be unsafe. The pass should require a stable receiver (a name/parameter/field chain), not merely equal source text.

**Claims checked**

- `fieldfacts.py`, driver/pyfunc wiring, JSON dump: verified (diff and dumps).
- tally/ledger expected facts: verified; actual ledger group also contains `offs` and `nonneg` also contains `Rd.err` (report omitted both).
- “all 20 task/syntax pairs same C”: partially verified — `tally_lang` and `ledger_bin` × `.ail`/python all `same C`/same failure, exit 0; remaining 16 not run.
- “all 7 test modules pass”: `test_ail_bce` and `test_ail_safetynet` pass on HEAD; the other five not re-run.
- compile time: tally_lang head 0.12 s CPU vs base 0.13 s; no regression (the tool’s “python” figure is negative/artifact).
- not pushed / only `.agent/pipeline.md` untracked: verified.
- user-module facts empty: verified for a Python-module import.

**Test gap:** the new `unequal_construction` probe has no appends and `raising_between_appends` puts the appends in different bodies, so both would pass even if those invalidations were absent. Proper variants (unequal constructor + balanced run, raising argument between the two appends) do behave correctly.

**Pre-existing:** none found; probe runtime outputs match CPython where comparable.

**Unverified:** full 20-pair census; `--separate`/`--object`/`--module`/`--lib`/`@extern`/hybrid guards; the other five test modules; other tasks’ compile time; `AIL_UNIFIED_FORCE=1` probe runs.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 6524630, "input": 157305, "output": 13342, "reasoning": 61503, "cache.write": 0, "cache.read": 6292480}]
    tool time: bash 5.5 min
        187s bash   cd /home/runner/work/ail-ci/ail-ci; date; timeout 900 python3 tools/par_check.py -j 2 test_ail_bce test_ail_sa
         82s bash   cd /home/runner/work/ail-ci/ail-ci; date; timeout 600 python3 lab/beatc/bce_census.py check --base /tmp/base -
         35s bash   cd /home/runner/work/ail-ci/ail-ci; timeout 300 python3 tools/compile_phases.py lab/compare/src/tally_lang/mai
          8s bash   mkdir -p /tmp/rprobes /tmp/rfacts; cd /home/runner/work/ail-ci/ail-ci; for t in tally_lang ledger_bin; do rm -
          4s bash   cd /home/runner/work/ail-ci/ail-ci; rm -f /tmp/rfacts/off.json; AIL_BCE=0 AIL_NO_CACHE=1 AIL_BCE_FACTS=/tmp/rf
          1s bash   cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/unequal_real.ail <<'EOF' struct P { a: list[int]; b: li
          1s bash   cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/get_instance.ail <<'EOF' struct P { a: list[int]; b: li
          1s bash   cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/py_nonneg_param.py <<'EOF' class R:     def __init__(se

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `704643d`.

- Field group blocks now require a stable receiver (name or field chain rooted at a name), so `pick(items, s).a.append(...); pick(items, s).b.append(...)` no longer forms a false group. Reviewer probe now dumps `{"groups":[],"nonneg":[]}` and prints `1 0 0 1`.
- Strengthened `unequal_construction` and `raising_between_appends` probes with balanced append runs, and added a `side_effect_receiver` probe.
- `bce_census.py check`: all 20 task/syntax pairs `same C`/same failure, exit 0.
- tally_lang/ledger_bin facts still show the required groups and non-negative `Lx.pos` / `Rd.pos` / `Rd.err`.
- `tools/par_check.py -j 2` on the 7 targeted/required modules: 7 passed, 0 failed (462 s).
- Probe programs (`fieldfacts_pick/groups/unequal/nonneg`) match CPython on both default and `AIL_UNIFIED_FORCE=1` builds.
- Manifest `--check` passes; `.agent/pipeline.md` left untracked.
[cost $0.0000, opencode tokens {"total": 963665, "input": 47944, "output": 5124, "reasoning": 5765, "cache.write": 0, "cache.read": 904832}]
    tool time: bash 29.1 min, edit 0.0 min, read 0.0 min
        763s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 lab/beatc/bce_census.py check --base /tmp/base --out
        463s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_bce test_ail_ir_s3
        461s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_bce test_ail_ir_s3
         40s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/rfacts2 && mkdir -p /tmp/rfacts2 && for t in tally_lang ledg
          9s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fieldfacts_pick.py <<'EOF' class P:     def __init__(self, a: list[i
          8s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 -B -m unittest AIL_CURRENT.test_ail_bce.FieldFactsTe
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   mkdir -p /tmp/rprobes /tmp/rfacts && cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/pick_side2.ail <

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change does:** adds `python/pkg-v12/fieldfacts.py`, called from `pyfunc._to_c_once` before lowering; it computes `{'groups','nonneg'}` and (a) installs it in `ir/driver.py` keyed by `sigs` identity, (b) dumps it to `AIL_BCE_FACTS`. No pass reads `facts['fields']`, so generated C is untouched. This matches the report.

**Claims checked**
- Stable-receiver fix: **verified** — my `pick.py` dump is `{"groups": [], "nonneg": []}` and prints `1 0 0 1`, same as CPython.
- tally/ledger facts: **verified** — `Lx.pos`, `Rd.pos`, `Rd.err`, `{val,has}`, `{n_op,n_a,n_b}`, the seven `s_*`, `{tk,tv}`, `ops/xs/ys/zs`.
- C byte-identical: **verified** on 9 probes (`program.c` from `--debug-dir`, HEAD vs `/tmp/base`); the 20-pair census I did not rerun.
- `test_ail_bce` + `test_ail_safetynet`: **verified**, 2/2 pass (221 s).
- Compile time: **verified** within budget (tally +1.6%, ticket_audit +0.9%, tree_fold +1.4%).
- `cmp.sh`: **verified** for 3 probes, both builds match CPython.
- Manifest `--check`: passes.

**Defects (both in the new pass, both unreported)**

1. `fieldfacts.py:476` builds `bytes_fields` from **struct names**, not field names (`{f for f, st in self.structs.items() ...}`), and `_bytes_expr` (`:739`) then tests `node.attr in bytes_fields`. So `x.<attr>[i]` is treated as a bytes index whenever `<attr>` equals a struct name that owns a bytes field. Probe `/tmp/rp2/n_bytes_collide.ail`:
```
struct vals { data: bytes; }
struct R { vals: list[int]; pos: int; }
fn main() { let r = R([-5], 1); r.pos = r.vals[0]; print(r.pos); }
```
Expected `nonneg: []`; actual `{"groups": [], "nonneg": [["R","pos"]]}` while the program prints `-5`.

2. `_field_still_nonneg` (`:782-793`) recognises only a single-target `Assign`, `AnnAssign` and `AugAssign`. Any other store form is **silently skipped** instead of invalidating the field, contrary to "Any AST construct the pass does not recognise invalidates the facts". Probe `/tmp/rp2/n_tuple.py`:
```
class R:
    def __init__(self, pos: int) -> None: self.pos = pos
def main() -> int:
    r = R(0); r.pos, x = -1, 0; print(r.pos); return 0
main()
```
Expected `nonneg: []`; actual `[["R","pos"]]` while the program prints `-1`. The same hole covers chained/multi-target stores and `for`/`with` attribute targets.

**Pre-existing:** `g_dict.py` (storing a list in a dict) fails to build with exit 4 identically on base and HEAD.

**Unverified:** the 20 census pairs (worker-run, expensive), the remaining 5 of the 7-module `par_check` list, and empty facts for `--separate`/`--object`/`--module` (I could not construct a working invocation; only `--separate` reachability was reported).

Instruction counts: not measured — no generated C differs, so runtime cannot change.

VERDICT: FIX
1. `n_bytes_collide.ail`: `fieldfacts.py` compares attribute names against struct names, so `r.vals[0]` (a `list[int]` element `-5`) is treated as a bytes index. Expected `nonneg: []`; actual `nonneg: [["R","pos"]]`.
2. `n_tuple.py`: a tuple-unpack store `r.pos, x = -1, 0` is ignored instead of invalidating the field. Expected `nonneg: []`; actual `nonneg: [["R","pos"]]`. Handle every unrecognised store form (`Assign` with `Tuple`/multiple targets, `For`, `With`) as "unknown".
[commandcode stop=end_turn turns=37 out_tokens=43882]

FINAL VERDICT: FIX  2026-11-05T10:22:24Z
