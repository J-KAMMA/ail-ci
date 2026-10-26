"""The constant index ``(-2 ** 63) // (2 ** 63)`` is refused by name (job pre276).

The reviewer of job rbpre47 recorded this as a pre-existing difference: CPython
evaluates the expression to -1 and indexes the last item, while AIL refuses it at
compile time as ``int64 index out of range`` because the positive operand
``2 ** 63`` leaves int64.  The task accepts a named compile-time refusal, and both
builds already give one, so no compiler change is needed; this module pins that
refusal for a list and the other indexable receivers.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INDEX_REFUSED = {
    'list': 'print([1, 2, 3][(-2 ** 63) // (2 ** 63)])\n',
    'tuple': 'print((1, 2, 3)[(-2 ** 63) // (2 ** 63)])\n',
    'str': 'print("abc"[(-2 ** 63) // (2 ** 63)])\n',
    'bytes': 'print(b"abc"[(-2 ** 63) // (2 ** 63)])\n',
    'dict': 'print({-1: "minus"}[(-2 ** 63) // (2 ** 63)])\n',
    'name': 'xs = [1, 2, 3]\nprint(xs[(-2 ** 63) // (2 ** 63)])\n',
}


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre276Tests(unittest.TestCase):
    def test_constant_index_with_wide_operand_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre276-') as directory:
            for slug, text in INDEX_REFUSED.items():
                for general in (True, False):
                    with self.subTest(slug=slug, general=general):
                        built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                            text, general)
                        output = built.stdout + built.stderr
                        self.assertEqual(built.returncode, 2, '%s\n%s' % (slug, output[-4000:]))
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertIn('int64 index out of range', output, output[-4000:])


if __name__ == '__main__':
    unittest.main()
