#!/usr/bin/env python3
"""Assign the test modules to the CI shards of .github/workflows/tests.yml.

    python3 tools/ci_shards.py --shard 3      # print the modules shard 3 runs (the workflow uses this)
    python3 tools/ci_shards.py --report       # predicted cost of each shard
    python3 tools/ci_shards.py --update       # keep the assignment, add new modules, drop removed ones
    python3 tools/ci_shards.py --rebalance    # recompute everything from ~/.cache/ail_par_check.json
    python3 tools/ci_shards.py --check        # exit 1 if the file names an unknown or duplicated module

tools/ci_shards.json holds the weights (relative seconds from the timing cache that par_check.py
keeps) and the assignment. A shard runs its modules with `par_check.py -j 4`, so its cost is the
larger of its longest module and its total weight / 4 (longest-processing-time assignment on that
cost). A module missing from the file is spread over the shards by name, so a new test module
still runs in CI before the file is updated.
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


def load():
    try:
        data = json.loads(MAP.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'shards': SHARDS, 'jobs': JOBS, 'weights': {}, 'assignment': [[] for _ in range(SHARDS)]}
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
    modules = list(dict.fromkeys(modules))   # a duplicate name is still one module
    n = previous.get('shards', SHARDS)
    old_weights = {} if rebalance else previous.get('weights', {})
    default = fallback_weight(cache, modules)
    weights = {m: old_weights.get(m, cache.get(m, default)) for m in modules}
    assignment = [[] for _ in range(n)]
    if not rebalance:
        wanted = set(modules)
        seen = set()
        for index, members in enumerate(previous.get('assignment', [])[:n]):
            kept = []
            for name in members:
                if name in wanted and name not in seen:
                    seen.add(name)
                    kept.append(name)
            assignment[index] = kept
    placed = {m for members in assignment for m in members}
    for name in sorted((m for m in modules if m not in placed), key=lambda m: (-weights[m], m)):
        place(weights, assignment, name)
    return {'shards': n, 'jobs': JOBS, 'weights': dict(sorted(weights.items())),
            'assignment': [sorted(members) for members in assignment]}


def shard_modules(data, index):
    modules = all_modules()
    n = data['shards']
    mapped = {m for members in data['assignment'] for m in members}
    chosen = [m for m in data['assignment'][index] if m in modules]
    chosen += [m for k, m in enumerate(m for m in modules if m not in mapped) if k % n == index]
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
    mapped = [m for members in data['assignment'] for m in members]
    missing = sorted(set(modules) - set(mapped))
    extra = sorted(set(mapped) - set(modules))
    duplicates = sorted({m for m in mapped if mapped.count(m) > 1})
    for label, names in (('unassigned', missing), ('unknown', extra), ('duplicated', duplicates)):
        if names:
            print('%s: %s' % (label, ' '.join(names)))
    # `--shard` still spreads an unassigned module over the shards by name, so only a stale
    # (unknown) or duplicated name makes the file disagree with what CI runs.
    return 1 if extra or duplicates else 0


if __name__ == '__main__':
    sys.exit(main())
