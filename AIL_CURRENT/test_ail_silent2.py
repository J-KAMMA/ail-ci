"""Silent differences closed by a fix or a refusal, round 2 (DIFFERENCES C119, C114, C115), against CPython 3.12.

1. `list.count`, `index`, `remove`, `in` and the tuple and deque equivalents compare by identity first (`x is y or x == y`), so a
   NaN that is the same object is found; two NaN objects are not (C119). The general path boxes floats and now does this in
   every such operation. The typed path keeps floats unboxed (a NaN has no identity there). A count / index / remove of a float in
   a list of floats, a `count` on a float list field and `x in d.values()` of a dict of floats stay on the typed path: the answer
   is CPython's for every argument that is not NaN (identity cannot change a non-NaN `==`), and a NaN argument stops the program
   by name ("DIFFERENCES C119" and the operation), one `x != x` test per call, outside the element loop. A deque
   of floats built in a function (the typed ring buffer, collib.py) does the same for `count`, `index`, `remove` and `in`: it
   stays on the typed path (no compile-time refusal, no fallback), one `x != x` on the argument, a NaN stops by name. A NaN key of a Counter, dict,
   defaultdict, set or frozenset already finds the same NaN object on both paths (tests only).

2. `is` / `is not` on numbers (C114, C115). CPython shares the ints -5..256, merges equal constants and makes two objects of two
   equal ints computed at run time; an int here is a value. The compiler refuses, naming C114 / C115, an `is` with a number
   literal (or a name only bound to constants, or an item of a list written with number literals) and an `is` where an operand is
   statically an int; `is` against None / True / False / a str, two floats made by arithmetic, and objects are unchanged. For an `is`
   the scan cannot type (two parameters) the general-path runtime stops with a message naming C114 when both ints are equal and
   outside -5..256 (`ail_is`); ints of -5..256 and different values answer as CPython does. An int literal of -5..256 against
   any operand that is not itself a float constant (`x is 0`, `x is not 256`, `n is -5`) is not refused: CPython caches those ints,
   so it answers `==` for an int and False for a bool, a float or anything else; an object compared with an expression built from itself
   (`(x or "o") is not x`, `h[1] is h[1]`) is not refused either (the same object, not two merged constants); the typed lowering and `ail_is` do the same, and
   the `ail_is` stop cannot fire (it needs two equal ints outside the range). Float literals and int literals outside -5..256 are refused.

Programs are built with the general path forced and with the default build; stdout and the exit status must match CPython.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, built


def _build_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False), rc=0):
    """stdout and exit status equal CPython's; an uncaught exception also has the same last stderr line."""
    with tempfile.TemporaryDirectory(prefix='ail-silent2-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:3000], general, err))


def check_refused(test, name, text, words, modes=(True, False)):
    """The program does not build in either mode, and the message contains every word of `words`."""
    with tempfile.TemporaryDirectory(prefix='ail-silent2-') as directory:
        for general in modes:
            _, built = _build(directory, '%s%d' % (name, general), text, general)
            test.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (name, general))
            for word in words:
                test.assertIn(word, built.stdout + built.stderr, '%s (general=%s)' % (name, general))




# ---- 1. identity before equality in a container search (C119) ---------------------------------------------------------

