"""Pre-246: the v1 boxed runtime builds, and INT64_MIN is a legal index.

Two pre-existing differences were recorded by the rbrbpre204 review.

The v1 emitter (``AIL_GENERAL=v1``, used only when the typed path falls back) still carried
unprefixed ``ail_exc_top`` / ``ail_exc_stack`` / ``ail_exc_current`` and its own ``ail_die`` /
``ail_alloc``; the DIE block the same build now pulls in defines those same names, so the C
compiler rejected every such program with ``redefinition of 'ail_exc_top'``.  The v1 frame stack
and current-exception slot now use ``ail_v1_*`` names (and the v1 emitter reads the renamed slot),
and the duplicate ``ail_die`` / ``ail_alloc`` definitions are gone, so the DIE versions are used.

The pre177 constant-index check folded a unary minus operand with the per-step int64 bound, so
``d[-(1 << 63)]`` was refused as ``int64 index out of range: 9223372036854775808`` although the
result ``-9223372036854775808`` is in range and CPython uses it as an ordinary key.  Unary ``-``
(and ``~``) now fold their operand exactly and range-check only the result; a result that still
leaves int64 keeps the by-name refusal.

Both behaviours are checked below on the builds that can show them: the v1 programs force the
general fallback and are compared with CPython, and the index cases use the two cmp.sh builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


V1_DYNAMIC = '''xs = [1, "a", 2.5, None, True]
d = {"k": 1, "j": "two"}
d["x"] = xs
class Box:
    def __init__(self, v):
        self.v = v
b = Box(xs)
b.v = d
print(xs)
print(d)
print(xs[0], xs[1], xs[2], xs[3], xs[4])
print(len(xs), len(d))
for k in d:
    print(k, d[k])
print(b.v["x"][1])
'''

V1_TRY = '''def f(x):
    v = 1
    v = x
    r = ""
    try:
        if v == 0:
            r = str(1 // v)
        elif v == 1:
            raise ValueError("bad")
        elif v == 2:
            r = str([1, 2][5])
        else:
            r = v + "s"
    except ValueError as e:
        r = "value:" + str(e)
    except ZeroDivisionError as e:
        r = "zero:" + str(e)
    except IndexError as e:
        r = "index:" + str(e)
    except TypeError as e:
        r = "type:" + str(e)
    finally:
        print("fin", v)
    return r

for v in [0, 1, 2, 3]:
    print(f(v))
'''

V1_NESTED = '''def g(n):
    v = "x"
    v = n
    try:
        try:
            if v == 1:
                raise ValueError("inner")
            print("ok", v)
        except ValueError as e:
            print("caught", str(e))
            raise
        finally:
            print("finally inner", v)
    except ValueError as e:
        print("outer", str(e))
    finally:
        print("finally outer", v)

g(0)
g(1)
'''

V1_UNCAUGHT = '''v = 1
v = "uncaught"
print("before")
raise ValueError("boom")
'''

V1_HARDSTOP = '''v = 1
v = "x"
print("before")
xs = [1, 2]
print(xs[5])
'''

V1_PROGRAMS = {
    'dynamic': V1_DYNAMIC,
    'try': V1_TRY,
    'nested': V1_NESTED,
    'uncaught': V1_UNCAUGHT,
    'hardstop': V1_HARDSTOP,
}

INDEX_BOUNDS = '''def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)

MIN = -(1 << 63)
MAX = (1 << 63) - 1
d = {MIN: "min", MAX: "max", 0: "zero"}
xs = [10, 20, 30]
show("dict-min", lambda: d[MIN])
show("dict-max", lambda: d[MAX])
show("dict-zero", lambda: d[0])
show("list-min", lambda: xs[MIN])
show("list-max", lambda: xs[MAX])
show("tuple-min", lambda: (1, 2, 3)[MIN])
show("str-min", lambda: "abc"[MIN])
show("bytes-min", lambda: b"abc"[MIN])
show("invert-min", lambda: d[~MIN])
show("invert-min-list", lambda: xs[~MIN])
show("min-plus-one", lambda: d[MIN + 1])
show("min-div-one", lambda: d[MIN // 1])
show("min-times-one", lambda: xs[MIN * 1])
show("shift-min", lambda: d[-(1 << 63)])
show("literal-min", lambda: d[-9223372036854775808])
'''

INDEX_FLOW = '''def at(seq, i):
    return seq[i]

def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)

class Box:
    def __init__(self, i):
        self.i = i

MIN = -(1 << 63)
d = {MIN: "min"}
xs = [10, 20, 30]
show("arg-list", lambda: at(xs, MIN))
show("arg-dict", lambda: at(d, MIN))
show("list-item", lambda: xs[[MIN][0]])
show("dict-value", lambda: d[{"i": MIN}["i"]])
show("attribute", lambda: xs[Box(MIN).i])
show("alias", lambda: xs[MIN])
b = Box(MIN)
b.i = MIN + 0
show("attr-rebind", lambda: d[b.i])
'''

INDEX_REFUSED = {
    'positive_shift': 'xs = [1]\nprint(xs[1 << 63])\n',
    'below_min': 'd = {}\nprint(d[-(1 << 63) - 1])\n',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, mode):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'v1':
        env['AIL_GENERAL'] = 'v1'
    else:
        env['AIL_QUIET_FALLBACK'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _last_line(blob):
    lines = [line for line in blob.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre246Tests(unittest.TestCase):
    def check_v1(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre246-') as directory:
            want, want_rc, want_err = _cpython(directory, slug, text)
            built, exe = _build(directory, slug, text, 'v1')
            output = built.stdout + built.stderr
            self.assertEqual(built.returncode, 0, '%s\n%s' % (slug, output[-4000:]))
            self.assertIn('built on the general path', built.stderr, '%s\n%s' % (slug, output[-4000:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, slug)
            self.assertEqual(got.returncode, want_rc, slug)
            self.assertEqual(_last_line(got.stderr), _last_line(want_err), slug)

    def test_v1_generated_c_compiles_and_matches(self):
        for slug, text in V1_PROGRAMS.items():
            with self.subTest(slug):
                self.check_v1(slug, text)

    def check_index(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre246-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for mode in ('g', 'd'):
                with self.subTest(slug=slug, mode=mode):
                    built, exe = _build(directory, '%s_%s' % (slug, mode), text, mode)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 0, '%s (%s)\n%s' % (slug, mode, output[-4000:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, slug + ' ' + mode)

    def test_int64_min_is_a_legal_index(self):
        self.check_index('bounds', INDEX_BOUNDS)
        self.check_index('flow', INDEX_FLOW)

    def test_out_of_int64_index_still_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre246-') as directory:
            for slug, text in INDEX_REFUSED.items():
                for mode in ('g', 'd'):
                    with self.subTest(slug=slug, mode=mode):
                        built, exe = _build(directory, '%s_%s' % (slug, mode), text, mode)
                        output = built.stdout + built.stderr
                        self.assertEqual(built.returncode, 2, '%s (%s)\n%s' % (slug, mode, output[-4000:]))
                        self.assertFalse(exe.exists(), '%s (%s) built an executable' % (slug, mode))
                        self.assertIn('int64 index out of range', output,
                                      '%s (%s)\n%s' % (slug, mode, output[-4000:]))


if __name__ == '__main__':
    unittest.main()
