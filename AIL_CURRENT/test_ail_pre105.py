"""A multi-name import refusal names only the module that is not modelled.

Job errmsg3 recorded that `import math, html` printed `import of 'math, html'` as one
unavailable module, which wrongly denies the supported `math`.  The typed path now
picks the first name outside the modelled set (`html`, or `html.parser`), so the
refusal names that module at the import's own line.  The general path already
refuses the use of `html` by name; an unused `html` import still builds on both.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'plain': ('import math, html\n\n\ndef main():\n    print(html)\n\n\nmain()\n', "import of 'html'"),
    'reversed': ('import html, math\n\n\ndef main():\n    print(html)\n\n\nmain()\n', "import of 'html'"),
    'three': ('import math, html, sys\n\n\ndef main():\n    print(html)\n\n\nmain()\n', "import of 'html'"),
    'argument': ('import math, html\n\n\ndef use(mod):\n    return mod\n\n\ndef main():\n'
                 '    print(use(html) is html)\n\n\nmain()\n', "import of 'html'"),
    'list_item': ('import math, html\n\n\ndef main():\n    xs = [html]\n'
                  '    print(len(xs), math.floor(2.5))\n\n\nmain()\n', "import of 'html'"),
    'attribute': ('import math, html\n\n\nclass Holder:\n    pass\n\n\ndef main():\n'
                  '    h = Holder()\n    h.mod = html\n    print(h.mod is html)\n\n\nmain()\n', "import of 'html'"),
    'dict_value': ('import math, html\n\n\ndef main():\n    d = {"h": html}\n'
                   '    print(len(d), math.floor(2.5))\n\n\nmain()\n', "import of 'html'"),
    'dotted': ('import math, html.parser\n\n\ndef main():\n    print(html.parser)\n\n\nmain()\n',
               "import of 'html.parser'"),
}

UNUSED = 'import math, html\n\n\ndef main():\n    print(math.floor(2.5))\n\n\nmain()\n'


def compile_case(directory, text, general):
    src = Path(directory) / 'prog.py'
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', 'prog'], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class MultiNameImportRefusal(unittest.TestCase):
    def test_refusal_names_the_unmodelled_module_only(self):
        for name, (text, expected) in REFUSED.items():
            for general in (True, False):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built = compile_case(directory, text, general)
                    message = built.stdout + built.stderr
                    self.assertIn(built.returncode, (2, 3), message)
                    self.assertFalse(Path(directory, 'prog').exists(), message)
                    self.assertIn('html', message)
                    self.assertNotIn("'math, html'", message)
                    self.assertNotIn("'html, math'", message)
                    self.assertNotIn("'math, html, sys'", message)
                    if not general:
                        self.assertTrue(message.startswith('prog.py:1:1:'), message)
                        self.assertIn(expected, message)

    def test_an_unused_second_import_still_builds(self):
        for general in (True, False):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built = compile_case(directory, UNUSED, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(Path(directory, 'prog'))], capture_output=True, timeout=120,
                                     cwd=directory)
                self.assertEqual(got.stdout, b'2\n')


if __name__ == '__main__':
    unittest.main()
