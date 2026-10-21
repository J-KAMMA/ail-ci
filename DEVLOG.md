# DEVLOG

## 2026-10-21 -- job-fuzz4-10220602 (dicts, sets, comprehensions)

Ran 240 generated programs (dict order churn, set algebra/subset churn, set range churn,
comprehension and update/delete templates) plus ~60 hand-written edge programs and 8 probes in
`/tmp/probes`, each with `bash ~/tools/cmp.sh` on the general path and the default build.

Fixed two silent-difference causes:

1. Dict operations on stored keys re-ran `__hash__`: `pop`/`setdefault` hashed twice, and
   `update(other_dict)`, `copy`, `popitem`, `dict(d)` re-hashed.  The object runtime now uses one
   hash for pop/setdefault, clones the entry table for `copy`, removes the last entry directly
   for `popitem`, and reuses stored hashes for update/dict.  `dict.pop` on an empty dict also
   takes CPython's no-hash fast path.
2. Dict and set literals on the general path hashed each element as it was evaluated.  CPython
   3.12's `BUILD_MAP`/`BUILD_SET` evaluate every key/value/element first, then hash/insert; the
   general lowering now does the two phases.  The typed literal emitter still inserts per pair,
   but its keys are scalar int/str/bytes/float values with no user `__hash__`, so no silent
   stdout difference was observed on that path.

Remaining (not fixed): same-size dict mutation during iteration still differs by path/declared
structural-mutation rule; `reversed(dict)` and `dict | dict` are accepted then stop at run time;
and `dict(d)` may call a user `__eq__` a different number of times than CPython when the source
table has a particular internal shape (CPython's own count depends on key-table sharing).
`test_ail_fuzz1` could not run locally because `difffuzz` is not in this snapshot; the required
and targeted modules were run on the final commit.
