"""pre34: a literal `%d` accepts a float and truncates it toward zero.

CPython's `%` formatting converts a real number for `%d`/`%i`/`%u` with
`int(value)` rules: `"%d%%" % 60.0654` is `60%`, NaN raises
`ValueError: cannot convert float NaN to integer`, infinity raises
`OverflowError`, and a non-number raises
`TypeError: %d format: a real number is required, not str`.

The general path's literal-`%d` fast path passed the operand to
`ail_obj_format`, which only accepted int/bool, so a float percentage died with
`TypeError: unsupported format string passed to non-int` and a non-number got
the wrong message.  `%i`, `%u` and a computed template already went through
`safetyrt.ail2f_percent`, which implements CPython's rules; the literal `%d`
path now keeps the direct formatter for int/bool and sends the other values to
that same runtime.  DIFFERENCES C?-job-pre34-10240952-1.

The residual is the language's int64 limit: a finite float outside int64 is a
big integer in CPython, and stays the documented `integer overflow` limit here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


FLOAT_PERCENT = '''class Box:
    def __init__(self, value):
        self.value = value


def pct(part, whole):
    return 100.0 * part / whole


def render(x):
    return "%d%%" % x


def main():
    part = 60
    whole = 100
    print("%d%%" % pct(part, whole))
    print(render(pct(part, whole)))
    print("%d%%" % [60.0654, 31.7053, 2.3492][0])
    boxes = [Box(60.0654)]
    print("%d%%" % boxes[0].value)
    d = {"pct": 60.0654}
    print("%d%%" % d["pct"])
    for x in [0.0, 1.0, 1.9, -1.9, -0.9, 0.5, 12345.6789, -12345.6789,
              1e15, 9.2233720368547748e18, -9223372036854775808.0]:
        print("%d" % x, "%i" % x, "%u" % x, "%5d" % x, "%-5d|" % x,
              "%05d" % x, "%+d" % x)


main()
'''

NON_NUMBER = '''def main():
    for v in ["x", [1], None, {"a": 1}, (1,), 1.5, True, 7]:
        try:
            print("%d" % v)
        except (TypeError, ValueError) as e:
            print(type(e).__name__, e)


main()
'''

NONFINITE = '''def main():
    for v in [float("nan"), float("inf"), float("-inf")]:
        try:
            print("%d%%" % v)
        except (OverflowError, ValueError) as e:
            print(type(e).__name__, e)


main()
'''

OTHER_FORMS = '''def main():
    x = 60.0654
    print("%i" % x, "%u" % x)
    f = "%d%%"
    print(f % x)
    print(("%i" + "") % x, ("%u" + "") % x)
    print("%.1f%%" % x, "%.2f%%" % (100.0 * 2 / 3))
    print("%.3d|%#d|%#o|%#x" % (x, 7, 8, 255))
    print("%(pct)d%%" % {"pct": x})
    print("%d %s %d" % (x, "mid", -x))
    print(f"{x:.1%}")
    print("{}".format(x), format(x, ".2f"))


main()
'''


class Pre34Tests(unittest.TestCase):
    def check_matches(self, directory, name, text):
        want, rc = cpython(directory, name, text)
        self.assertEqual(rc, 0)
        for general in (True, False):
            with self.subTest(name=name, general=general):
                exe, built = build(directory, name + ('g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, general))
                self.assertEqual(got.returncode, rc, (name, general))

    def test_percent_d_float_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre34-') as directory:
            self.check_matches(directory, 'float_percent', FLOAT_PERCENT)

    def test_percent_d_non_number_message_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre34-') as directory:
            self.check_matches(directory, 'non_number', NON_NUMBER)

    def test_percent_d_nonfinite_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre34-') as directory:
            self.check_matches(directory, 'nonfinite', NONFINITE)

    def test_other_percent_and_format_forms_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre34-') as directory:
            self.check_matches(directory, 'other_forms', OTHER_FORMS)


if __name__ == '__main__':
    unittest.main()
