# job job-fz228-11050703  started 2026-11-04T22:05:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**No change made — the difference does not reproduce on this tree.**

What I ran (Python 3.12.3, this branch `job-fz228-11050703`):

1. `/tmp/probes/fz228.py` (verbatim from the report) via `bash ~/tools/cmp.sh /tmp/probes/fz228.py $PWD`: CPython exit 0, `g` (unified/general) exit 0 **same stdout**, `d` (default) exit 0 **same stdout**. Separately compiled with `AIL_IR=1`: exit 0, no diff.
2. The authoritative harness `python3 lab/fuzz/run.py --start 2076120347 --count 1 --modes default,ir`: `default 1 same / DIFF 0`, `ir 1 same / DIFF 0`; `/tmp/fzout/findings` is empty. So the CI finding predates this export.

Cause I narrowed it to (and probed): the construct was a keyed sort over a list that had received a wide-literal element — `v12.sort(key=lambda q: (-q, q))` after `v12 = [abs(96), 27, (62 % 4611686018427387904), 0]`, with `v12 += v12`, `v12[2] = i17` and `v12.pop()` in between; the old build typed the element as `object`, so the tuple-key comparison died with `'<' not supported between instances of 'object' and 'int'` instead of printing the `pt0` row. That construct is now handled (tuple-key sorts landed well after the CI commit; DEVLOG has several entries on tuple keys / sortkey).

Probes (each `cmp.sh` → CPython vs `g` and `d`, plus a manual `AIL_IR=1` compile), all **same stdout, same exit**:

| probe | construct | default | unified | IR |
|---|---|---|---|---|
| m1 | `list[int]` with `62 % 4611686018427387904`, `sort(key=lambda q: (-q, q))`, `sorted()` | same | same | same |
| m2 | empty `v12 = []` rebound, `+=` doubling, item store at index 2, `pop()`, then `sorted()` + keyed sort, `xs[:4]` | same (general path) | same | same |
| m3 | keyed sort over a list arriving as a **function argument**, `sum()` of the result | same | same | same |

Other differences seen: none — no other output or exit-code divergence appeared in the seed run or in the three probes; the tree stayed clean (`git status` shows only the pre-existing untracked `.agent/pipeline.md`), so nothing was committed, no DIFFERENCES row, DEVLOG entry or test module was added (per the "confirm; if not, change nothing" instruction).
[commandcode stop=end_turn turns=16 out_tokens=8694]

FINAL VERDICT: NOCHANGE  2026-11-04T22:09:35Z  (the worker changed nothing; no review was run)
