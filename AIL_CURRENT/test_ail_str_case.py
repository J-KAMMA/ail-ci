"""str.lower() / str.upper() match CPython for every code point and for Final_Sigma contexts.

Every code point (surrogates excluded) is lowered and uppered on its own line; then random strings
built from cased letters, case-ignorable characters (apostrophes, combining marks, modifier
letters), Greek capital sigma, spaces and punctuation check the context-dependent final sigma.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let out: list[str] = [];
    for line in text.split("\n") {
        out.append(line.lower() + "\t" + line.upper());
    }
    write_stdout_bytes("\n".join(out).encode("utf-8"));
    return 0;
}'''

PIECES = ['Σ', 'σ', 'ς', 'Α', 'a', 'Z', "'", '́', 'ʰ', '·', ' ', '.', '1', 'İ', 'ß', 'ΐ',
          '’', 'ͅ', 'ǅ', '\U00010400', '日']


class StrCaseTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def check(self, program, lines):
        path = self.root / 'case.txt'
        path.write_bytes('\n'.join(lines).encode('utf-8'))
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        got = result.stdout.decode('utf-8').split('\n')
        want = ['%s\t%s' % (line.lower(), line.upper()) for line in lines]
        self.assertEqual(len(got), len(want))
        bad = [(lines[i], got[i], want[i]) for i in range(len(want)) if got[i] != want[i]]
        self.assertFalse(bad, bad[:10])

    def test_every_code_point_and_sigma_contexts(self):
        program = build(self, 'str_case', SOURCE)
        singles = [chr(cp) for cp in range(1, 0x110000) if cp != 10 and not 0xD800 <= cp <= 0xDFFF]
        self.check(program, singles)
        rng = random.Random(20261012)
        contexts = [''.join(rng.choice(PIECES) for _ in range(rng.randrange(1, 9))) for _ in range(20000)]
        self.check(program, contexts)


if __name__ == '__main__':
    unittest.main()
