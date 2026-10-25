"""Silent differences in string padding/alignment with format specs (fuzz76).

The IR path dropped every fill character of a str field (`{s:*^8}`, `{s:é>6}`), printing spaces, and the
general path kept the fill in a `char`, so a fill outside Latin-1 (for example `日`) became its low byte
(`å`). Both now keep the whole code point. The same narrow `char` in the general runtime's numeric padding
is fixed too. The programs below are compared with CPython on the default build and on the forced general
path, including empty/zero/negative values, a width narrower than the text, and width combined with
precision. Values reach the fields through an argument, a list item, a dict value and an attribute.

Known differences left in this area (not this fix): the IR path still does not build `=` alignment or a
sign flag on an int/float spec (it aligns right and drops the sign), so those are not in the passing
programs; the wrong-type probes raise a different exception class than CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STRING_FILL = '''
from dataclasses import dataclass


@dataclass
class Box:
    s: str


def show(s: str) -> None:
    print(f"[{s:*^9}]", f"[{s:é>7.2}]", f"[{s:.1}]")


def main() -> None:
    xs: list[str] = ["ab", "日本語"]
    d: dict[str, str] = {"k": "xy"}
    b: Box = Box("日x")
    print(f"[{'ab':é>6}]", f"[{'ab':日<6}]", f"[{'ab':日^7}]")
    print(f"[{'':>3}]", f"[{'x':0}]", f"[{'abcdef':3}]")
    print(f"[{'abcdef':8.3}]", f"[{'abcdef':>8.3}]", f"[{'abcdef':*^10.3}]")
    print(f"[{'日本語abc':日^9.3}]", f"[{'日本語abc':é>9.2}]", f"[{'':*^5.0}]")
    show(xs[0])
    show(xs[1])
    print(f"[{d['k']:*<6}]", f"[{b.s:日^6}]", f"[{b.s:.1}]")


main()
'''

NUMERIC_FILL = '''
def main() -> None:
    print(f"[{42:日^8d}]", f"[{-42:é>9d}]")
    print(f"[{-3.5:日<10.2f}]", f"[{3.5:é^11.1f}]")
    print(f"[{0:*^5d}]", f"[{-1:*^5d}]")


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


class Fuzz76Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz76-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_str_fill_and_alignment(self):
        self.check('str_fill', STRING_FILL)

    def test_numeric_fill_code_point(self):
        self.check('num_fill', NUMERIC_FILL)


if __name__ == '__main__':
    unittest.main()