NAN_SAME = {
    'list_methods': ('nan = float("nan")\nxs = [nan, 1.0, nan]\nprint(xs.count(nan), xs.index(nan), nan in xs, xs == [nan, 1.0, nan])\n'
                     'xs.remove(nan)\nprint(len(xs), xs.index(nan, 1), xs.count(1.0))\n'),
    'two_objects': ('a = float("nan")\nb = float("nan")\nxs = [a]\nprint(xs.count(b), b in xs, xs == [b], a in xs, xs.count(a))\n'
                    'try:\n    xs.index(b)\nexcept ValueError as e:\n    print("ValueError")\n'
                    'try:\n    xs.remove(b)\nexcept ValueError as e:\n    print("ValueError")\n'),
    'inf_minus_inf': ('inf = float("inf")\nn = inf - inf\nm = inf - inf\nxs = [n, 0.0, -0.0]\n'
                      'print(xs.count(n), xs.count(m), xs.index(n), xs.count(0.0), xs.count(-0.0), xs.index(-0.0), -0.0 in xs)\n'),
    'tuple': ('nan = float("nan")\nt = (1.0, nan)\nprint(t.count(nan), t.index(nan), nan in t, t == (1.0, nan), t.count(float("nan")))\n'),
    'deque': ('from collections import deque\nnan = float("nan")\nq = deque([2.0, nan])\nprint(q.count(nan), q.index(nan), nan in q)\n'
              'q.remove(nan)\nprint(len(q), q.count(nan))\n'),
    'nested': ('nan = float("nan")\nxs = [[nan], (nan, 1)]\nprint(xs.count([nan]), [nan] in xs, xs.index((nan, 1)), [nan] == [nan])\n'),
    'argument': ('def find(xs, v):\n    return xs.count(v), xs.index(v), v in xs\n\n\nnan = float("nan")\nprint(find([nan], nan))\n'
                 'print(find([float("nan"), nan], nan))\n'),
    'attribute': ('class C:\n    def __init__(self, v):\n        self.v = v\n        self.xs = [v, 2.5]\n'
                  '    def look(self):\n        return self.xs.count(self.v), self.xs.index(self.v), self.v in self.xs\n\n\n'
                  'print(C(float("nan")).look())\nprint(C(float("inf") - float("inf")).look())\n'),
    'dict_value': ('nan = float("nan")\nd = {"k": [nan, 1.0]}\nprint(d["k"].count(nan), d["k"].index(nan), nan in d["k"])\n'
                   'e = {"a": nan}\nprint(nan in e.values(), [e["a"]].count(nan), list(e.values()).index(nan))\n'),
    'from_data': ('s = "na" + "n"\nx = float(s)\ny = float(s)\nxs = [x, 1.0]\nprint(xs.count(x), xs.count(y), x in xs, y in xs)\n'),
    'zeros_and_inf': ('xs = [0.0, -0.0, float("inf"), 1.5]\nprint(xs.count(0.0), xs.count(-0.0), xs.index(-0.0), xs.count(float("inf")), '
                      'xs.index(1.5), -0.0 in xs, float("-inf") in xs)\n'),
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class NanIdentity(unittest.TestCase):
    def test_same_object_is_found_two_objects_are_not(self):
        for name, text in sorted(NAN_SAME.items()):
            check_program(self, 'nan_' + name, text)

    def test_general_path_with_a_float_list(self):
        # the general path (forced) answers like CPython for a NaN argument in a float list, list field and dict values
        text = ('def main():\n    big = 1e308 * 10\n    m = big - big\n    xs = [m, 1.0]\n    print(xs.count(m), xs.index(m), xs.count(1.0))\n'
                '    ys = [1.0, m, 2.0]\n    ys.remove(m)\n    print(len(ys), ys.index(2.0))\n\n\nmain()\n')
        check_program(self, 'nan_typed', text, modes=(True,))
        field = ('class S:\n    def __init__(self):\n        self.xs = [1.5]\n\n\ndef main():\n    s = S()\n    m = 1e308 * 10 - 1e308 * 10\n'
                 '    s.xs.append(m)\n    print(s.xs.count(m), s.xs.count(1.5))\n\n\nmain()\n')
        check_program(self, 'nan_typed_field', field, modes=(True,))
        values = ('def main():\n    m = 1e308 * 10 - 1e308 * 10\n    d: dict[int, float] = {}\n    d[1] = m\n    d[2] = 1.5\n'
                  '    print(m in d.values(), 1.5 in d.values(), 7.5 in d.values())\n\n\nmain()\n')
        check_program(self, 'nan_typed_values', values, modes=(True,))

    def test_typed_float_search_without_a_nan_argument_is_cpython(self):
        # a NaN element and an ordinary argument, -0.0, inf: same answers as CPython on both paths
        text = ('def main():\n    m = 1e308 * 10 - 1e308 * 10\n    xs = [1.5, m, 0.0, 2.5, 1.5, -0.0, 1e308 * 10]\n'
                '    for v in [1.5, 2.5, 0.0, -0.0, 1e308 * 10, 9.0]:\n        print(xs.count(v), v in xs)\n'
                '        if v != 9.0:\n            print(xs.index(v))\n    ys = list(xs)\n    ys.remove(0.0)\n    print(len(ys), ys.count(-0.0), ys.index(2.5, 1, 6))\n'
                '    print(xs.index(max(xs[2:5])))\n'
                '    d: dict[int, float] = {1: m, 2: 1.5}\n    print(1.5 in d.values(), 7.5 in d.values(), 0.0 in d.values())\n\n\nmain()\n')
        check_program(self, 'nonnan_float_search', text)
        field = ('class S:\n    def __init__(self):\n        self.xs = [1.5, 1e308 * 10 - 1e308 * 10, 1.5]\n\n\ndef main():\n'
                 '    s = S()\n    print(s.xs.count(1.5), s.xs.count(7.5))\n\n\nmain()\n')
        check_program(self, 'nonnan_float_field', field)

    def _typed_run(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-silent2-') as directory:
            src = Path(directory) / (name + '.ail')
            src.write_text(text, encoding='utf-8')
            debug = Path(directory) / 'dbg'
            built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '--strict',
                                    '-o', 'exe', '--debug-dir', str(debug)], cwd=directory, capture_output=True, text=True,
                                   timeout=900, env=dict(os.environ, AIL_NO_CACHE='1', AIL_NO_GENERAL='1'))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)     # the typed path, not refused
            got = subprocess.run([str(Path(directory) / 'exe')], capture_output=True, text=True, timeout=120, cwd=directory)
            return got, (debug / 'program.c').read_text(encoding='utf-8')

    def test_typed_nan_argument_stops_by_name(self):
        head = 'def main():\n    m = 1e308 * 10 - 1e308 * 10\n    xs = [1.0, m]\n    print("start")\n'
        cases = {
            'list.index': head + '    print(xs.index(m))\n\n\nmain()\n',
            'list.count': head + '    print(xs.count(m))\n\n\nmain()\n',
            'list.remove': head + '    xs.remove(m)\n    print(len(xs))\n\n\nmain()\n',
            'x in d.values()': head + '    d: dict[int, float] = {1: 1.0}\n    print(m in d.values())\n\n\nmain()\n',
            'field': ('class S:\n    def __init__(self):\n        self.xs = [1.0]\n\n\ndef main():\n    s = S()\n    m = 1e308 * 10 - 1e308 * 10\n'
                      '    print("start")\n    print(s.xs.count(m))\n\n\nmain()\n'),
        }
        for name, text in sorted(cases.items()):
            got, _ = self._typed_run('stop_' + name.replace('.', '_').replace(' ', '_').replace('(', '').replace(')', ''), text)
            self.assertNotEqual(got.returncode, 0, name)
            self.assertEqual(got.stdout, 'start\n', name)
            self.assertIn('C119', got.stderr, name)
            self.assertIn(name if name != 'field' else 'list.count', got.stderr, name)

    def test_typed_check_is_one_test_outside_the_loop(self):
        text = ('def main():\n    xs = [1.5, 2.5, 3.5]\n    v = xs[1]\n    print(xs.index(v), xs.count(v))\n    xs.remove(v)\n'
                '    print(xs)\n\n\nmain()\n')
        got, c_text = self._typed_run('one_check', text)
        self.assertEqual(got.stdout, '1 1\n[1.5, 3.5]\n')
        lines = c_text.splitlines()
        checks = [i for i, line in enumerate(lines) if 'C119' in line]
        self.assertEqual(len(checks), 3)
        for i in checks:
            match = re.search(r'if \((\w+) != \1\) \{ ail_die\(', lines[i])
            self.assertTrue(match, lines[i])
            # straight after the statement that stores the argument, at the same nesting: once per call, before the loop
            self.assertRegex(lines[i - 1], r'^\s*%s = ' % re.escape(match.group(1)))
            self.assertEqual(len(lines[i]) - len(lines[i].lstrip()), len(lines[i - 1]) - len(lines[i - 1].lstrip()))
            self.assertNotIn('C119', lines[i + 1])

    def test_typed_float_lists_without_a_nan_unchanged_for_ints_and_strs(self):
        text = ('def main():\n    xs = [3, 1, 3]\n    ws = ["a", "b", "a"]\n    print(xs.count(3), xs.index(1), ws.count("a"), ws.index("b"))\n'
                '    xs.remove(3)\n    print(xs, sum([1.5, 2.5]), 2 in xs)\n    t = 0.0\n    for v in [0.5, 1.5]:\n        t += v\n    print(t)\n\n\nmain()\n')
        check_program(self, 'ints_strs', text)
        got, c_text = self._typed_run('ints_strs_typed', text)
        self.assertEqual(got.returncode, 0)
        self.assertNotIn('C119', c_text)                    # no NaN test for an int or str list


