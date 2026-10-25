"""pre112: a frozenset of tuples as a dict key must not be lowered to the tuple pass's table class.

The tuple pass (tuplib.py) lowers `frozenset({(1, 'a'), (2, 'b')})` to an open-addressing table class
(`_AilS_Pi_sQ`).  When the same expression is a *dict key*, the table class cannot be built (a set is not
a table key), so the dict stays a plain object; lowering only the key then hashes a table-set object
against a plain frozenset and every lookup misses.  On a module-level assignment whose type could not be
told the pass also swallowed the refusal and lowered the key anyway.  `D[frozenset({(1, 'a'), (2, 'b')})]`
raised `KeyError`, `frozenset(...) in D` printed False and `D.get(...)` returned None.

Now the pass refuses the set-of-tuples key (so the whole program is left as written) and also bails on a
module-level constant it cannot type that mentions a tuple; the general path keeps the dict and its key
boxed, matching CPython.

The programs print lookup / membership / length results only: the *order* of a frozenset's own repr is a
separate, known difference (hash randomization), so a raw print of the set is not compared here.  Each
program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INLINE_KEY = r'''D = {frozenset({(1, "a"), (2, "b")}): "found"}
print(D[frozenset({(1, "a"), (2, "b")})])
print(frozenset({(1, "a"), (2, "b")}) in D)
print(D.get(frozenset({(1, "a"), (2, "b")})))
print(D.get(frozenset({(9, "z")}), "missing"))
print(len(D))
'''

STORE_AND_MEMBERSHIP = r'''D = {}
D[frozenset({(1, "a"), (2, "b")})] = "v"
print(D[frozenset({(1, "a"), (2, "b")})])
D[frozenset({(3, "c")})] = "w"
print(D[frozenset({(3, "c")})], D[frozenset({(1, "a"), (2, "b")})])
print(D.setdefault(frozenset({(1, "a"), (2, "b")}), "x"))
print(D.setdefault(frozenset({(4, "d")}), "y"))
print(D[frozenset({(4, "d")})])
print(D.pop(frozenset({(1, "a"), (2, "b")})))
print(len(D), frozenset({(4, "d")}) in D)
'''

LOOKUP_FORMS = r'''class Holder:
    def __init__(self, d):
        self.d = d


def lookup(d, k):
    return d[k]


def mem(d, k):
    return k in d


key = frozenset({(1, "a"), (2, "b")})
container = {key: "from-var"}
print(lookup(container, key))
holder = Holder({frozenset({(1, "a")}): "attrval"})
print(lookup(holder.d, frozenset({(1, "a")})))
lst = [{frozenset({(1, "a"), (2, "b")}): "listitem"}]
print(lookup(lst[0], frozenset({(1, "a"), (2, "b")})))
outer = {"k": {frozenset({(1, "a"), (2, "b")}): "dictval"}}
print(lookup(outer["k"], frozenset({(1, "a"), (2, "b")})))
print(mem(container, frozenset({(2, "b"), (1, "a")})))
print(mem({key: 1}, frozenset({(1, "a"), (2, "b")})))
print({key: 1}[key])
print(lookup({frozenset({(5, "e"), (6, "f")}): "arg"}, frozenset({(6, "f"), (5, "e")})))
'''

BOUNDARIES = r'''E = {frozenset({}): "empty"}
print(E[frozenset({})])
F = {frozenset({(1, "a")}): "one"}
print(F[frozenset({(1, "a")})])
G = {frozenset({(1, 2, 3), (4, 5, 6)}): "triples"}
print(G[frozenset({(4, 5, 6), (1, 2, 3)})])
H = {frozenset({(-1, "a"), (2.5, "b")}): "negfloat"}
print(H[frozenset({(2.5, "b"), (-1, "a")})])
I = {frozenset({1, 2}): "ints"}
print(I[frozenset({2, 1})])
J = {frozenset({"a", "b"}): "strs"}
print(J[frozenset({"b", "a"})])
shared = frozenset({(1, "a"), (2, "b")})
aliases = [shared, shared]
K = {shared: "alias"}
print(K[aliases[0]], K[aliases[1]], K[frozenset({(1, "a"), (2, "b")})])
print(K[shared] == K[frozenset({(2, "b"), (1, "a")})])
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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


class Pre112Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre112-') as directory:
            want, rc = _cpython(directory, slug, text)
            self.assertEqual(rc, 0)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_inline_key(self):
        self.check('inline_key', INLINE_KEY)

    def test_store_and_membership(self):
        self.check('store_membership', STORE_AND_MEMBERSHIP)

    def test_lookup_forms(self):
        self.check('lookup_forms', LOOKUP_FORMS)

    def test_boundaries(self):
        self.check('boundaries', BOUNDARIES)


if __name__ == '__main__':
    unittest.main()
