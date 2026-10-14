"""Advisory slow-pattern hints (ail_slow_patterns): `check` reports them as `slow_patterns`, `compile`
prints them on stderr after a successful build. Never a failure, at most 3 lines, one per kind.

Why: in the 2026-10-14 held-out task round AIL's route-search program was 40x C. The program used a heap of
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

BAD = """struct Step { dist: int; node: int; }
fn main() {
    let n = int(input());
    let seen: list[int] = [];
    for i in range(n) {
        let x = (i * 7) % 1000;
        if x not in seen { seen.append(x); }
    }
    let q = [0];
    let order: list[int] = [];
    while len(q) > 0 {
        let u = q.pop(0);
        order.insert(0, u);
        if u + 1 < n { q.append(u + 1); }
    }
    let pending: list[int] = [];
    let total = 0;
    for i in range(n) {
        pending.append((i * 31) % 97);
        let m = min(pending);
        total += m;
    }
    let src = [0, 0, 1, 2];
    let dst = [1, 2, 3, 3];
    let w = [4, 1, 1, 5];
    let best = [1 << 60] * 4;
    best[0] = 0;
    let h: list[Step] = [Step(0, 0)];
    while len(h) > 0 {
        let s = heappop(h, key=lambda s: (s.dist, -s.node));
        if s.dist > best[s.node] { continue; }
        for e in range(len(src)) {
            if src[e] == s.node and s.dist + w[e] < best[dst[e]] {
                best[dst[e]] = s.dist + w[e];
                heappush(h, Step(best[dst[e]], dst[e]), key=lambda s: (s.dist, -s.node));
            }
        }
    }
    let pairs = 0;
    for i in range(len(seen)) {
        for j in range(i + 1, len(seen)) { if seen[i] + seen[j] == 1000 { pairs += 1; } }
    }
    print(len(seen), len(order), total, best[3], pairs);
}
"""

GOOD = """struct Box { rows: list[int]; }
fn main() {
    let n = int(input());
    let seen: set[int] = set();
    let mark = [False] * 1000;
    let d: dict[int, int] = {};
    let names = ["a", "b", "c"];
    let s = "";
    let hits = 0;
    for i in range(n) {
        let x = (i * 7) % 1000;
        if x not in seen { seen.add(x); }
        if not mark[x] { mark[x] = True; }
        if x in d { d[x] += 1; } else { d[x] = 1; }
        if str(x % 4) in names { hits += 1; }
        if "1" in str(x) { hits += 1; }
        s += str(x % 10);
    }
    let q = [0];
    let head = 0;
    while head < len(q) {
        let u = q[head];
        head += 1;
        if u + 1 < n { q.append(u + 1); }
    }
    let start = [0, 2, 3, 5];
    let val = [1, 2, 3, 4, 5];
    let b = Box([]);
    for g in range(3) {
        let part: list[int] = [];
        for k in range(start[g], start[g + 1]) { if val[k] == g { part.append(k); } }
        part.sort();
        b.rows.append(len(part));
        let top = max(part + [0]);
        hits += top;
    }
    for i in range(3) { for j in range(3) { hits += i * j; } }
    print(len(seen), len(d), hits, len(s), len(q), len(b.rows));
}
"""


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
        self.assertEqual(found, {(7, 0), (12, 1), (20, 3), (32, 2), (35, 5), (41, 4)})
        more = {w['line']: w['more'] for w in scan(BAD, limit=99)}
        self.assertEqual(more[12], 1)  # insert(0, x) on line 13 is the second front shift

    def test_good_shapes_are_silent(self):
        self.assertEqual(scan(GOOD, limit=99), [])

    def test_limit_keeps_the_worst_kinds(self):
        lines = [w['line'] for w in scan(BAD)]
        self.assertEqual(lines, [7, 12, 32])

    def test_check_and_compile_report_but_never_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'main.ail').write_text(BAD, encoding='utf-8')
            result = cli('check', 'main.ail', cwd=directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(len(report['slow_patterns']), 3)
            self.assertTrue(report['slow_patterns'][0].startswith('main.ail:7: slow: `in seen` scans the list'))
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
        files = sorted(glob.glob(str(runs / 'private-runs/sources/*-ail-*.ail')))
        if not files:
            self.skipTest('experiments/llm-compare is not part of this tree')
        warned = {}
        for name in files:
            source_map = {}
            text, _, _ = ail_chatgpt._load_sources(Path(name), source_map=source_map)
            found = ail_slow_patterns.scan(text, source_map)
            if found:
                warned[Path(name).name] = sorted((w['line'], w['rank']) for w in found)
        # audit-2: venues x events scan. a route-search program 3/4 (the 40x program) key their struct
        # heaps on int fields, which the compiler now sifts in C (4.6x fewer instructions).
        self.assertEqual(warned, {'audit-ail-2.ail': [(254, 2)]})
        self.assertEqual(len(files), 60)


if __name__ == '__main__':
    unittest.main()
