"""`_load_sources` must return the same merged text and the same other values after the
load-time work is memoised.

The expected digests below were taken from the base build (before the per-function scan data
was cached and before the checks for shapes a tree does not contain were short-circuited).
They cover the merged text, the contracts flag, the unit map, the notes and the source map
for three of the ten `lab/compare/src` tasks, whose `main.ail` is what `compile` loads.
The augmented-power refusals are pinned by name because that is the check whose scan was
memoised.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))

import ail_chatgpt  # noqa: E402

TASKS = {
    'chain_relax': '4cff12957857683859f08dda0c1bc096dfcf3c945b970091ef78596475cc84ac',
    'tally_lang': '90bb00e5967df824378c671bd8206c17ae15771b1a0d2a7c981e1fff21235f93',
    'tree_fold': 'c3c4986f2f1b006547544c58619462a20c75df3e6f8aaaf5c52e75955c985096',
}

RANGE_MESSAGE = 'int64 constant expression out of range: 10000000000000000000000000000000000000000'

DIRECT = 'fn main() -> int {\n    let b = 10;\n    b **= 40;\n    print(b);\n    return 0;\n}\n'
ROUTED = ('fn power(b: int, e: int) -> int {\n    b **= e;\n    return b;\n}\n\n'
          'fn main() -> int {\n    print(power(10, 40));\n    return 0;\n}\n')
IN_RANGE = 'fn main() -> int {\n    let b = 10;\n    b **= 2;\n    print(b);\n    return 0;\n}\n'


def dump_hash(path):
    notes = {}
    source_map = {}
    text, contracts, unit_map = ail_chatgpt._load_sources(
        path, (), 'auto', local_imports=True, notes=notes, source_map=source_map)
    payload = {'text': text, 'contracts': contracts,
               'unit_map': {str(key): value for key, value in unit_map.items()},
               'notes': {str(key): list(value) for key, value in notes.items()},
               'source_map': {str(key): repr(value) for key, value in source_map.items()}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=repr).encode('utf8')).hexdigest()


def load_text(text):
    directory = tempfile.mkdtemp()
    path = Path(directory) / 'main.ail'
    path.write_text(text, encoding='utf8')
    return ail_chatgpt._load_sources(path, (), 'auto', local_imports=True, notes={}, source_map={})


class DumpSame(unittest.TestCase):
    def test_compare_task_dumps(self):
        for task, expected in sorted(TASKS.items()):
            with self.subTest(task=task):
                source = ROOT.parent / 'lab' / 'compare' / 'src' / task / 'main.ail'
                self.assertEqual(dump_hash(source), expected)

    def test_direct_augmented_power_still_refused(self):
        with self.assertRaises(ValueError) as caught:
            load_text(DIRECT)
        self.assertIn(RANGE_MESSAGE, str(caught.exception))

    def test_routed_augmented_power_still_refused(self):
        with self.assertRaises(ValueError) as caught:
            load_text(ROUTED)
        self.assertIn(RANGE_MESSAGE, str(caught.exception))

    def test_in_range_augmented_power_is_built(self):
        text, _, _ = load_text(IN_RANGE)
        self.assertIn('b **=', text)


if __name__ == '__main__':
    unittest.main()
