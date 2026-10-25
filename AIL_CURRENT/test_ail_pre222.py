"""pre222: a generator expression that a set or dict must hash is refused by name.

The review of job pre207 recorded the pre-existing case p8c: ``print({(x for x in [1, 2])})``
differs from CPython.  Both builds materialise a generator expression as an eager list (pre166),
so the object cannot be the identity-hashed generator CPython stores, and no repr can agree.  The
front end now refuses the hash-key forms it can see statically, ``_check_genexpr_hash_keys``, and
the v2 runtime refuses a materialised generator expression reaching ``ail_obj_hash`` at run time;
both name the construct instead of reporting a list.  The key can also be a tuple or a
``tuple()``/``frozenset()`` call, whose elements are hashed; a consumed generator expression
(``sum``/``next``/``list``/``frozenset`` directly) and a generator expression kept as a dict
value are not hash keys and keep matching CPython.
"""
import tempfile
import unittest

from test_ail_silent1 import _build_run, check_program, check_refused

REFUSAL = 'a generator expression used as a hash key is not supported'

COMPILE_REFUSED = {
    'set_literal': 'print({(x for x in [1, 2])})\n',
    'dict_key': 'print({(x for x in [1, 2]): 1})\n',
    'set_comp': 'print({(x for x in [1, 2]) for y in [1]})\n',
    'dict_comp_key': 'print({(x for x in [1, 2]): 1 for y in [1]})\n',
    'tuple_key': 'print({((x for x in [1, 2]),): 1})\n',
    'hash_call': 'print(hash((x for x in [1, 2])))\n',
    'set_call': 'print(set([(x for x in [1, 2])]))\n',
    'frozenset_key': 'print({frozenset([(x for x in [1, 2])]): 1})\n',
}

RUNTIME_REFUSED = {
    'saved': 'g = (x for x in [1, 2])\nprint({g})\n',
    'alias': 'g = (x for x in [1, 2])\nh = g\nprint({h})\n',
    'argument': 'def f(k):\n    return {k}\n\n\nprint(f((x for x in [1, 2])))\n',
    'list_item': 'g = (x for x in [1, 2])\nxs = [g]\nprint({xs[0]})\n',
    'attribute': ('class C:\n    def __init__(self):\n        self.g = (x for x in [1, 2])\n\n\n'
                  'print({C().g})\n'),
    'dict_value': 'g = (x for x in [1, 2])\nd = {"k": g}\nprint({d["k"]})\n',
    'add': 's = set()\ns.add((x for x in [1, 2]))\nprint(s)\n',
    'membership': 'print((x for x in [1, 2]) in set())\n',
    'subscript': 'd = {}\nd[(x for x in [1, 2])] = 1\nprint(d)\n',
    'hash_name': 'g = (x for x in [1, 2])\nprint(hash(g))\n',
    'tuple_key': 'g = (x for x in [1, 2])\nprint({(g,): 1})\n',
}

PLAIN_LIST = 'print({[1, 2]})\n'
FROZENSET_CONSUMED = 'print(frozenset(x for x in [1, 2, 2]))\n'
EATEN = 'print(sum(x * x for x in [1, 2]))\ng = (x for x in [1, 2])\nprint(next(g))\nprint(list(g))\n'
DICT_VALUE = 'd = {"k": (x for x in [1, 2])}\nprint(len(d), d["k"] is d["k"])\n'
CONSUMER_KEYS = 'print({tuple(x for x in [1, 2]): 1})\nprint({frozenset(x for x in [1, 2]): 2})\n'

# A name the program binds is not the builtin, so the static refusal must not fire; the call runs
# as CPython's does.
SHADOWED = {
    'module_def_hash': 'def hash(x):\n    return 42\n\n\nprint(hash((x for x in [1, 2])))\n',
    'nested_def_hash': ('def f():\n    def hash(x):\n        return 42\n    return hash((x for x in [1, 2]))\n\n\n'
                        'print(f())\n'),
    'assigned_hash': 'def f(x):\n    return 42\n\n\nhash = f\nprint(hash((x for x in [1, 2])))\n',
    'nested_def_set': ('def f():\n    def set(x):\n        return len(x)\n    return set([(x for x in [1, 2])])\n\n\n'
                       'print(f())\n'),
    'nested_def_frozenset': ('def f():\n    def frozenset(x):\n        return 7\n    return {frozenset([(x for x in [1, 2])]): 1}\n\n\n'
                             'print(f())\n'),
    'nested_def_tuple': ('def f():\n    def tuple(x):\n        return 5\n    return {tuple([(x for x in [1, 2])]): 1}\n\n\n'
                         'print(f())\n'),
}


def _runtime_refusal(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre222-') as directory:
        for general in (True, False):
            got, err = _build_run(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, err))
            stdout, rc, last = got
            test.assertEqual(rc, 1, '%s (general=%s)\n%s' % (text[:2000], general, last))
            test.assertEqual(stdout, b'', '%s (general=%s)\n%s' % (text[:2000], general, last))
            test.assertIn(REFUSAL, last, '%s (general=%s)' % (text[:2000], general))


class Pre222Tests(unittest.TestCase):
    def test_static_hash_keys_are_refused(self):
        for name, text in COMPILE_REFUSED.items():
            with self.subTest(name=name):
                check_refused(self, name, text, (REFUSAL,))

    def test_runtime_hash_keys_are_refused(self):
        for name, text in RUNTIME_REFUSED.items():
            with self.subTest(name=name):
                _runtime_refusal(self, name, text)

    def test_plain_list_key_still_matches_cpython(self):
        check_program(self, 'plain_list', PLAIN_LIST, rc=1)

    def test_consumed_and_value_genexprs_match_cpython(self):
        check_program(self, 'frozenset_consumed', FROZENSET_CONSUMED)
        check_program(self, 'eaten', EATEN)
        check_program(self, 'dict_value', DICT_VALUE)
        check_program(self, 'consumer_keys', CONSUMER_KEYS)

    def test_bound_names_are_not_refused(self):
        for name, text in SHADOWED.items():
            with self.subTest(name=name):
                check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