DEQUE_NAN = {
    # a deque of floats built inside a function is the typed ring buffer: the general path (forced) answers as CPython; the default
    # (typed) build stops by name for a NaN argument (test_typed_float_deque_nan_argument_stops_by_name)
    'local_float_deque': ('from collections import deque\n\n\ndef main():\n    n = float("nan")\n    q = deque([n, 3.0])\n'
                          '    print(q.count(n), q.index(3.0), n in q)\n    print(q.index(n))\n    q.remove(n)\n    print(len(q), q.count(3.0))\n'
                          '    m = float("nan")\n    r = deque([n])\n    print(r.count(m), m in r, n in r)\n    try:\n        r.remove(m)\n'
                          '    except ValueError as e:\n        print("ValueError", e)\n\n\nmain()\n'),
    'issue_example': ('from collections import deque\n\n\ndef main():\n    n = float("nan")\n    q = deque([n, 3.0])\n'
                      '    print(q.count(n), q.index(3.0), n in q)\n\n\nmain()\n'),
}

# the deque reaches the search through an attribute, an argument, a list item or a dict value: both paths
DEQUE_NAN_BOTH = {
    'attribute': ('from collections import deque\n\n\nclass C:\n    def __init__(self, v):\n        self.v = v\n        self.q = deque([v, 2.5])\n'
                  '    def look(self):\n        return self.q.count(self.v), self.q.index(self.v), self.v in self.q\n\n\n'
                  'print(C(float("nan")).look())\nprint(C(float("inf") - float("inf")).look())\n'),
    'argument': ('from collections import deque\n\n\ndef find(q, v):\n    return q.count(v), q.index(v), v in q\n\n\n'
                 'n = float("nan")\nprint(find(deque([n]), n))\nprint(find(deque([float("nan"), n]), n))\n'),
    'list_item': ('from collections import deque\n\n\nn = float("nan")\nqs = [deque([n, 1.0]), deque([2.0])]\n'
                  'print(qs[0].count(n), qs[0].index(n), n in qs[0], n in qs[1])\nqs[0].remove(n)\nprint(len(qs[0]), qs[0].count(float("nan")))\n'),
    'dict_value': ('from collections import deque\n\n\nn = float("nan")\nd = {"k": deque([n])}\nprint(d["k"].count(n), n in d["k"], d["k"].index(n))\n'),
    'two_objects': ('from collections import deque\n\n\na = float("nan")\nb = float("nan")\nq = deque([a])\nprint(q.count(b), b in q, q.count(a))\n'
                    'try:\n    q.index(b)\nexcept ValueError:\n    print("ValueError")\n'),
    'ints_strs_unchanged': ('from collections import deque\n\n\ndef main():\n    q = deque([3, 1, 3])\n    w = deque(["a", "b"])\n'
                            '    print(q.count(3), q.index(1), 3 in q, 9 in q, w.count("a"), w.index("b"), "c" in w)\n    q.remove(3)\n    print(list(q))\n\n\nmain()\n'),
}

