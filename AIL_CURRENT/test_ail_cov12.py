"""cov12: a conditional that mixes a str sentinel with a number in a print/f-string.

The typed path has one static type per expression, so ``print(v if v is not None else "none")``
used to stop with ``a str constant 'none' used where a number is needed`` even though CPython
converts the chosen value to a str at that position.  ``iterlower`` now wraps the non-literal arm
of such a conditional in ``str()`` when it is a print argument, or an f-string field with no
conversion and no format spec -- the same conversion CPython applies.  A field with ``!r`` or a
format spec is left alone and stays a named refusal, because ``format()`` may differ from ``str``.
Programs that bind ``print`` or ``str`` are untouched, as is the conditional optlib already builds
for an Optional value (``best__v if best__p else "None"``).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REFUSAL = "a str constant 'none' used where a number is needed"

PROGRAMS = {}
PROGRAMS['routes'] = r'''class Box:
    def __init__(self, v):
        self.v = v

def pick(v, missing):
    return v if v is not None else missing

b = Box(31)
xs = [41, 0]
d = {"k": 51}
print(7 if True else "none")
print(7 if False else "none")
print(-3 if True else "none")
print(0 if True else "none")
print(9223372036854775807 if True else "none")
print(1.5 if True else "none")
print(-0.0 if True else "none")
print(1e300 if True else "none")
print(True if True else "none")
print(False if True else "none")
print("none" if False else -42)
print(pick(11, "none"))
print(pick(None, "none"))
print(xs[0] if xs[1] == 0 else "none")
print(b.v if b.v else "none")
print(d["k"] if "k" in d else "none")
print(pick(b.v, "none") if xs[0] else "none")
print("none" if not b.v else d["k"])
'''
PROGRAMS['fstrings'] = r'''v = 9
s = "none"
print(f"{v if v > 5 else s}")
print(f"a {v if v > 5 else s} b {s if v < 5 else v} c")
text = f"{v if v < 5 else s}"
print(text)
print(f"{v if v > 5 else 'none':}")
print(v if v else "none", sep="-")
print(v if not v else "none", end="!\n")
'''


PROGRAMS['optional'] = r'''def smallest(xs):
    best = None
    for x in xs:
        if best is None or x < best:
            best = x
    print(f"{best} {best}")
    print(best)

def last_word(words):
    last = None
    for word in words:
        last = word
    print(f"{last!s}")
    print(last)

smallest([3, 1, 2, 9])
last_word(["alpha", "beta"])
print(4 if 4 is not None else "None")
'''
PROGRAMS['plain'] = r'''v = 4
print(v if v else 99)
print(1.5 if v else 2.5)
print("yes" if v else "no")
print(f"{'yes' if v else 'no'}")
print(v)
print("unchanged")
'''
PROGRAMS['nonnumber'] = r'''class U:
    def __init__(self, v):
        self.v = v
    def __str__(self):
        return "U<%d>" % self.v
u = U(6)
print(u if u.v else "none")
print(f"{u if u.v else 'none'}")
print([1, 2] if u.v else "none")
'''
REFUSED = {
    'format_spec': 'v = 3\nprint(f"{v if v is not None else \'none\':>8}")\n',
    'conversion': 'v = 3\nprint(f"{v if v is not None else \'none\'!r}")\n',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general, typed_only=False):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    else:
        env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Cov12Tests(unittest.TestCase):
    def test_mixed_conditionals_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov12-') as directory:
            for slug, text in PROGRAMS.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_format_spec_and_conversion_stay_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov12-') as directory:
            for slug, text in REFUSED.items():
                _, built = build(directory, slug, text, False, typed_only=True)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, (slug, output[-1200:]))
                self.assertIn(REFUSAL, output, (slug, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
