"""Refusals of constructs LLM-written programs guess say where and what to write instead."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

CASES = [
    # Bytes-expression loops, `ba[i] += v`, `return [0] * n` and self-referential structs used to be
    # refused here; they compile now (test_ail_for_bytes_expr.py, test_ail_optional_structs.py).
    ('fn f(xs: list[int]) -> void { xs.append(1); }\nfn main() { let a = [1]; f(a); print(a[0]); }',
     'prog.ail:1:', 'keep the list in a struct field'),
]


class RefusalHints(unittest.TestCase):
    def test_refusals_locate_and_name_the_rewrite(self):
        for source, where, hint in CASES:
            with self.subTest(source=source[:50]), tempfile.TemporaryDirectory() as tmp:
                Path(tmp, 'prog.ail').write_text(source + '\n', encoding='utf-8')
                proc = subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                                       'prog.ail', '-o', 'prog'], cwd=tmp, capture_output=True,
                                      text=True, timeout=300)
                self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
                self.assertTrue(proc.stderr.startswith(where), proc.stderr)
                self.assertIn(hint, proc.stderr)
                self.assertFalse(Path(tmp, 'prog').exists())


if __name__ == '__main__':
    unittest.main()
