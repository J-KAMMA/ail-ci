"""Differential fuzz round 73: dict view membership and ordering.

Found with small programs compared against CPython on both builds:

A `dict_keys` view is set-like for `in`: CPython hashes the item first, so an unhashable
item raises `TypeError: unhashable type: 'list'` even when the dict is empty or after it
was cleared. The general runtime tested view membership with `ail_member_eq` over the
snapshot list, so `[1] in d.keys()` printed `False`. The list branch of
`ail_op_contains` now hashes the item first when the list is a keys view (aux == 1).
Values and items views keep CPython's compare-by-equality membership, so an unhashable
tuple value in `d.items()` still matches (CPython does not hash it there).

Unlike the keys and items views, a `dict_values` view inherits `object.__hash__` in
CPython, so `d.values() in d.keys()` is a plain `False` and `hash(d.values())` works. It
is hashed by identity here; keys and items views remain unhashable and now name
themselves (`dict_keys` / `dict_items`) in the error, not the internal snapshot `list`.

The programs below also keep hashable membership (numeric equal keys, tuples,
frozensets, huge/negative/zero keys), empty views, aliases and the other two view kinds
compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


UNHASHABLE = r'''class C:
    pass


def check(label, view, item) -> None:
    try:
        print(label, item in view)
    except TypeError as e:
        print(label, "TypeError", str(e))


def via_arg(view, item) -> None:
    check("arg", view, item)


def main() -> None:
    d = {"a": 1, "b": 2, (1, 2): 3}
    c = C()
    c.bad = [1]
    xs = [[2], {"k": 1}, {3}, (4, [5]), (6, (7, [8]))]
    vals = {"v": [9]}
    check("direct-list", d.keys(), [1])
    check("direct-dict", d.keys(), {"x": 1})
    check("direct-set", d.keys(), {1, 2})
    check("arg", d.keys(), xs[0])
    check("list-item", d.keys(), xs[1])
    check("list-item2", d.keys(), xs[2])
    check("attr", d.keys(), c.bad)
    check("dict-value", d.keys(), vals["v"])
    check("tuple-nested", d.keys(), xs[3])
    check("tuple-deep", d.keys(), xs[4])
    check("empty", {}.keys(), [1])
    via_arg(d.keys(), [1])
    print("done")


main()
'''


HASHABLE_AND_OTHER_VIEWS = r'''class C:
    pass


def has(view, item):
    return item in view


def main() -> None:
    d = {1: "a", 2: "b", "x": "c", (3, 4): "d", frozenset([5]): "e"}
    c = C()
    c.k = 2
    xs = [1, "x", (3, 4), 99, [1]]
    vals = {"k": frozenset([5])}
    print(has(d.keys(), True), has(d.keys(), 1.0), has(d.keys(), 2.0), has(d.keys(), 3.0))
    print(has(d.keys(), "x"), has(d.keys(), (3, 4)), has(d.keys(), (4, 3)))
    print(has(d.keys(), frozenset([5])), has(d.keys(), frozenset([6])))
    print(has(d.keys(), c.k), has(d.keys(), xs[0]), has(d.keys(), xs[1]))
    print(has(d.keys(), xs[2]), has(d.keys(), xs[3]), has(d.keys(), vals["k"]))
    print(has({}.keys(), 0), has({}.keys(), ""), has({}.keys(), ()))
    d[5] = "e"
    print(has(d.keys(), 5), 5 in d.keys(), 6 in d.keys(), len(d.keys()))
    print([1] in d.values(), ("x", "c") in d.items(), ("x", [1]) in d.items())
    print([1] in d.items(), ("x", "c", 1) in d.items())
    print(0 in d.keys(), -1 in d.keys(), 2**62 in d.keys(), -(2**62) in d.keys())
    print("done")


main()
'''


VIEWS_AS_ITEM = r'''def show(label, f):
    try:
        print(label, f())
    except TypeError as e:
        print(label, "TypeError", str(e))


def main() -> None:
    d = {"a": 1, (1, 2): 3}
    show("keys-as-item", lambda: d.keys() in d.keys())
    show("items-as-item", lambda: d.items() in d.keys())
    show("values-as-item", lambda: d.values() in d.keys())
    show("values-hashable", lambda: isinstance(hash(d.values()), int))
    show("values-eq-self", lambda: d.values() == d.values())
    show("values-in-values", lambda: d.values() in d.values())
    show("list-literal", lambda: [d.keys()] in d.keys())
    show("tuple-literal", lambda: (d.keys(),) in d.keys())
    show("arg-keys", lambda: (lambda x: x in d.keys())(d.keys()))
    show("dict-value", lambda: {"v": d.items()}["v"] in d.keys())
    show("empty-keys-item", lambda: {}.keys() in d.keys())
    show("empty-values-item", lambda: {}.values() in {}.keys())
    show("hash-keys", lambda: hash(d.keys()))
    show("hash-items", lambda: hash(d.items()))
    show("hash-tuple-keys", lambda: hash((d.keys(),)))
    show("hash-values", lambda: isinstance(hash(d.values()), int))
    show("after-del", lambda: (d.pop((1, 2)), d.keys() in d.keys())[1])
    show("values-after-clear", lambda: (d.clear(), d.values() in d.keys())[1])
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


class Fuzz73Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz73-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_keys_view_membership_hashes_unhashable_items(self):
        self.check('view_keys_unhashable', UNHASHABLE)

    def test_keys_view_membership_hashable_and_other_views(self):
        self.check('view_keys_hashable', HASHABLE_AND_OTHER_VIEWS)

    def test_views_used_as_the_item(self):
        self.check('view_items_all', VIEWS_AS_ITEM)


if __name__ == '__main__':
    unittest.main()