# a NaN key: the same NaN object is found, a second float("nan") is a new key (already CPython on both paths)
NAN_KEYS = {
    'counter_dict_set': ('from collections import Counter, defaultdict\n\n\ndef main():\n    n = float("nan")\n    m = float("nan")\n'
                         '    c = Counter([n, n, 1.0])\n    print(c[n], c[m], n in c, m in c, len(c))\n    d = {n: 1}\n    d[n] = 2\n'
                         '    print(d[n], n in d, m in d, d.get(n), d.get(m, "no"), len(d))\n    d[m] = 3\n    print(len(d))\n    del d[n]\n    print(len(d))\n'
                         '    s = {n, 1.0}\n    print(n in s, m in s, len(s))\n    s.add(n)\n    print(len(s))\n    s.discard(n)\n    print(len(s))\n'
                         '    dd = defaultdict(int)\n    dd[n] += 1\n    dd[n] += 1\n    print(dd[n], len(dd))\n    c2 = Counter()\n    c2[n] += 1\n'
                         '    c2[n] += 1\n    c2[m] += 1\n    print(c2[n], len(c2))\n    fs = frozenset([n])\n    print(n in fs, m in fs)\n'
                         '    print(len(set([n, n, m])), len({n: 1, n: 2}))\n\n\nmain()\n'),
    'from_a_list': ('from collections import Counter\n\n\ndef main():\n    n = float("nan")\n    xs = [n, n, 1.0]\n    c = Counter(xs)\n'
                    '    print(c[n], len(c))\n    d = {}\n    for x in xs:\n        d[x] = d.get(x, 0) + 1\n    print(len(d), d[n])\n'
                    '    s = set(xs)\n    print(n in s, len(s))\n    print(c.most_common(1))\n\n\nmain()\n'),
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class DequeNan(unittest.TestCase):
    _typed_run = NanIdentity._typed_run

    def test_float_deque_is_cpython(self):
        for name, text in sorted(DEQUE_NAN.items()):
            check_program(self, 'dq_' + name, text, modes=(True,))

    def test_deque_reached_by_attribute_argument_item_value(self):
        for name, text in sorted(DEQUE_NAN_BOTH.items()):
            check_program(self, 'dq_' + name, text)

    def test_typed_float_deque_nan_argument_stops_by_name(self):
        head = ('from collections import deque\n\n\ndef main():\n    n = float("nan")\n    q = deque([n, 3.0])\n    print("start")\n')
        cases = {
            'deque.count': head + '    print(q.count(n))\n\n\nmain()\n',
            'deque.index': head + '    print(q.index(n))\n\n\nmain()\n',
            'deque.remove': head + '    q.remove(n)\n    print(len(q))\n\n\nmain()\n',
            'x in deque': head + '    print(n in q)\n\n\nmain()\n',
        }
        for name, text in sorted(cases.items()):
            # not refused at compile time (strict, typed only), and not built on the general path: the run stops by name
            got, c_text = self._typed_run('dqstop_' + name.replace('.', '_').replace(' ', '_'), text)
            self.assertNotEqual(got.returncode, 0, name)
            self.assertEqual(got.stdout, 'start\n', name)
            self.assertIn('C119', got.stderr, name)
            self.assertIn(name, got.stderr, name)
            self.assertIn('_AilDeque_float', c_text, name)
        check_program(self, 'dq_refused_general', head.replace('    print("start")\n', '') + '    print(q.count(n), q.index(3.0), n in q)\n    q.remove(n)\n    print(len(q))\n\n\nmain()\n', modes=(True,))

    def test_typed_float_deque_check_is_one_test_per_call_outside_the_loop(self):
        text = ('from collections import deque\n\n\ndef main():\n    q = deque([1.5, 2.5, 1.5])\n    v = 1.5\n'
                '    print(q.count(v), q.index(v), v in q)\n    q.remove(v)\n    print(len(q))\n\n\nmain()\n')
        got, c_text = self._typed_run('dq_one_check', text)
        self.assertEqual(got.stdout, '2 0 True\n2\n')
        lines = c_text.splitlines()
        checks = [i for i, line in enumerate(lines) if 'C119' in line]
        self.assertEqual(len(checks), 4)
        for i in checks:
            self.assertRegex(lines[i - 1] + lines[i], r'!=')
            for j in range(i + 1, min(i + 4, len(lines))):
                self.assertNotIn('C119', lines[j])

    def test_typed_float_deque_without_a_nan_argument_is_cpython(self):
        text = ('from collections import deque\n\n\ndef main():\n    m = 1e308 * 10 - 1e308 * 10\n    q = deque([1.5, m, 0.0, 2.5, 1.5, -0.0])\n'
                '    for v in [1.5, 2.5, 0.0, -0.0, 9.0]:\n        print(q.count(v), v in q)\n        if v != 9.0:\n            print(q.index(v))\n'
                '    q.remove(2.5)\n    print(len(q), q.count(1.5), 1e308 * 10 in q)\n\n\nmain()\n')
        check_program(self, 'dq_nonnan', text)

    def test_nan_keys_of_counter_dict_set(self):
        for name, text in sorted(NAN_KEYS.items()):
            check_program(self, 'key_' + name, text)


# ---- 2. `is` on numbers (C114, C115) ---------------------------------------------------------------------------------

IS_REFUSED = {
    'c115_float_literal': ('t = 2.5\nprint(t is 2.5)\n', 'C115'),
    'c115_name_literals': ('def f():\n    a = 2.0\n    b = 2.0\n    return a is b\n\n\nprint(f())\n', 'C115'),
    'c115_list_items': ('xs = [1.5, 2.5, 1.5]\nprint(xs[0] is xs[2])\n', 'C115'),
    'c115_negative': ('def f(a):\n    return a is not -6\n\n\nprint(f(-6))\n', 'C115'),
    'c115_int_literal': ('def f(a):\n    return a is 257\n\n\nprint(f(257))\n', 'C115'),
    'c115_float_literal_operand': ('def f(a):\n    return a is 1.5\n\n\nprint(f(1.5))\n', 'C115'),
    'c115_float_literal_and_int': ('def f(a):\n    return a is 0.0, 0 is 0.0\n\n\nprint(f(0.0))\n', 'C115'),
    'c115_two_literals_outside': ('print(300 is 300)\n', 'C115'),
    'c114_computed': ('def f(n):\n    a = n + 1000\n    b = n + 1000\n    return a is b\n\n\nprint(f(1))\n', 'C114'),
    'c114_len': ('def f(x, y):\n    return len(x) is len(y)\n\n\nprint(f([1] * 300, [2] * 300))\n', 'C114'),
    'c114_annotated': ('def f(a: int, b: int):\n    return a is not b\n\n\nprint(f(2**62, 2**62))\n', 'C114'),
    'c114_loop': ('def f(n):\n    c = 0\n    for i in range(n):\n        c += i\n    return c is n\n\n\nprint(f(3))\n', 'C114'),
    'c114_module': ('k = 300\n\n\ndef f(a):\n    return a is k\n\n\nprint(f(300))\n', 'C115'),
    'c114_int_call': ('def f(s, t):\n    return int(s) is int(t)\n\n\nprint(f("300", "300"))\n', 'C114'),
}

# an int literal of -5..256 against an int, a bool, a float or something unknown: CPython caches those ints, so `is` is `==` for an
# int and False for anything else (default build, general path and CPython agree)
IS_CACHED = {
    'unknown_argument': 'def f(x):\n    return x is 0, x is not 256, x is 5, x is not 0\n\n\nfor v in [0, 256, 5, 1, False, True, 0.0, 5.0, "a", None, 300]:\n    print(f(v))\n',
    'bool_and_constants': 'print(True is 1, 0 is False, 1 is True, False is 0)\n',
    'negative_bound': 'def g(n):\n    return n is -5, n is not -5, -5 is n\n\n\nprint(g(-5), g(-4), g(-6), g(-5.0), g(False))\n',
    'int_typed': 'def f(x: int):\n    return x is 0, x is not 256, x is +3\n\n\nprint(f(0), f(256), f(3), f(257), f(-1))\n',
    'typed_bool_and_float': ('def f(b: bool, n: float):\n    print(b is 1, 0 is b, n is 3, n is not 0, b is not 0)\n\n\nf(True, 3.0)\nf(False, 0.0)\n'),
    'list_items': 'xs = [0, True, 0.0, 256, "a", None, 300, -5]\nfor v in xs:\n    print(v is 0, v is not 256, v is -5)\nprint(xs[0] is 0, xs[3] is not 256, xs[1] is 1)\n',
    'computed': 'def f(n):\n    a = n - 1\n    b = n * 1.0\n    return a is 0, a is not 255, b is 5, len([1] * n) is 3\n\n\nprint(f(1), f(256), f(5), f(3))\n',
    'through_a_call': 'def same(a, b):\n    return a is b\n\n\ndef f(x):\n    return same(x, 0), same(x, 256), x is 0\n\n\nprint(f(0), f(256), f(False), f(1.0))\n',
    'in_a_loop': 'n = 0\nfor i in range(300):\n    if i is 100 or i is not 255 and i is 256:\n        n += i\nprint(n)\n',
    'same_object_derived': ('def f():\n    x = 0.0\n    y = 2.5\n    z = -3\n    return ((x or "o") is not x, (y or "o") is not y, (y and "a") is not y, '
                            '(z or "o") is not z, x is x, y is y)\n\n\nprint(f())\nh = [0, 0.0, 2.5]\nprint((h[2] or "o") is not h[2], (h[1] or "o") is not h[1], h[0] is h[0])\n'),
    'chained_and_not': 'def f(x):\n    return 0 is x is 0, not x is 3, x is 3 is x\n\n\nprint(f(0), f(3), f(0.0))\n',
}

# `is True` / `is False` / `is None` on ints, floats, bools and unknown values (C115-silent2-1): an int is never the bool singleton
IS_SINGLETON = {
    'literals': 'print(1 is True, 0 is False, 1 is not True, 0 is not False, True is 1, False is 0)\n',
    'module_int_and_bool': 'x = 1\nprint(x is True, x is False, x is not True, x is not False)\nb = 1 > 0\nprint(b is True, b is False, b is not True)\nprint(int(True) is True, (x == 1) is True, (x == 2) is False, (x == 1) is not True)\n',
    'typed_parameter': 'def f(x: int, y: float, b: bool):\n    return x is True, x is not False, y is False, y is not True, b is True, b is False, x is None, y is not None, b is None\n\n\nprint(f(1, 1.0, True), f(0, 0.0, False), f(5, 2.5, True))\n',
    'unknown_parameter': 'def f(x):\n    return x is True, x is False, x is not True, x is not False, x is None, x is not None\n\n\nfor v in [1, 0, True, False, 1.0, 0.0, "a", None, [1]]:\n    print(f(v))\n',
    'list_and_attribute': 'class A:\n    def __init__(self, v):\n        self.v = v\n\n\nxs = [1, 0, True, False, None]\nprint([v is True for v in xs], [v is False for v in xs], [v is not None for v in xs])\na = A(1)\nprint(xs[0] is True, xs[3] is False, a.v is True, a.v is not False, A(True).v is True)\n',
}

# an `is` the scan does not refuse and that answers as CPython does
IS_ALLOWED = {
    'floats_by_arithmetic': ('def f(x: float):\n    c = x / 2\n    d = x / 2\n    return c is d, c is c\n\n\nprint(f(3.0), f(0.0))\n'),
    'none_true_false': ('def f(a):\n    return a is None, a is not None, a is True, a is False, a is not True\n\n\n'
                        'print(f(None), f(1), f(True), f(0), f(False))\n'),
    'objects': ('class N:\n    def __init__(self, v):\n        self.v = v\n\n\na = N(1)\nb = N(1)\nc = a\n'
                'print(a is b, a is c, a is not b, [a][0] is a, {"k": a}["k"] is c)\n'),
    'same_nan_and_inf': ('def same(a, b):\n    return a is b\n\n\nnan = float("nan")\ninf = float("inf")\nn2 = inf - inf\n'
                         'print(same(nan, nan), same(nan, float("nan")), same(inf, inf), same(n2, n2), same(n2, inf - inf), same(inf, -inf))\n'),
    'small_ints_pass_through': ('class H:\n    def __init__(self, v):\n        self.v = v\n\n\ndef same(a, b):\n    return a is b\n\n\n'
                                'xs = [-5, 256, 0]\nt = (-5, 256)\nd = {"a": 256, "b": -5}\nh = H(256)\n'
                                'print(same(-5, -5), same(256, 256), same(xs[0], t[0]), same(xs[1], d["a"]), same(h.v, xs[1]), same(d["b"], xs[0]))\n'),
    'different_ints_and_types': ('def same(a, b):\n    return a is b\n\n\nxs = [257, 258, 2**62]\n'
                                 'print(same(xs[0], xs[1]), same(xs[2], xs[0]), same(257, 1.5), same(1, True), same("a", 1), same(None, 0))\n'),
    'zeros': ('def same(a, b):\n    return a is b\n\n\nz = -0.0\nprint(same(z, z), same(z, 0.0 * 1.0), same(0, False))\n'),
    'unknown_operands': ('def same(a, b):\n    return a is b, a is not b\n\n\nxs = [1, 2]\nys = xs\nprint(same(xs, ys), same(xs, [1, 2]), same((1,), (2,)))\n'),
}

# both ints equal and outside -5..256 with no static type: the runtime stops, naming C114 (CPython's answer depends on provenance)
IS_RUNTIME = {
    'argument': 'def same(a, b):\n    return a is b\n\n\nprint(same(5, 5))\nprint(same(2**62, 2**62))\n',
    'list': 'def same(a, b):\n    return a is b\n\n\nxs = [257, 257]\nprint(same(1, 1))\nprint(same(xs[0], xs[1]))\n',
    'tuple': 'def same(a, b):\n    return a is not b\n\n\nt = (-6, -6)\nprint(same(0, 1))\nprint(same(t[0], t[1]))\n',
    'dict_value': 'def same(a, b):\n    return a is b\n\n\nd = {"a": 1000, "b": 1000}\nprint(same(d["a"], d["a"] - 1))\nprint(same(d["a"], d["b"]))\n',
    'attribute': ('class H:\n    def __init__(self, v):\n        self.v = v\n\n\ndef same(a, b):\n    return a is b\n\n\n'
                  'h = H(300)\ng = H(300)\nprint(same(h, g))\nprint(same(h.v, g.v))\n'),
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class NumberIs(unittest.TestCase):
    def test_refused_by_name(self):
        for name, (text, word) in sorted(IS_REFUSED.items()):
            check_refused(self, 'is_' + name, text, [word, 'is'])

    def test_singleton_identity_is_cpython(self):
        for name, text in sorted(IS_SINGLETON.items()):
            check_program(self, 'issingle_' + name, text)
        check_program(self, 'issingle_typed_all', 'class A:\n    def __init__(self, v: int):\n        self.v = v\n\n\ndef p(v: int) -> int:\n    return v\n\n\ndef q(x: int, y: float, b: bool) -> int:\n    n = 0\n    if x is True: n += 1\n    if x is False: n += 2\n    if x is not True: n += 4\n    if x is not False: n += 8\n    if y is True: n += 16\n    if y is not False: n += 32\n    if b is True: n += 64\n    if b is False: n += 128\n    if b is not True: n += 256\n    if True is b: n += 512\n    if x is None: n += 1024\n    if y is not None: n += 2048\n    if b is None: n += 4096\n    return n\n\n\ndef main():\n    x = 1\n    b = x > 0\n    f = 1.5\n    xs = [1, 0]\n    a = A(1)\n    print(x is True, x is False, x is not True, 1 is True, 0 is False)\n    print(b is True, b is False, b is not True, b is not False)\n    print(int(True) is True, int(b) is not False)\n    print(p(1) is True, p(0) is False, xs[0] is True, xs[1] is False, a.v is True, a.v is not False)\n    print((x == 1) is True, (x == 2) is False, (x == 1) is not True)\n    print(f is True, f is not False, x is None, f is None, b is None, p(2) is not None, a.v is None)\n    print(q(1, 1.0, True), q(0, 0.0, False), q(2, 2.5, True))\n    c = 0\n    while c < 3:\n        c += 1\n        if c is not True:\n            print(c)\n\n\nmain()\n')

    def test_singleton_identity_typed_path_builds(self):
        text = 'class A:\n    def __init__(self, v: int):\n        self.v = v\n\n\ndef p(v: int) -> int:\n    return v\n\n\ndef q(x: int, y: float, b: bool) -> int:\n    n = 0\n    if x is True: n += 1\n    if x is False: n += 2\n    if x is not True: n += 4\n    if x is not False: n += 8\n    if y is True: n += 16\n    if y is not False: n += 32\n    if b is True: n += 64\n    if b is False: n += 128\n    if b is not True: n += 256\n    if True is b: n += 512\n    if x is None: n += 1024\n    if y is not None: n += 2048\n    if b is None: n += 4096\n    return n\n\n\ndef main():\n    x = 1\n    b = x > 0\n    f = 1.5\n    xs = [1, 0]\n    a = A(1)\n    print(x is True, x is False, x is not True, 1 is True, 0 is False)\n    print(b is True, b is False, b is not True, b is not False)\n    print(int(True) is True, int(b) is not False)\n    print(p(1) is True, p(0) is False, xs[0] is True, xs[1] is False, a.v is True, a.v is not False)\n    print((x == 1) is True, (x == 2) is False, (x == 1) is not True)\n    print(f is True, f is not False, x is None, f is None, b is None, p(2) is not None, a.v is None)\n    print(q(1, 1.0, True), q(0, 0.0, False), q(2, 2.5, True))\n    c = 0\n    while c < 3:\n        c += 1\n        if c is not True:\n            print(c)\n\n\nmain()\n'
        with tempfile.TemporaryDirectory(prefix='ail-silent2-') as directory:
            want = _cpython(directory, 'issingle_strict', text)
            src = Path(directory) / 'issingle_strict.ail'
            src.write_text(text, encoding='utf-8')
            built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '--strict', '-o', 'exe'],
                                   cwd=directory, capture_output=True, text=True, timeout=900,
                                   env=dict(os.environ, AIL_NO_CACHE='1', AIL_NO_GENERAL='1'))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)     # the typed path, not refused
            got = subprocess.run([str(Path(directory) / 'exe')], capture_output=True, timeout=120, cwd=directory)
            self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0])

    def test_unrefused_forms_equal_cpython(self):
        for name, text in sorted(IS_ALLOWED.items()):
            check_program(self, 'isok_' + name, text)

    def test_cached_int_literal_is_cpython(self):
        for name, text in sorted(IS_CACHED.items()):
            check_program(self, 'iscache_' + name, text)

    def test_unknown_equal_big_ints_stop_by_name(self):
        for name, text in sorted(IS_RUNTIME.items()):
            with tempfile.TemporaryDirectory(prefix='ail-silent2-') as directory:
                want = _cpython(directory, 'isrt_' + name, text)
                self.assertEqual(want[1], 0)
                first = want[0].split(b'\n')[0] + b'\n'
                for general in (True, False):
                    got, err = _build_run(directory, 'isrt_' + name, text, general)
                    self.assertIsNotNone(got, err)
                    self.assertEqual(got[0], first, '%s general=%s' % (name, general))
                    self.assertNotEqual(got[1], 0, '%s general=%s' % (name, general))
                    self.assertIn('C114', got[2], '%s general=%s' % (name, general))


if __name__ == '__main__':
    unittest.main()
