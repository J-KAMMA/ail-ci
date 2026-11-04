"""Read-only list-field aliases lower to in-place reads, and every unsafe shape keeps its copy.

A `let x = o.f` for a `list[int]`/`list[float]`/`list[str]` field is a private copy.  The AST pass
elides only read-only aliases that feed sort-key columns; the cases below pin both the elided C and
each reason the copy must survive.  The Python-syntax read-only shapes are compared with CPython,
and the mutation shapes are compared with today's explicit `.copy()` reference build.  A lambda
whose parameters shadow the struct name (or the alias name) must keep the copy.  The forced general
path is smoke-built separately.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support

MIXED = r'''struct T { nm: list[str]; par: list[int]; }
struct U { par: list[int]; idx: int; }

fn positive(t: T) -> int {
    let n = len(t.nm);
    let nm = t.nm;
    let par = t.par;
    let idx = [i for i in range(1, n)];
    idx.sort(key=lambda i: (par[i], nm[i], i));
    let total = 0;
    for i in idx { total += par[i] + len(nm[i]); }
    return total;
}
fn n_append(t: T) -> int { let nm = t.nm; nm.append("z"); return len(nm); }
fn n_elem(t: T) -> int { let par = t.par; par[0] = 5; return par[0] + len(t.par); }
fn n_other(t: T) -> int { let nm = t.nm; let u = T(["q"], [9]); u.nm = ["r"]; return len(nm) + len(u.nm); }
fn touch(x: T) -> int { return len(x.nm); }
fn n_usert(t: T) -> int { let nm = t.nm; return len(nm) + touch(t); }
fn n_xsort(t: T) -> int { let nm = t.nm; nm.sort(); return len(nm); }
fn n_xappend(t: T) -> int { let nm = t.nm; nm.append("z"); return len(nm); }
fn g(xs: list[int]) -> list[int] { return xs; }
fn n_return(t: T) -> int { let par = t.par; let q = g(par); return len(q); }
fn n_alias(t: T) -> int { let nm = t.nm; let y = nm; return len(y); }
fn count(xs: list[str]) -> int { return len(xs); }
fn n_pass(t: T) -> int { let nm = t.nm; return count(nm); }
fn n_rebind(t0: T) -> int { let t = t0; let nm = t.nm; t = T(["q"], [1]); return len(nm) + len(t.nm); }
fn n_after(t: T) -> int { let nm = t.nm; let a = len(nm); t.nm.append("z"); let b = len(nm); return a + b; }
fn n_fieldpop(t: T) -> int { let par = t.par; let a = len(par); t.par.pop(); let b = len(par); return a * 10 + b; }
fn n_minlambda(t: T) -> int {
    let nm = t.nm;
    let par = t.par;
    let n = len(nm);
    return min(range(n), key=lambda i: (par[i], nm[i]));
}
fn shadow_o(o: U, xs: list[U]) -> list[int] {
    let p = o.par;
    let ys = sorted(xs, key=lambda o: p[o.idx]);
    let out: list[int] = [];
    for y in ys { out.append(y.idx); }
    return out;
}
fn shadow_x(t: T) -> int {
    let par = t.par;
    let xs = [3, 1, 2];
    let ys = sorted(xs, key=lambda par: par);
    return ys[0] + par[0];
}
fn comp_shadow(o: U, xs: list[U]) -> int {
    let p = o.par;
    let total = 0;
    for q in [p[o.idx] for o in xs] { total += q; }
    return total;
}
fn main() -> int {
    let t = T(["b","a","c"], [3,1,2]);
    print(positive(t));
    print(n_append(t));
    print(n_elem(t));
    print(n_other(t));
    print(n_usert(t));
    print(n_xsort(t));
    print(n_xappend(t));
    print(n_return(t));
    print(n_alias(t));
    print(n_pass(t));
    print(n_rebind(t));
    print(n_minlambda(t));
    print(n_after(t));
    print(n_fieldpop(t));
    let u = U([10,20,30], 9);
    let us = [U([100,0,0], 2), U([0,200,0], 0), U([0,0,300], 1)];
    for v in shadow_o(u, us) { print(v); }
    print(shadow_x(t));
    print(comp_shadow(u, us));
    return 0;
}
'''

REFERENCE = (MIXED.replace('let nm = t.nm;', 'let nm = t.nm.copy();')
                  .replace('let par = t.par;', 'let par = t.par.copy();')
                  .replace('let p = o.par;', 'let p = o.par.copy();'))

EXPECTED = '5\n4\n8\n4\n6\n3\n4\n3\n3\n3\n4\n1\n6\n33\n0\n1\n2\n4\n60\n'

READONLY = '''class T:
    nm: list[str]
    par: list[int]
    def __init__(self, nm: list[str], par: list[int]) -> None:
        self.nm = nm
        self.par = par

class U:
    par: list[int]
    idx: int
    def __init__(self, par: list[int], idx: int) -> None:
        self.par = par
        self.idx = idx

def positive(t: T) -> int:
    n = len(t.nm)
    nm = t.nm
    par = t.par
    idx = [i for i in range(1, n)]
    idx.sort(key=lambda i: (par[i], nm[i], i))
    total = 0
    for i in idx: total += par[i] + len(nm[i])
    return total

def shadow_o(o: U, xs: list[U]) -> list[int]:
    p = o.par
    ys = sorted(xs, key=lambda o: p[o.idx])
    out: list[int] = []
    for y in ys:
        out.append(y.idx)
    return out

def shadow_x(t: T) -> int:
    par = t.par
    xs = [3, 1, 2]
    ys = sorted(xs, key=lambda par: par)
    return ys[0] + par[0]

def comp_shadow(o: U, xs: list[U]) -> int:
    p = o.par
    total = 0
    for q in [p[o.idx] for o in xs]:
        total += q
    return total

def main() -> int:
    t = T(["b", "a", "c"], [3, 1, 2])
    print(positive(t))
    u = U([10, 20, 30], 9)
    us = [U([100, 0, 0], 2), U([0, 200, 0], 0), U([0, 0, 300], 1)]
    for v in shadow_o(u, us):
        print(v)
    print(shadow_x(t))
    print(comp_shadow(u, us))
    return 0

main()
'''

GLOBAL_READONLY = '''class T:
    nm: list[str]
    par: list[int]
    def __init__(self, nm: list[str], par: list[int]) -> None:
        self.nm = nm
        self.par = par

g: list[int] = [1]
t_global: T = T(["a"], [1, 2])

def f_global(t: T) -> int:
    global g
    g = t.par
    return len(g)

def f_owner() -> int:
    global t_global
    par = t_global.par
    return len(par)

def outer(t: T) -> int:
    h: list[int] = [9]
    def inner() -> int:
        nonlocal h
        h = t.par
        return len(h)
    n = inner()
    return n * 10 + len(h)

def main() -> int:
    print(f_global(T(["a"], [1, 2])))
    print(len(g))
    print(f_owner())
    print(outer(T(["a"], [1, 2])))
    return 0

main()
'''

FORCE_SMOKE = '''def f() -> int:
    xs = [1, 2]
    ys = xs
    ys.append(5)
    return len(xs) * 10 + len(ys)

def main() -> int:
    print(f())
    return 0

main()
'''

SNAPSHOT_NEGATIVES = ('n_append', 'n_other', 'n_usert', 'n_xsort', 'n_xappend',
                      'n_alias', 'n_pass', 'n_rebind', 'n_after', 'n_minlambda')
PAR_NEGATIVES = ('n_elem', 'n_return', 'n_minlambda', 'n_fieldpop', 'shadow_x')
SHADOW_NEGATIVES = ('shadow_o',)


def function_body(csource, name):
    match = re.search(r'\n(?:\w+) ' + re.escape(name) + r'\([^;]*?\) \{(.*?)\n\}',
                      csource, re.S)
    if match is None:
        raise AssertionError('no C body for ' + name)
    return match.group(1)


def cpython_output(source):
    return subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', source],
                          capture_output=True, timeout=60)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class ReadonlyFieldAliasNativeTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def compile_with(self, name, source, env_extra=None, syntax=None):
        path = self.write(name + '.py', source)
        output = self.root / name
        env = dict(os.environ, PYTHONUTF8='1', **(env_extra or {}))
        args = [sys.executable, '-X', 'utf8', '-B',
                str(support.ROOT / 'ail_chatgpt.py'), 'compile', str(path)]
        if syntax is not None:
            args.extend(('--syntax', syntax))
        args.extend(('-o', str(output)))
        result = subprocess.run(args, capture_output=True, timeout=180, env=env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        path.unlink()
        return output

    def compile_debug(self, name, source):
        path = self.write(name + '.ail', source)
        output = self.root / name
        debug = self.root / (name + '-debug')
        result = self.command('compile', path, '-o', output, '--debug-dir', debug)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        path.unlink()
        return output, (debug / 'program.c').read_text(encoding='utf8')

    def test_elided_alias_matches_reference_and_keeps_unsafe_copies(self):
        executable, csource = self.compile_debug('readonly_alias', MIXED)
        reference = self.ail_build('readonly_alias_ref', REFERENCE)
        self.check_run(executable, EXPECTED)
        self.check_run(reference, EXPECTED)

        positive = function_body(csource, 'positive')
        self.assertIn('f_nm', positive)
        self.assertIn('f_par', positive)
        self.assertNotIn('ail_slist_snapshot(&v__sarena', positive)
        self.assertNotIn('v_nm', positive)
        self.assertNotIn('v_par', positive)

        for name in SNAPSHOT_NEGATIVES:
            with self.subTest(case=name):
                self.assertIn('ail_slist_snapshot(&v__sarena', function_body(csource, name))
        for name in PAR_NEGATIVES:
            with self.subTest(case=name):
                self.assertIn('v_par', function_body(csource, name))
        for name in SHADOW_NEGATIVES:
            with self.subTest(case=name):
                self.assertIn('v_p', function_body(csource, name))

    def test_readonly_shapes_match_cpython(self):
        expected = cpython_output(READONLY)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode(errors='replace'))
        for name, extra in (('readonly_cpython', None),
                            ('readonly_cpython_forced', {'AIL_UNIFIED_FORCE': '1'})):
            with self.subTest(build=name):
                built = self.compile_with(name, READONLY, extra, syntax='python')
                self.check_run(built, expected.stdout.decode())

    def test_global_and_nonlocal_aliases_match_cpython(self):
        expected = cpython_output(GLOBAL_READONLY)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode(errors='replace'))
        for name, extra in (('readonly_outer', None),
                            ('readonly_outer_forced', {'AIL_UNIFIED_FORCE': '1'})):
            with self.subTest(build=name):
                built = self.compile_with(name, GLOBAL_READONLY, extra, syntax='python')
                self.check_run(built, expected.stdout.decode())

    def test_forced_general_path_still_runs(self):
        normal = self.compile_with('force_smoke', FORCE_SMOKE, syntax='python')
        forced = self.compile_with('force_smoke_forced', FORCE_SMOKE,
                                   {'AIL_UNIFIED_FORCE': '1'}, syntax='python')
        self.check_run(normal, '33\n')
        self.check_run(forced, '33\n')


if __name__ == '__main__':
    unittest.main()
