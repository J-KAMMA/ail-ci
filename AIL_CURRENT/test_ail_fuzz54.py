"""Differential round 54: a mixed list display keeps each element's own type.

Found with small random programs compared against CPython on both builds:

`print([["a"], {"x": "y"}])` printed the dict as a list of its keys once the
tuple pass emitted its rewritten source.  `Exprs.seq_type` took the type of the
first known element (list[str]) and silently dropped later, incompatible
elements (the dict), so `tupcalls.printable` chose the list-of-list repr helper
and that helper iterated the dict.  The rewrite is only used when some other
statement forces it (here `repr(xs)`), which is why the same display printed
correctly on its own.

Incompatible element types now refuse the tuple rewrite, leaving the source as
written so the generic path prints the real objects.  The programs below keep
the shape compared with CPython on both builds, including homogeneous nested
lists and dicts that must keep using the typed path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MIXED_DISPLAY = r'''def main() -> None:
    xs: list[str] = ["plain", "a\\b", "a\nb"]
    print(xs)
    d: dict[str, list[str]] = {"k": xs}
    print(d)
    print([["a\nb"], {"x": "a\\b"}])
    print([{"x": "a\\b"}, ["a\nb"]])
    print([[1], {"x": 2}])
    print([1, [2]])
    print([[3], 4])
    print([["a"], {}])
    print({"mix": [1], "text": "s"})
    alias = d
    print(alias)
    print(f"{[['a'], {'x': 'y'}]}")
    print(repr(xs))
    print([["a\nb"], {"x": "a\\b"}])
    print("done")


main()
'''

HOMOGENEOUS = r'''def main() -> None:
    rows: list[list[str]] = [["a"], ["b", "c"]]
    maps: list[dict[str, str]] = [{"x": "y"}, {"k": "v"}]
    print(rows)
    print(maps)
    print(rows, maps)
    print(repr(rows), repr(maps))
    print(f"{rows} {maps}")
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz54Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz54-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_mixed_display_keeps_dict(self):
        self.check('mixed_display', MIXED_DISPLAY)

    def test_homogeneous_nested_displays(self):
        self.check('homogeneous', HOMOGENEOUS)


if __name__ == '__main__':
    unittest.main()
