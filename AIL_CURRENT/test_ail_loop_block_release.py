"""Loop-body list locals are freed in nested blocks; field-loop snapshots are freed after the loop.

The positive cases grep the generated C for a free on the line after the value's last use (inside
an elif body, an inner loop body, and after a field-loop closing brace).  Every program is also
run, in the default build and with AIL_UNIFIED_FORCE=1, against the same source under CPython.
The escape cases would read freed memory if the analysis were less careful: a use after the block,
a use in the next iteration, a lambda capture, an attribute store, a returned value, break and
continue.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import test_ail_c_objects as support

ROOT = support.ROOT
MODES = {'default': {}, 'forced': {'AIL_UNIFIED_FORCE': '1'}}
CLEAR = ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_EXACT',
         'AIL_QUIET_FALLBACK')


POSITIVE = r'''def isum(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s

def fsum(xs: list[float]) -> float:
    s = 0.0
    for x in xs:
        s += x
    return s

def join(xs: list[str]) -> str:
    out = ""
    for x in xs:
        out += x
    return out

def main() -> int:
    int_total = 0
    float_total = 0.0
    words = ""
    for q in range(6):
        if q == 0:
            al = [1, 2, 3]
            int_total += isum(al)
        elif q == 1:
            bl = [1.5, 2.5]
            float_total += fsum(bl)
        elif q == 2:
            cl = ["a", "b", "c"]
            words += join(cl)
        elif q == 3:
            for r in range(2):
                dl = [q, r]
                int_total += isum(dl)
        elif q == 4:
            el = [4, 5]
            int_total += isum(el)
        else:
            fl = [3.0]
            float_total += fsum(fl)
    print(int_total, float_total, words)
    return 0

main()
'''


FIELDS = r'''class Node:
    def __init__(self):
        self.i: list[int] = [1, 2, 3]
        self.f: list[float] = [1.5, 2.5]
        self.s: list[str] = ["a", "b"]

def main() -> int:
    n = Node()
    a = 0
    for x in n.i:
        a += x
    b = 0.0
    for y in n.f:
        b += y
    t = ""
    for z in n.s:
        t += z
    print(a, b, t)
    return 0

main()
'''


ESCAPES = r'''def isum(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s

class Box:
    def __init__(self):
        self.f: list[int] = []

def read_after() -> int:
    total = 0
    xs = []
    for q in range(3):
        if q == 0:
            xs = [1, 2, 3]
        else:
            xs = [4, 5]
        total += isum(xs)
    return total

def next_iteration() -> int:
    total = 0
    cc = [0]
    for q in range(3):
        if q > 0:
            total += isum(cc)
        if q == 0:
            cc = [4, 5]
    return total

def captured() -> int:
    total = 0
    for q in range(2):
        if q == 1:
            ys = [6, 7]
            f = lambda: isum(ys)
            total += f()
    return total

def stored_field() -> int:
    b = Box()
    for q in range(2):
        if q == 0:
            zs = [8, 9]
            b.f = zs
    return isum(b.f)

def appended() -> int:
    total = 0
    outer = []
    for q in range(2):
        if q == 0:
            us = [10, 11]
            outer.append(us)
        if q == 1:
            total += isum(outer[0])
    return total

def returned() -> int:
    for q in range(2):
        if q == 1:
            ws = [q, q + 10]
            return isum(ws)
    return 0

def jumped() -> int:
    total = 0
    for q in range(4):
        if q == 1:
            vs = [q, q + 1]
            total += isum(vs)
            break
        if q == 2:
            ts = [2, 3]
            total += isum(ts)
            continue
        total += q
    return total

def main() -> int:
    print(read_after(), next_iteration(), captured(), stored_field(), appended(), returned(), jumped())
    return 0

main()
'''


CASES = {'positive': POSITIVE, 'fields': FIELDS, 'escapes': ESCAPES}


def compile_case(root, name, source, mode, extra):
    work = root / name / mode
    work.mkdir(parents=True)
    src = work / 'prog.py'
    src.write_text(source, encoding='utf8')
    exe = work / 'prog'
    env = dict(os.environ)
    for key in CLEAR:
        env.pop(key, None)
    env.update(extra)
    env['AIL_NO_CACHE'] = '1'
    env['PYTHONUTF8'] = '1'
    done = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '--debug-dir', 'debug', '-o', exe.name],
                          cwd=work, env=env, capture_output=True, text=True, timeout=900)
    if done.returncode:
        raise AssertionError('%s/%s build failed: %s' % (name, mode, (done.stdout + done.stderr)[-1500:]))
    generated = (work / 'debug' / 'program.c').read_text(encoding='utf8')
    return exe, generated


def run(exe):
    done = subprocess.run([str(exe)], capture_output=True, timeout=120)
    return done.returncode, done.stdout, done.stderr


class LoopBlockReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ail-loop-release-')
        cls.root = Path(cls.tmp.name)
        jobs = [(name, mode) for name in CASES for mode in MODES]
        build = lambda job: (job, compile_case(cls.root, job[0], CASES[job[0]], job[1], MODES[job[1]]))
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.built = dict(pool.map(build, jobs))
        cls.ref = {}
        for name, source in CASES.items():
            path = cls.root / (name + '.py')
            path.write_text(source, encoding='utf8')
            done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120)
            cls.ref[name] = (done.returncode, done.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assert_matches_cpython(self, name):
        for mode in MODES:
            exe, _ = self.built[(name, mode)]
            code, out, err = run(exe)
            self.assertEqual((code, out), self.ref[name], '%s/%s: %s' % (name, mode, err.decode(errors='replace')))

    def test_list_locals_in_elif_and_inner_loop_are_freed(self):
        _, generated = self.built[('positive', 'default')]
        for call, kind, name in (('isum', 'list', 'al'), ('fsum', 'flist', 'bl'), ('join', 'slist', 'cl'),
                                 ('isum', 'list', 'dl'), ('isum', 'list', 'el'), ('fsum', 'flist', 'fl')):
            args = r'v_%s(?:\.p, v_%s\.n)?' % (name, name)
            pattern = r'%s\(%s\)[^\n]*\n\s*ail_%s_free\(&v_%s\);' % (call, args, kind, name)
            self.assertRegex(generated, pattern, '%s should be freed right after its last use' % name)
        self.assert_matches_cpython('positive')

    def test_field_loop_snapshots_are_freed_after_the_loop(self):
        _, generated = self.built[('fields', 'default')]
        for kind in ('list', 'flist', 'slist'):
            found = False
            for loop in re.finditer(r'for \([^;]+; [^;]+< (v__t\d+)\.n; [^)]*\) \{.*?\n\s*\}', generated, re.S):
                temp = loop.group(1)
                tail = generated[loop.end():]
                if re.match(r'\n(?:\s*ail_\w+_free\(&v__t\d+\);\n)*\s*ail_%s_free\(&%s\);' % (kind, temp), tail):
                    found = True
                    break
            self.assertTrue(found, 'the %s loop temp should be freed after the closing brace' % kind)
        self.assert_matches_cpython('fields')

    def test_escapes_and_control_flow_match_cpython(self):
        _, generated = self.built[('escapes', 'default')]
        self.assertNotRegex(generated, r'isum\(v_xs\.p, v_xs\.n\)[^\n]*\n\s*ail_list_free\(&v_xs\);\n\s*\}',
                            'a use after the block must keep xs alive')
        self.assertNotRegex(generated, r'ail_obj_field_list_move\([^\n]*&v_zs\);\s*\n\s*ail_list_free\(&v_zs\);',
                            'an attribute store must keep zs alive')
        self.assertNotRegex(generated, r'append[^\n]*v_us[^\n]*\n\s*ail_list_free\(&v_us\);\n\s*\}',
                            'appending to another container must keep us alive')
        self.assert_matches_cpython('escapes')


if __name__ == '__main__':
    unittest.main()
