"""Differential round 86: CPython's 4300-digit int() limit on both builds.

Found with small programs compared against CPython on both builds:

CPython 3.12 refuses `int(<str>)` for more than 4300 digits in every base except
2/4/8/16/32, raising ValueError even when the value is zero. AIL's parser only
bound the int64 value, so `int("0" * 4301)` printed 0 and `int("0" * 4301 + "1")`
printed 1; `int("0" * 4301 + "1", 3)` printed 1. The limit is now checked after
digit validation and before the int64 overflow test, with CPython's message and
its exemptions for power-of-two bases and a base-0 0x/0o/0b prefix.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOUNDARY = r'''def main():
    for n in [4299, 4300, 4301, 5000]:
        for s in ["0" * n, "0" * n + "1", "-" + "0" * n, "-" + "0" * n + "7"]:
            try:
                print(len(s), int(s))
            except ValueError:
                print(len(s), "ValueError")
    print("done")
main()
'''

BASES = r'''def show(label, fn):
    try:
        print(label, fn())
    except ValueError as e:
        print(label, "VE", str(e)[:70])
def main():
    cases = []
    for b in [0, 2, 3, 4, 8, 10, 16, 32, 36]:
        cases.append((b, "0" * 4301))
    for b in [0, 16]:
        cases.append((b, "0x" + "0" * 4301))
    for b, s in cases:
        show("base%d" % b, lambda b=b, s=s: int(s, b))
    show("invalid", lambda: int("z" * 4301))
    show("underscore", lambda: int("0_" * 4301 + "0"))
    show("sign", lambda: int("-" + "0" * 4301))
    show("space", lambda: int("\t" + "0" * 4301 + "\n"))
    show("boundary", lambda: int(" " + "0" * 4300 + " "))
    show("base0digit", lambda: int("0" * 4301 + "1", 0))
    show("base0boundary", lambda: int("0" * 4300 + "1", 0))
    show("base0invalid", lambda: int("0" * 4301 + "z", 0))
    show("base0underscore", lambda: int("0_" * 4301 + "1", 0))
    print("done")
main()
'''

MESSAGES = r'''def main():
    for s in ["abc", "", "1.0", "0" * 4301, "0" * 4300]:
        try:
            print(int(s))
        except ValueError as e:
            print(type(e).__name__, str(e))
    print("done")
main()
'''

VALID = r'''def main():
    print(int("0" * 4300), int("0" * 4299 + "1"), int("-" + "0" * 4299 + "7"))
    print(int("0" * 4300, 0), int("0x" + "0" * 4300, 0), int("0" * 4300, 2))
    print(int("1_0", 2), int(" 0o777 ", 0), int("+0b101", 0), int("-0XfF", 16))
    for s in ["1_", "_1", "1__0", "0x", "", " ", "1.0"]:
        try:
            print(repr(s), int(s, 0))
        except ValueError:
            print(repr(s), "ValueError")
    print("done")
main()
'''

SOURCES = r'''class Box:
    pass
def conv(s):
    try:
        return int(s)
    except ValueError as e:
        return "VE " + str("Exceeds" in str(e))
def baseconv(s, b):
    try:
        return int(s, b)
    except ValueError as e:
        return "VE " + str("Exceeds" in str(e))
def main():
    long0 = "0" * 4301
    xs = [long0, "0" * 4299 + "1"]
    d = {"k": long0}
    box = Box()
    box.s = long0
    for s in [long0, xs[0], xs[1], d["k"], box.s]:
        print(len(s), conv(s))
    for b in [0, 2, 3, 16]:
        print(b, baseconv(long0, b), baseconv(xs[1], b))
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


class Fuzz86Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz86-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_zero_padded_limit(self):
        self.check('boundary', BOUNDARY)

    def test_limit_bases_and_exemptions(self):
        self.check('bases', BASES)

    def test_limit_message(self):
        self.check('messages', MESSAGES)

    def test_below_limit_still_parses(self):
        self.check('valid', VALID)

    def test_limit_through_arguments_and_containers(self):
        self.check('sources', SOURCES)


if __name__ == '__main__':
    unittest.main()
