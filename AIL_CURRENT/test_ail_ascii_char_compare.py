"""One-character str == / != an ASCII literal compares the first byte; answers match CPython.

Multi-byte characters (whose lead or continuation bytes might be mistaken for ASCII if the test
were wrong), combining marks, an empty loop over "", and s[i] indexing, including negative
indexes, all have to give the same counts as Python.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let quotes: int = 0;
    let commas: int = 0;
    let others: int = 0;
    for c in text {
        if c == "\"" { quotes += 1; }
        if c != "," { others += 1; } else { commas += 1; }
    }
    let empty: int = 0;
    for c in "" { if c == "a" { empty += 1; } }
    let hits: int = 0;
    for i in range(len(text)) {
        if text[i] == "a" or text[-1 - i] == "\n" { hits += 1; }
    }
    print(quotes, commas, others, empty, hits);
    return 0;
}'''

ALPHABET = ['a', 'b', '"', ',', '\n', ' ', 'é', '日', '😀', '́', '¢', '߿', '￿', 'A']


class AsciiCharCompareTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_matches_cpython(self):
        program = build(self, 'ascii_char_compare', SOURCE)
        rng = random.Random(20261011)
        for case in range(120):
            text = ''.join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 40)))
            path = self.root / 'text.txt'
            path.write_bytes(text.encode('utf-8'))
            result = subprocess.run([str(program), str(path)], capture_output=True, timeout=30)
            quotes = text.count('"')
            commas = text.count(',')
            hits = sum(1 for i in range(len(text)) if text[i] == 'a' or text[-1 - i] == '\n')
            expected = '%d %d %d 0 %d\n' % (quotes, commas, len(text) - commas, hits)
            self.assertEqual((result.returncode, result.stdout.decode()), (0, expected), repr(text))


if __name__ == '__main__':
    unittest.main()
