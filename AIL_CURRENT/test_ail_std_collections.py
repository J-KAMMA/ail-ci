"""The lab programs in lab/stdlib/collections: each builds with the default pipeline and prints
exactly what CPython prints, with the same exit code.

These are ordinary Python programs using collections the way application code does: Counter
(including tuple keys and mapping literals), defaultdict, OrderedDict, deque, and ChainMap.
Three further programs in the directory are refused by name and recorded in RESULTS.md.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LAB = REPO / 'lab' / 'stdlib' / 'collections'

PROGRAMS = (
    'config_layers',
    'coordinate_freq',
    'counter_edges',
    'graph_bfs',
    'group_anagrams',
    'inventory',
    'queue_sim',
    'sliding_window',
    'word_stats',
)


class StdCollectionsPrograms(unittest.TestCase):
    maxDiff = None

    def test_programs_match_cpython(self):
        env = dict(os.environ)
        for key in ('AIL_NO_GENERAL', 'AIL_STRICT', 'AIL_UNIFIED_FORCE'):
            env.pop(key, None)
        for name in PROGRAMS:
            with self.subTest(program=name):
                source = LAB / (name + '.py')
                self.assertTrue(source.is_file(), source)
                python = subprocess.run([sys.executable, str(source)], capture_output=True,
                                        text=True, timeout=300)
                with tempfile.TemporaryDirectory(prefix='ail-std-collections-') as tmp:
                    exe = Path(tmp) / 'prog'
                    built = subprocess.run(
                        [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                         '--syntax', 'python', '-o', str(exe)],
                        cwd=tmp, capture_output=True, text=True, timeout=900, env=env)
                    self.assertEqual(built.returncode, 0,
                                     '%s did not build:\n%s' % (name, built.stderr[-4000:]))
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
                self.assertEqual(ran.stdout, python.stdout, name)
                self.assertEqual(ran.returncode, python.returncode, name)

    def test_counter_subtract_mapping_forms(self):
        source_text = '''from collections import Counter
from typing import Dict


class Holder:
    def __init__(self) -> None:
        self.counts: Dict[str, int] = {"a": 2}


def main() -> int:
    c = Counter("aab")
    c.subtract({"a": 2})
    print(sorted(c.items()))
    d = {"b": 2}
    c.subtract(d)
    print(sorted(c.items()))
    h = Holder()
    c.subtract(h.counts)
    print(sorted(c.items()))
    t: Counter[tuple[int, int]] = Counter({(1, 2): 3})
    t.subtract({(1, 2): 2})
    print(sorted(t.items()))
    u = {(1, 2): 1}
    t.subtract(u)
    print(sorted(t.items()))
    return 0


main()
'''
        env = dict(os.environ)
        for key in ('AIL_NO_GENERAL', 'AIL_STRICT', 'AIL_UNIFIED_FORCE'):
            env.pop(key, None)
        with tempfile.TemporaryDirectory(prefix='ail-std-collections-') as tmp:
            source = Path(tmp) / 'probe.py'
            source.write_text(source_text, encoding='utf8')
            python = subprocess.run([sys.executable, str(source)], capture_output=True,
                                    text=True, timeout=300)
            exe = Path(tmp) / 'prog'
            built = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                 '--syntax', 'python', '-o', str(exe)],
                cwd=tmp, capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(built.returncode, 0,
                             'counter_subtract_mappings did not build:\n%s' % built.stderr[-4000:])
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        self.assertEqual(ran.stdout, python.stdout)
        self.assertEqual(ran.returncode, python.returncode)


if __name__ == '__main__':
    unittest.main()
