"""The S-expression surface converts losslessly to and from block syntax and compiles the same.

Every bundled block-syntax source must survive block -> S-expression -> block with an identical
translated AST and imports, and converting the result again must give the same S-expression text.
A program written directly as S-expressions (with contracts) must compile and run.
"""
import ast
import re
import subprocess
import unittest
from pathlib import Path

import ail_sexpr
import ail_syntax
import test_ail_c_objects as support

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''; S-expression surface
(struct Counter (count int))
(impl Counter
  (fn bump (self (by int)) int
    (requires (> by 0))
    (+= self.count by)
    (return self.count)))
(fn isqrt ((n int)) int
  (requires (>= n 0))
  (ensures (cmp (* result result) <= n < (* (+ result 1) (+ result 1))))
  (let r int 0)
  (while (<= (* (+ r 1) (+ r 1)) n) (+= r 1))
  (return r))
(fn main () int
  (let c Counter (Counter 0))
  (for i (range 1 4) (c.bump i))
  (let words (list str) (.split "a,b,c" ","))
  (print (isqrt (int (@ sys.argv 1))) c.count (len words) (@ words -1) :sep "|")
  (return 0))
'''


class SexprTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_bundled_sources_round_trip(self):
        checked = 0
        for path in sorted((ROOT / 'language_examples').glob('*.ail')):
            source = path.read_text(encoding='utf8')
            entry = re.search(r'^\s*fn\s+main\s*\(', source, re.M) is not None
            first = []
            try:
                translated = ail_syntax.translate(source, module=not entry, imports=first)
            except ail_syntax.SyntaxErrorAIL:
                continue
            with self.subTest(path.name):
                sexpr = ail_sexpr.to_sexpr(source)
                block = ail_sexpr.to_block(sexpr)
                second = []
                again = ail_syntax.translate(block, module=not entry, imports=second)
                self.assertEqual(ast.dump(ast.parse(translated)), ast.dump(ast.parse(again)))
                self.assertEqual(first, second)
                self.assertEqual(ail_sexpr.to_sexpr(block), sexpr)
            checked += 1
        self.assertGreater(checked, 200)

    def test_sexpr_program_compiles_and_runs(self):
        source = self.write('program.ail', PROGRAM)
        output = self.root / 'program'
        result = self.command('compile', source, '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        binary = output if output.exists() else output.with_suffix('.exe')
        run = subprocess.run([str(binary), '17'], capture_output=True, timeout=30)
        self.assertEqual((run.returncode, run.stdout), (0, b'4|6|3|c\n'))
        failed = subprocess.run([str(binary), '-1'], capture_output=True, timeout=30)
        self.assertEqual(failed.returncode, 1)
        self.assertIn(b'requires failed in isqrt: n >= 0', failed.stderr)

    def test_form_word_names_are_refused(self):
        with self.assertRaises(ail_sexpr.SexprError):
            ail_sexpr.to_sexpr('fn main() -> int { let neg = 1; return neg; }\n')


if __name__ == '__main__':
    unittest.main()
