"""pre346: each test module is assigned to exactly one CI shard.

The pre334 review recorded that `tools/ci_shards.py --check` failed because four modules
(`test_ail_fuzz4`, `test_ail_pre126`, `test_ail_pre59`, `test_ail_pre61`) were listed twice in
`ail_check.MODULES`, so `--update` placed each of them on two shards.  The module list is now
unique, and a stale assignment file cannot reintroduce a duplicate: `build()` keeps only the
first placement of each module.
"""
import collections
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
TOOLS = REPO / 'tools'
sys.path.insert(0, str(ROOT))

import ail_check


def load_ci_shards():
    spec = importlib.util.spec_from_file_location('ci_shards_pre346', TOOLS / 'ci_shards.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CiShardsAssignment(unittest.TestCase):
    def test_module_list_has_no_duplicates(self):
        counts = collections.Counter(ail_check.MODULES)
        self.assertEqual([name for name, count in counts.items() if count > 1], [])
        counts = collections.Counter(load_ci_shards().all_modules())
        self.assertEqual([name for name, count in counts.items() if count > 1], [])

    def test_assignment_places_every_module_once(self):
        data = json.loads((TOOLS / 'ci_shards.json').read_text(encoding='utf-8'))
        mapped = [name for members in data['assignment'] for name in members]
        self.assertEqual(len(mapped), len(set(mapped)),
                         'duplicated: %s' % ' '.join(sorted(
                             name for name, count in collections.Counter(mapped).items() if count > 1)))
        self.assertEqual(set(mapped), set(ail_check.MODULES))

    def test_check_passes(self):
        result = subprocess.run([sys.executable, str(TOOLS / 'ci_shards.py'), '--check'],
                                cwd=str(REPO), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_build_drops_duplicate_placements(self):
        ci = load_ci_shards()
        previous = {
            'shards': 3,
            'jobs': 4,
            'weights': {'a': 1.0, 'b': 1.0, 'c': 1.0},
            'assignment': [['a', 'b'], ['b', 'c'], ['a']],
        }
        data = ci.build(['a', 'b', 'c', 'a'], {}, previous, False)
        self.assertEqual(data['assignment'], [['a', 'b'], ['c'], []])
        data = ci.build(['a', 'b', 'a'], {}, previous, True)
        mapped = [name for members in data['assignment'] for name in members]
        self.assertEqual(sorted(mapped), ['a', 'b'])


if __name__ == '__main__':
    unittest.main()
