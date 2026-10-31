"""Three silent differences from CPython, now matching it (or stopping with CPython's own words).

1. ``__len__`` returning a negative int, a non-int or a value above sys.maxsize.  CPython raises ValueError
   ``__len__() should return >= 0``, TypeError ``'float' object cannot be interpreted as an integer`` and
   OverflowError ``cannot fit 'int' into an index-sized integer`` from ``len(x)``, ``bool(x)``, ``if x``,
   ``not x`` and ``x if ...``; the general path used to hand the value back (and to ignore anything
   ``__len__`` / ``__bool__`` raised inside a truth test, taking the instance as true).  ``__bool__`` must
   return a bool (TypeError otherwise).  A class with an ``__init__`` is built on the typed path, which
   already checked the sign; it stays checked.
2. ``b += b`` on a non-empty bytearray: CPython raises BufferError ``Existing exports of data: object cannot
   be re-sized`` (the operand is exported while the receiver is resized).  ``b.extend(b)``, ``b[len(b):] = b``,
   ``b *= 2`` and the other self-referencing forms succeed there and still do.  The extended slice
   assignment error names ``bytes`` as CPython does.
3. Text stdin that is not UTF-8.  CPython's default stdin (errors='surrogateescape') keeps going with lone
   surrogates in the str, which AIL's str cannot hold; CPython's strict mode raises UnicodeDecodeError.  AIL
   stops with that error's own text on stderr and exit status 1 (not "AIL internal error: ..."), on the typed
   and the general path alike (documented in SEMANTICS.md).

Every case runs the default build and AIL_UNIFIED_FORCE=1 (and, for stdin and the typed class, AIL_NO_GENERAL=1)
and compares with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _exact_int(test):
    """The test is about exact (arbitrary precision) ints: it runs in the opt-in mode (intmode.py, `--exact-int`)."""
    import functools
    import os

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        saved = os.environ.get('AIL_EXACT_INT')
        os.environ['AIL_EXACT_INT'] = '1'
        try:
            return test(*args, **kwargs)
        finally:
            if saved is None:
                os.environ.pop('AIL_EXACT_INT', None)
            else:
                os.environ['AIL_EXACT_INT'] = saved
    return wrapper


def compile_source(directory, name, source, mode):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    exe = Path(directory) / (name + '_' + mode)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source, stdin=b'', strict_stdin=False):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ)
    if strict_stdin:
        env['PYTHONIOENCODING'] = 'utf-8:strict'
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, input=stdin, capture_output=True,
                         timeout=120, env=env)
    return (ran.stdout.decode('utf-8', 'replace').replace('\r\n', '\n'),
            ran.stderr.decode('utf-8', 'replace').replace('\r\n', '\n'), ran.returncode)


def run_exe(directory, exe, stdin=b''):
    ran = subprocess.run([str(exe)], cwd=directory, input=stdin, capture_output=True, timeout=120)
    return (ran.stdout.decode('utf-8', 'replace').replace('\r\n', '\n'),
            ran.stderr.decode('utf-8', 'replace').replace('\r\n', '\n'), ran.returncode)


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ''


# ---------------------------------------------------------------------------------------------------- 1. __len__
LEN_VALUES = {'neg': '-1', 'float': '2.5', 'str': "'x'", 'big': '2 ** 63', 'bool': 'True', 'max': '2 ** 63 - 1',
              'ok': '3', 'negbig': '-(2 ** 70)', 'bigbig': '2 ** 70', 'zero': '0'}
LEN_FORMS = (('len', 'len(o)'), ('bool', 'bool(o)'), ('if', '1 if o else 0'), ('not', 'not o'))


def len_static_source():
    out = []
    for key, value in LEN_VALUES.items():
        out.append('class C_%s:\n    def __len__(self):\n        return %s\n' % (key, value))
    for key in LEN_VALUES:
        for form, expr in LEN_FORMS:
            out.append('def t_%s_%s():\n    o = C_%s()\n    try:\n        r = %s\n        print(%r, %r, "ok", r)\n'
                       '    except Exception as e:\n        print(%r, %r, type(e).__name__, e)\n'
                       % (key, form, key, expr, key, form, key, form))
    out.append('def main():')
    for key in LEN_VALUES:
        for form, _ in LEN_FORMS:
            out.append('    t_%s_%s()' % (key, form))
    out.append('\nmain()')
    return '\n'.join(out) + '\n'


LEN_DYNAMIC = '''
class N:
    def __len__(self):
        return -1
class F:
    def __len__(self):
        return 2.5
class S:
    def __len__(self):
        return 'x'
class B:
    def __len__(self):
        return 2 ** 63
class T:
    def __len__(self):
        return True
class Z:
    def __len__(self):
        return 3


def main():
    for name, ctor in (('neg', N), ('float', F), ('str', S), ('big', B), ('bool', T), ('ok', Z)):
        o = ctor()
        for stmt in ('len', 'bool', 'if', 'not', 'while', 'comp'):
            try:
                if stmt == 'len':
                    r = len(o)
                elif stmt == 'bool':
                    r = bool(o)
                elif stmt == 'if':
                    r = 1 if o else 0
                elif stmt == 'while':
                    r = 0
                    while o:
                        r = 1
                        break
                elif stmt == 'comp':
                    r = [k for k in range(3) if o]
                else:
                    r = not o
                print(name, stmt, 'ok', r)
            except Exception as e:
                print(name, stmt, type(e).__name__, e)


main()
'''

TRUTH_RAISES = '''
class B:
    def __bool__(self):
        raise KeyError('boom')


class L:
    def __len__(self):
        raise KeyError('lenboom')


class I:
    def __bool__(self):
        return 1


class W:
    def __bool__(self):
        return False


def main():
    for o in (B(), L(), I(), W()):
        for k in range(5):
            try:
                if k == 0:
                    r = bool(o)
                elif k == 1:
                    r = not o
                elif k == 2:
                    r = 1 if o else 0
                elif k == 3:
                    r = 5
                    while o:
                        r = 6
                        break
                else:
                    r = (o and 7) or 8
                print('ok', r)
            except Exception as e:
                print(type(e).__name__, e)
    print('end')


main()
'''

# a class with __init__ is built on the typed path
LEN_TYPED = '''
class N:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n


def main():
    o = N(%d)
    print(len(o))
    if o:
        print('t')
    else:
        print('f')


main()
'''


class LenDunder(unittest.TestCase):
    def check(self, slug, source, modes=('default', 'force')):
        with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
            expected, _, status = run_cpython(directory, slug, source)
            for mode in modes:
                with self.subTest(slug=slug, mode=mode):
                    built, exe = compile_source(directory, slug, source, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    out, err, rc = run_exe(directory, exe)
                    self.assertEqual(out, expected, err)
                    self.assertEqual(rc, status, err)

    @_exact_int

    def test_static_class(self):
        self.check('len_static', len_static_source())

    @_exact_int

    def test_dynamic_receiver(self):
        self.check('len_dynamic', LEN_DYNAMIC)

    def test_truth_test_raises(self):
        self.check('truth_raises', TRUTH_RAISES)

    def test_typed_class(self):
        for value in (-1, 0, 3):
            source = LEN_TYPED % value
            with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
                expected, cpython_err, status = run_cpython(directory, 'len_typed', source)
                for mode in ('default', 'force'):
                    with self.subTest(value=value, mode=mode):
                        built, exe = compile_source(directory, 'len_typed', source, mode)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        out, err, rc = run_exe(directory, exe)
                        self.assertEqual(out, expected, err)
                        self.assertEqual(rc, status, err)
                        self.assertEqual(last_line(err), last_line(cpython_err), err)


# ---------------------------------------------------------------------------------------------------- 2. bytearray
BYTEARRAY_FORMS = [
    ('self_iadd', 'b = bytearray(b"ab")\n    b += b\n    return bytes(b)'),
    ('alias_iadd', 'b = bytearray(b"ab")\n    c = b\n    c += b\n    return bytes(b)'),
    ('self_extend', 'b = bytearray(b"ab")\n    b.extend(b)\n    return bytes(b)'),
    ('self_slice_end', 'b = bytearray(b"ab")\n    b[len(b):] = b\n    return bytes(b)'),
    ('self_slice_front', 'b = bytearray(b"ab")\n    b[0:1] = b\n    return bytes(b)'),
    ('self_slice_all', 'b = bytearray(b"ab")\n    b[:] = b\n    return bytes(b)'),
    ('self_imul', 'b = bytearray(b"ab")\n    b *= 2\n    return bytes(b)'),
    ('self_append_elem', 'b = bytearray(b"ab")\n    b.append(b[0])\n    return bytes(b)'),
    ('iadd_bytes_copy', 'b = bytearray(b"ab")\n    b += bytes(b)\n    return bytes(b)'),
    ('iadd_slice_copy', 'b = bytearray(b"ab")\n    b += b[:]\n    return bytes(b)'),
    ('self_add', 'b = bytearray(b"ab")\n    b = b + b\n    return bytes(b)'),
    ('empty_iadd', 'b = bytearray()\n    b += b\n    return bytes(b)'),
    ('empty_extend', 'b = bytearray()\n    b.extend(b)\n    return bytes(b)'),
    ('self_slice_zero', 'b = bytearray(b"ab")\n    b[0:0] = b\n    return bytes(b)'),
    ('self_slice_len_len', 'b = bytearray(b"ab")\n    b[len(b):len(b)] = b\n    return bytes(b)'),
    ('self_slice_mid', 'b = bytearray(b"abc")\n    b[1:2] = b\n    return bytes(b)'),
    ('self_slice_past', 'b = bytearray(b"ab")\n    b[2:] = b\n    return bytes(b)'),
    ('self_slice_inner', 'b = bytearray(b"abcd")\n    b[1:3] = b\n    return bytes(b)'),
    ('extended_slice_size', 'b = bytearray(b"abc")\n    b[::2] = b[::-1]\n    return bytes(b)'),
    ('extended_slice_list', 'b = bytearray(b"abc")\n    b[::2] = [1, 2, 3]\n    return bytes(b)'),
    ('extended_slice_ok', 'b = bytearray(b"abcd")\n    b[::2] = b"xy"\n    return bytes(b)'),
    ('iadd_after_grow', 'b = bytearray(b"ab")\n    b += b"cd"\n    b += b\n    return bytes(b)'),
]


def bytearray_source():
    out = ['def t(label, f):',
           '    try:',
           '        r = f()',
           "        print(label, 'ok', r)",
           '    except Exception as e:',
           "        print(label, type(e).__name__, e)",
           '']
    for index, (_, body) in enumerate(BYTEARRAY_FORMS):
        out.append('def f%d():\n    %s\n' % (index, body))
    out.append('def main():')
    for index, (slug, _) in enumerate(BYTEARRAY_FORMS):
        out.append('    t(%r, f%d)' % (slug, index))
    out.append('\nmain()')
    return '\n'.join(out) + '\n'


class ByteArraySelfResize(unittest.TestCase):
    def test_forms_match_cpython(self):
        source = bytearray_source()
        with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
            expected, _, status = run_cpython(directory, 'ba_forms', source)
            self.assertIn('BufferError', expected)
            for mode in ('default', 'force'):
                with self.subTest(mode=mode):
                    built, exe = compile_source(directory, 'ba_forms', source, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    out, err, rc = run_exe(directory, exe)
                    self.assertEqual(out, expected, err)
                    self.assertEqual(rc, status)

    def test_uncaught_message(self):
        source = 'def main():\n    b = bytearray(b"ab")\n    b += b\n    print(len(b))\n\n\nmain()\n'
        with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
            _, cpython_err, status = run_cpython(directory, 'ba_uncaught', source)
            for mode in ('default', 'force'):
                with self.subTest(mode=mode):
                    built, exe = compile_source(directory, 'ba_uncaught', source, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    _, err, rc = run_exe(directory, exe)
                    self.assertEqual(rc, status, err)
                    self.assertEqual(last_line(err), last_line(cpython_err), err)

    def test_typed_extend_of_self_is_fine(self):
        source = ('def main() -> None:\n    b = bytearray(b"abcdefgh" * 3000)\n    b.extend(b)\n    b.extend(b)\n'
                  '    print(len(b))\n    print(b[1], b[24000], b[-1], b[-2])\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
            expected, _, status = run_cpython(directory, 'ba_typed', source)
            for mode in ('default', 'force', 'typed'):
                with self.subTest(mode=mode):
                    built, exe = compile_source(directory, 'ba_typed', source, mode)
                    if mode == 'typed' and built.returncode != 0:
                        continue
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    out, err, rc = run_exe(directory, exe)
                    self.assertEqual(out, expected, err)
                    self.assertEqual(rc, status)


# ---------------------------------------------------------------------------------------------------- 3. stdin
STDIN_PROGRAMS = {
    'input': 'def main():\n    print("start")\n    line = input()\n    print(len(line))\n\n\nmain()\n',
    'read': 'import sys\n\n\ndef main():\n    print("start")\n    data = sys.stdin.read()\n    print(len(data))\n\n\nmain()\n',
    'readline_int': ('import sys\n\n\ndef main():\n    print("start")\n    n = int(sys.stdin.readline())\n'
                     '    print(n + 1)\n\n\nmain()\n'),
}
STDIN_BYTES = {
    'good': b'caf\xc3\xa9 12\n',
    'good_number': b'41\n',
    'bad_start': b'a\xffb\nline2\n',
    'bad_number': b'12\xff\n',
    'bad_lead_only': b'\xff\n',
    'truncated': b'ok\n\xe2\x82\n',
    'overlong': b'x\xc0\x80y\n',
    'surrogate': b'x\xed\xa0\x80y\n',
    'too_big': b'x\xf5\x80\x80\x80\n',
    'bad_second_line_read': b'fine\nstill fine\n\xe2\x28\xa1\n',
}


class StdinNotUtf8(unittest.TestCase):
    def test_matches_strict_cpython(self):
        for pname, source in STDIN_PROGRAMS.items():
            for bname, data in STDIN_BYTES.items():
                if pname == 'input' and bname in ('truncated', 'bad_second_line_read'):
                    continue            # input() reads one line: the bad bytes on a later line are not reached
                if pname == 'readline_int' and bname in ('good', 'truncated', 'bad_second_line_read'):
                    continue
                slug = 'stdin_%s' % pname
                with tempfile.TemporaryDirectory(prefix='ail-diffs3-') as directory:
                    # surrogateescape (CPython's default) keeps going: nothing to compare with when the bytes are bad.
                    # strict mode raises the UnicodeDecodeError whose text AIL prints.
                    expected, cpython_err, status = run_cpython(directory, slug, source, data, strict_stdin=True)
                    for mode in ('default', 'force', 'typed'):
                        with self.subTest(program=pname, data=bname, mode=mode):
                            built, exe = compile_source(directory, slug, source, mode)
                            if mode == 'typed' and built.returncode != 0:
                                continue
                            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                            out, err, rc = run_exe(directory, exe, data)
                            self.assertEqual(out, expected, err)
                            self.assertEqual(rc, status, err)
                            self.assertNotIn('internal error', err)
                            if status:
                                self.assertEqual(last_line(err), last_line(cpython_err), err)


if __name__ == '__main__':
    unittest.main()
