"""Dict fields keep value semantics when the compiler moves instead of copying.

`let d = obj.field` copies once straight out of the field, and `obj.field = d` moves `d` when it is
a top-level statement and the last mention of `d`. Every case here would print a different answer
if a move leaked into a place where the local or the field can still be observed.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = 'import sys\n\nclass Box:\n\n    def __init__(self, counts: dict[str, int]):\n        self.counts = counts\n\ndef pick(b: Box, d: dict[str, int]) -> Box:\n    return b\n\ndef last_use(b: Box) -> None:\n    d: dict[str, int] = b.counts\n    d[\'moved\'] = 1\n    b.counts = d\n\ndef used_after(b: Box) -> int:\n    d: dict[str, int] = b.counts\n    d[\'kept\'] = 2\n    b.counts = d\n    d[\'after\'] = 3\n    return len(d)\n\ndef in_loop(b: Box) -> int:\n    d: dict[str, int] = {}\n    for i in range(3):\n        d[str(i)] = i\n        b.counts = d\n    return len(d)\n\ndef rebound(b: Box) -> int:\n    d: dict[str, int] = {\'a\': 1}\n    b.counts = d\n    d = {\'z\': 9}\n    return len(d)\n\ndef through_receiver(b: Box) -> None:\n    d: dict[str, int] = {\'r\': 5}\n    pick(b, d).counts = d\n\ndef main() -> int:\n    b = Box({\'start\': 0})\n    alias = b\n    snapshot: dict[str, int] = b.counts\n    snapshot[\'local\'] = 7\n    if \'local\' in b.counts:\n        return 1\n    last_use(b)\n    if len(alias.counts) != 2 or alias.counts[\'moved\'] != 1:\n        return 2\n    if \'local\' in alias.counts:\n        return 3\n    if used_after(b) != 4:\n        return 4\n    if len(b.counts) != 3 or \'after\' in b.counts:\n        return 5\n    if in_loop(b) != 3 or len(b.counts) != 3 or b.counts[\'2\'] != 2:\n        return 6\n    if rebound(b) != 1 or len(b.counts) != 1 or b.counts[\'a\'] != 1:\n        return 7\n    through_receiver(b)\n    if len(b.counts) != 1 or b.counts[\'r\'] != 5:\n        return 8\n    other = Box({\'x\': 1})\n    other.counts = b.counts\n    b.counts[\'r\'] = 6\n    if other.counts[\'r\'] != 5:\n        return 9\n    print(\'ok\')\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


class MapFieldMoveTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_moves_keep_value_semantics(self):
        program = build(self, 'map_field_moves', SOURCE)
        result = subprocess.run([str(program)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, b'ok\n'), result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
