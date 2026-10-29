#!/usr/bin/env python3
"""Assign the test modules to the CI shards of .github/workflows/tests.yml.

    python3 tools/ci_shards.py --shard 3      # print the modules shard 3 runs (the workflow uses this)
    python3 tools/ci_shards.py --report       # predicted cost of each shard
    python3 tools/ci_shards.py --update       # keep the assignment, add new modules, drop removed ones
    python3 tools/ci_shards.py --rebalance    # recompute everything from ~/.cache/ail_par_check.json
    python3 tools/ci_shards.py --check        # exit 1 if a module has no shard

tools/ci_shards.json holds the weights (relative seconds from the timing cache that par_check.py
keeps) and the assignment. A shard runs its modules with `par_check.py -j 4`, so its cost is the
larger of its longest module and its total weight / 4 (longest-processing-time assignment on that
cost). A module missing from the file is spread over the shards by name, so a new test module
still runs in CI before the file is updated.

A module that alone would be longer than a balanced shard is split into pieces: "pieces" in the json maps
"test_ail_x#0" ... to lists of "Class.test_name" ids, and the assignment lists the pieces instead of the
module. A piece reaches par_check.py as `test_ail_x.Class.test_a+test_ail_x.Class.test_b`, one
`python -m unittest` process (the tests of a split module are independent; keep a module whole when they
share state, as test_ail_sdk does). A test of a split module that no piece lists still runs: --shard
spreads it by name, --update puts it on the lightest piece, --check reports it, and a listed test that no
longer exists is dropped.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP = Path(__file__).with_name('ci_shards.json')
CACHE = Path.home() / '.cache' / 'ail_par_check.json'
SHARDS = 20
JOBS = 4


def all_modules():
    sys.path.insert(0, str(REPO / 'AIL_CURRENT'))
    import ail_check
    return sorted(ail_check.MODULES)


def test_ids(module):
    """The "Class.test_name" ids unittest finds in `module`."""
    sys.path.insert(0, str(REPO / 'AIL_CURRENT'))
    import unittest
    found = []

    def walk(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                walk(test)
            else:
                found.append(test.id())
    walk(unittest.defaultTestLoader.loadTestsFromName(module))
    prefix = module + '.'
    bad = [i for i in found if not i.startswith(prefix)]
    if bad:
        raise SystemExit('cannot list the tests of %s: %s' % (module, bad[0]))
    return sorted(i[len(prefix):] for i in found)


def base(name):
    return name.split('#')[0]


def pieces_modules(pieces):
    return {base(p) for p in pieces}


def split_modules(data):
    return sorted({base(p) for p in data.get('pieces', {})})


def load():
    try:
        data = json.loads(MAP.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'shards': SHARDS, 'jobs': JOBS, 'weights': {}, 'pieces': {}, 'assignment': [[] for _ in range(SHARDS)]}
    data.setdefault('pieces', {})
    return data


def cost(weights, members):
    if not members:
        return 0.0
    values = [weights[m] for m in members]
    return max(max(values), sum(values) / JOBS)


def place(weights, assignment, name):
    """Put `name` on the shard whose cost grows least (ties: the lighter, then the lower index)."""
    best = None
    for index, members in enumerate(assignment):
        key = (cost(weights, members + [name]), sum(weights[m] for m in members), index)
        if best is None or key < best[0]:
            best = (key, index)
    assignment[best[1]].append(name)


def fallback_weight(cache, modules):
    known = [cache[m] for m in modules if m in cache]
    return round(statistics.median(known), 1) if known else 10.0


def build(modules, cache, previous, rebalance):
    n = previous.get('shards', SHARDS)
    old_weights = previous.get('weights', {})
    pieces = {}
    wanted = set(modules)
    for piece, ids in previous.get('pieces', {}).items():
        if base(piece) in wanted:
            current = set(test_ids(base(piece)))
            pieces[piece] = [i for i in ids if i in current]
    for module in sorted({base(p) for p in pieces}):
        listed = {i for piece, ids in pieces.items() if base(piece) == module for i in ids}
        lightest = min((p for p in pieces if base(p) == module), key=lambda p: (len(pieces[p]), p))
        pieces[lightest] += [i for i in test_ids(module) if i not in listed]
    split = {base(p) for p in pieces}
    items = [m for m in modules if m not in split] + sorted(pieces)
    default = fallback_weight(cache, modules)
    weights = {}
    for item in items:
        if item in pieces:
            weights[item] = old_weights.get(item, default)
        else:
            weights[item] = (cache.get(item, old_weights.get(item, default)) if rebalance
                             else old_weights.get(item, cache.get(item, default)))
    assignment = [[] for _ in range(n)]
    if not rebalance:
        keep = set(items)
        for index, members in enumerate(previous.get('assignment', [])[:n]):
            assignment[index] = [m for m in members if m in keep]
    placed = {m for members in assignment for m in members}
    for name in sorted((m for m in items if m not in placed), key=lambda m: (-weights[m], m)):
        place(weights, assignment, name)
    return {'shards': n, 'jobs': JOBS, 'weights': dict(sorted(weights.items())),
            'pieces': dict(sorted((p, sorted(ids)) for p, ids in pieces.items())),
            'assignment': [sorted(members) for members in assignment]}


def shard_modules(data, index):
    modules = all_modules()
    n = data['shards']
    pieces = data.get('pieces', {})
    split = set(split_modules(data)) & set(modules)
    mapped = {base(m) for members in data['assignment'] for m in members}
    chosen = []
    for name in data['assignment'][index]:
        if name in pieces:
            if base(name) in modules:
                current = set(test_ids(base(name)))
                chosen += ['+'.join('%s.%s' % (base(name), i) for i in pieces[name] if i in current)]                     if any(i in current for i in pieces[name]) else []
        elif name in modules:
            chosen.append(name)
    chosen += [m for k, m in enumerate(m for m in modules if m not in mapped) if k % n == index]
    for module in sorted(split):
        listed = {i for piece, ids in pieces.items() if base(piece) == module for i in ids}
        extra = [i for i in test_ids(module) if i not in listed]
        mine = ['%s.%s' % (module, i) for k, i in enumerate(extra) if k % n == index]
        if mine:
            chosen.append('+'.join(mine))
    return sorted(chosen)


def write(data):
    text = json.dumps(data, indent=1, sort_keys=False) + '\n'
    if not MAP.exists() or MAP.read_text(encoding='utf-8') != text:
        MAP.write_text(text, encoding='utf-8')
        return True
    return False


def report(data):
    weights = data['weights']
    costs = [cost(weights, members) for members in data['assignment']]
    for index, members in enumerate(data['assignment']):
        top = max(members, key=lambda m: weights[m]) if members else '-'
        print('shard %2d: %2d modules, total %6.1f, cost %6.1f, longest %s (%.1f)'
              % (index, len(members), sum(weights[m] for m in members), costs[index], top,
                 weights.get(top, 0.0)))
    print('max cost %.1f, mean cost %.1f' % (max(costs), sum(costs) / len(costs)))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--shard', type=int)
    group.add_argument('--report', action='store_true')
    group.add_argument('--update', action='store_true')
    group.add_argument('--rebalance', action='store_true')
    group.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = load()
    if args.shard is not None:
        print(' '.join(shard_modules(data, args.shard)))
        return 0
    if args.update or args.rebalance:
        try:
            cache = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            cache = {}
        if args.rebalance and not cache:
            print('no timing cache at %s' % CACHE, file=sys.stderr)
            return 1
        data = build(all_modules(), cache, data, args.rebalance)
        print('ci_shards.json %s' % ('written' if write(data) else 'unchanged'))
        return 0
    if args.report:
        report(data)
        return 0
    modules = all_modules()
    pieces = data.get('pieces', {})
    mapped = [base(m) for members in data['assignment'] for m in members]
    listed = [m for members in data['assignment'] for m in members]
    missing = sorted(set(modules) - set(mapped))
    extra = sorted(set(mapped) - set(modules))
    duplicates = sorted({m for m in listed if listed.count(m) > 1})
    duplicates += sorted({m for m in mapped if mapped.count(m) > 1 and m not in pieces_modules(pieces)})
    duplicates += sorted(m for m in pieces_modules(pieces) if m in listed)
    for module in split_modules(data):
        if module not in modules:
            continue
        existing = test_ids(module)
        mine = [i for p, ids in pieces.items() if base(p) == module for i in ids]
        unlisted = sorted(set(existing) - set(mine))
        unknown = sorted(set(mine) - set(existing))
        repeated = sorted({i for i in mine if mine.count(i) > 1})
        unassigned = sorted(p for p in pieces if base(p) == module and p not in listed)
        for label, names in (('unlisted tests of %s' % module, unlisted), ('unknown tests of %s' % module, unknown),
                             ('repeated tests of %s' % module, repeated), ('unassigned pieces of %s' % module, unassigned)):
            if names:
                print('%s: %s' % (label, ' '.join(names)))
                missing += names
    for label, names in (('unassigned', missing), ('unknown', extra), ('duplicated', duplicates)):
        if names:
            print('%s: %s' % (label, ' '.join(names)))
    return 1 if missing or extra or duplicates else 0


if __name__ == '__main__':
    sys.exit(main())
