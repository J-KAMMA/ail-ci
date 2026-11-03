"""Advisory slow-pattern hints (ail_slow_patterns): `check` reports them as `slow_patterns`, `compile`
prints them on stderr after a successful build. Never a failure, at most 3 lines, one per kind.

Why: in the 2026-10-14 novel-task round AIL's rail_transfer was 40x C. The program used a heap of
structs (then 5.5x the instructions of the same search over a heap of packed ints, measured with
tools/icount; a key of int/float fields is now sifted in C, so only computed keys are reported) and a one-sided search where C/Rust searched from both ends (175x fewer
relaxations); the reference's own Dijkstra example scanned every edge for each popped node. The
hints name the commonly O(n^2) shapes (list search / front shifts / re-scanning a list the loop
changes / per-key scans / nested loops over one list) and the struct heap; a survey of every
LLM-written AIL program in experiments/llm-compare must stay almost silent (false positives).
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import ail_chatgpt  # noqa: E402
import ail_slow_patterns  # noqa: E402

BAD = 'from ail import heappop, heappush\nimport sys\n\nclass Step:\n\n    def __init__(self, dist: int, node: int):\n        self.dist = dist\n        self.node = node\n\ndef main() -> int:\n    n = int(input())\n    seen: list[int] = []\n    for i in range(n):\n        x = i * 7 % 1000\n        if x not in seen:\n            seen.append(x)\n    q = [0]\n    order: list[int] = []\n    while len(q) > 0:\n        u = q.pop(0)\n        order.insert(0, u)\n        if u + 1 < n:\n            q.append(u + 1)\n    pending: list[int] = []\n    total = 0\n    for i in range(n):\n        pending.append(i * 31 % 97)\n        m = min(pending)\n        total += m\n    src = [0, 0, 1, 2]\n    dst = [1, 2, 3, 3]\n    w = [4, 1, 1, 5]\n    best = [1 << 60] * 4\n    best[0] = 0\n    h: list[Step] = [Step(0, 0)]\n    while len(h) > 0:\n        s = heappop(h, key=lambda s: (s.dist, -s.node))\n        if s.dist > best[s.node]:\n            continue\n        for e in range(len(src)):\n            if src[e] == s.node and s.dist + w[e] < best[dst[e]]:\n                best[dst[e]] = s.dist + w[e]\n                heappush(h, Step(best[dst[e]], dst[e]), key=lambda s: (s.dist, -s.node))\n    pairs = 0\n    for i in range(len(seen)):\n        for j in range(i + 1, len(seen)):\n            if seen[i] + seen[j] == 1000:\n                pairs += 1\n    print(len(seen), len(order), total, best[3], pairs)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

GOOD = 'import sys\n\nclass Box:\n\n    def __init__(self, rows: list[int]):\n        self.rows = rows\n\ndef main() -> int:\n    n = int(input())\n    seen: set[int] = set()\n    mark = [False] * 1000\n    d: dict[int, int] = {}\n    names = [\'a\', \'b\', \'c\']\n    s = \'\'\n    hits = 0\n    for i in range(n):\n        x = i * 7 % 1000\n        if x not in seen:\n            seen.add(x)\n        if not mark[x]:\n            mark[x] = True\n        if x in d:\n            d[x] += 1\n        else:\n            d[x] = 1\n        if str(x % 4) in names:\n            hits += 1\n        if \'1\' in str(x):\n            hits += 1\n        s += str(x % 10)\n    q = [0]\n    head = 0\n    while head < len(q):\n        u = q[head]\n        head += 1\n        if u + 1 < n:\n            q.append(u + 1)\n    start = [0, 2, 3, 5]\n    val = [1, 2, 3, 4, 5]\n    b = Box([])\n    for g in range(3):\n        part: list[int] = []\n        for k in range(start[g], start[g + 1]):\n            if val[k] == g:\n                part.append(k)\n        part.sort()\n        b.rows.append(len(part))\n        top = max(part + [0])\n        hits += top\n    for i in range(3):\n        for j in range(3):\n            hits += i * j\n    print(len(seen), len(d), hits, len(s), len(q), len(b.rows))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


def scan(source, limit=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'main.ail'
        path.write_text(source, encoding='utf-8')
        source_map = {}
        text, _, _ = ail_chatgpt._load_sources(path, source_map=source_map)
        old = ail_slow_patterns.LIMIT
        if limit is not None:
            ail_slow_patterns.LIMIT = limit
        try:
            return ail_slow_patterns.scan(text, source_map)
        finally:
            ail_slow_patterns.LIMIT = old


def cli(*args, cwd, env=None):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), *args], cwd=cwd,
                          capture_output=True, text=True, timeout=300, env=env)


class SlowPatternTests(unittest.TestCase):
    def test_every_kind_is_found_on_its_line(self):
        found = {(w['line'], w['rank']) for w in scan(BAD, limit=99)}
        self.assertEqual(found, {(15, 0), (20, 1), (28, 3), (40, 2), (43, 5), (46, 4)})
        more = {w['line']: w['more'] for w in scan(BAD, limit=99)}
        self.assertEqual(more[20], 1)  # insert(0, x) just below is the second front shift

    def test_good_shapes_are_silent(self):
        self.assertEqual(scan(GOOD, limit=99), [])

    def test_limit_keeps_the_worst_kinds(self):
        lines = [w['line'] for w in scan(BAD)]
        self.assertEqual(lines, [15, 20, 40])

    def test_check_and_compile_report_but_never_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'main.ail').write_text(BAD, encoding='utf-8')
            result = cli('check', 'main.ail', cwd=directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(len(report['slow_patterns']), 3)
            self.assertTrue(report['slow_patterns'][0].startswith('main.ail:15: slow: `in seen` scans the list'))
            build = cli('compile', 'main.ail', '-o', 'prog', cwd=directory)
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertEqual(build.stderr.splitlines(), report['slow_patterns'])
            run = subprocess.run([str(Path(directory, 'prog'))], input='50\n', capture_output=True,
                                 text=True, timeout=30)
            self.assertEqual(run.stdout.split()[:2], ['50', '50'])
            quiet = cli('check', 'main.ail', cwd=directory, env={**os.environ, 'AIL_NO_SLOW_HINTS': '1'})
            self.assertNotIn('slow_patterns', json.loads(quiet.stdout))
            Path(directory, 'good.ail').write_text(GOOD, encoding='utf-8')
            clean = cli('compile', 'good.ail', '-o', 'good', cwd=directory)
            self.assertEqual((clean.returncode, clean.stderr), (0, ''))

    def test_llm_corpus_is_almost_silent(self):
        runs = ROOT.parent / 'experiments/llm-compare'
        files = sorted(glob.glob(str(runs / 'runs-2026-10-1[34]/sources/*-ail-*.ail')))
        if not files:
            self.skipTest('experiments/llm-compare is not part of this tree')
        warned = {}
        for name in files:
            source_map = {}
            text, _, _ = ail_chatgpt._load_sources(Path(name), source_map=source_map)
            found = ail_slow_patterns.scan(text, source_map)
            if found:
                warned[Path(name).name] = sorted((w['line'], w['rank']) for w in found)
        # ticket_audit-2: venues x events scan. rail_transfer 3/4 (the 40x program) key their struct
        # heaps on int fields, which the compiler now sifts in C (4.6x fewer instructions).
        self.assertEqual(warned, {'ticket_audit-ail-2.ail': [(254, 2)]})
        self.assertEqual(len(files), 60)


if __name__ == '__main__':
    unittest.main()
