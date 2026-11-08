# job job-fz242-11090609  started 2026-11-08T21:10:38Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I verified the finding against this tree and could not reproduce it. Here is what I did and found.

**Reproduction attempt**
- Regenerated the program with `python3 lab/fuzz/gen.py 2076519017` — byte-identical to the supplied `prog.py`.
- Ran `bash ~/tools/cmp.sh /tmp/probes/fz242.py $PWD`: both builds fail at compile time (`build g failed`, `build d failed`).
- Also built with `AIL_IR=1`: same compile-time refusal.
- Ran the lab's own runner (`python3 lab/fuzz/run.py --start 2076519017 --count 1`): `default: refused 1`, `ir: refused 1`, `DIFF 0`.

**Why it no longer shows**
The construct that produced the DIFF is `h0(...) >= v5.count(i4 % i4)`: the typed lowering hoists `list.count()` into the statement prelude, so `i4 % i4` would run before `h0(...)`, printing nothing and raising `integer modulo by zero` — exactly the CI symptom. That lowering already refuses this by name on this tree (the fz216 fix, `index_or_count` in `AIL_CURRENT/python/pkg-v12/pyfunc.py:38975`):

```
not in the subset: list.count() after a part of this statement that Python evaluates first
may raise or run code; bind the earlier part to a name first, or move the method call before it
```

The default build then falls back to the general path, which additionally refuses this program for an unrelated construct, `break` out of a `try`/`finally` protected region. The whole program is thus refused (rc 3), so there is no silent stdout difference to minimize. Removing only the refused `break` (probe `p7`, the full program otherwise intact) makes it compile and match CPython on all three builds, out `-72|155`, rc 1, `ZeroDivisionError`.

**Probes run (cpython vs `AIL_UNIFIED_FORCE=1`, default, `AIL_IR=1`)** — all same stdout:
- `fz242` (original): refused by name on both builds, no DIFF
- `p5` `h0(...) >= v5.count(i4 % i4)`: match `-72|155`
- `p7` full program minus the refused `break`: match `-72|155`
- `p1`,`p4`,`p6`,`p8`,`p9`,`p11`,`p14`: call/side-effect order in comparisons, `abs/max/min/len/int/str`, `assert`, annotated assignment, f-strings, `%`, print args, item/dict provenance — all match
- `p2`,`p12`: value from list item, dict value, attribute (`b.xs`), argument, and `list[int]`/`list[float]`/`list[str]` receivers — all match
- `p3`,`p10`: attribute/dict/call-result receivers (`mk().count`, `d.values().count`) — all match
- `p13`,`p15`,`p16`: `pop` order, assignment-target vs RHS order, nested `count`/`index` — all match
- `test_ail_fz216`: 6 tests, all OK (the module covering this exact construct, refusal, and provenance cases)

**Changes:** none, per the "if it does not [reproduce], change nothing" instruction. `git status` shows only the pre-existing untracked `.agent/pipeline.md`. I did not commit, so the tree is unchanged.

**Other differences seen:** none in any probe or in the harness run.

Caveat: I cannot verify which AIL revision the linked CI run used; on this export the same program and seed are classified `refused`, not `DIFF`.
[commandcode stop=end_turn turns=44 out_tokens=27103]

FINAL VERDICT: NOCHANGE  2026-11-08T21:18:29Z  (the worker changed nothing; no review was run)
