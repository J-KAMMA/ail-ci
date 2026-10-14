"""str.splitlines() on UTF-8 text matches CPython, both as a list and as a `for` loop.

The boundary set includes U+0085, U+2028 and U+2029, whose UTF-8 bytes overlap the continuation
bytes of ordinary characters (U+0145 is C5 85, U+2026 is E2 80 A6, U+00A8 is C2 A8): testing single
bytes split those characters in half.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


ALPHABET = ['a', 'Z', ' ', '\n', '\r', '\r\n', '\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\x1f',
            '\x85', ' ', ' ', 'Ņ', '…', '¨', '©', '‧', '‪',
            'あ', '\U0001f600', 'é']

SOURCE = r'''fn main() -> int {
    let lines: list[str] = read_bytes(sys.argv[1]).decode("utf-8").split("\u{0}");
    for text in lines {
        let parts: list[str] = text.splitlines();
        let looped: list[str] = [];
        for line in text.splitlines() { looped.append(line); }
        if "|".join(parts) != "|".join(looped) { print("loop differs"); return 1; }
        let lengths: list[str] = [];
        for p in parts { lengths.append(str(len(p))); }
        print(str(len(parts)) + ":" + ",".join(lengths));
    }
    return 0;
}'''.replace('"\\u{0}"', 'chr(0)')


class SplitlinesUtf8Tests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_matches_cpython(self):
        rng = random.Random(2026_10_11)
        cases = [''.join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 12))) for _ in range(400)]
        cases += ['aŅb\nc\x85d e', '\r\n\r\n', '……', 'x ', '\x85']
        program = build(self, 'splitlines_utf8', SOURCE)
        data = self.root / 'cases.txt'
        data.write_bytes('\0'.join(cases).encode('utf8'))
        result = subprocess.run([str(program), str(data)], capture_output=True, timeout=60)
        expected = ''.join('%d:%s\n' % (len(c.splitlines()), ','.join(str(len(p)) for p in c.splitlines()))
                           for c in cases)
        self.assertEqual((result.returncode, result.stdout.decode()), (0, expected),
                         result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
