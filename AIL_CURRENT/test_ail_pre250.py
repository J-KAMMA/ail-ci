"""pre250: a module-level shadow of a built-in while Python still resolves the built-in.

The pre-existing difference recorded by the pre208 reviewer: `for x in [1]: print(next)`
before `next = 5` gave `NameError: name 'py_next' is not defined` on both builds, where
CPython reads the built-in in the loop and rebinds the name afterwards.  The shadowing
pass renames the binding to `py_next`, which has no fallback to the built-in, so a
module-level read before the first binding (or after a `del`) is refused by name at
compile time.  Function and lambda bodies are deferred, constant-false branches are
pruned, and bindings made by `for`, `try`, `with`, `match`, parameters, locals and
comprehension variables keep their own meaning, so those programs still match CPython.
"""
import shutil
import unittest

from test_ail_silent1 import check_program, check_refused

REFUSED = {
    'for_read_before_binding': '''for x in [1]:
    print(next)
next = 5
print(next)
''',
    'read_before_binding': '''print(next(iter([7, 8])))
next = lambda x: 0
''',
    'self_rebind': '''next = next
print(next is not None)
''',
    'read_in_list': '''xs = [next]
next = 5
print(xs[0] is not None, next)
''',
    'read_in_dict': '''d = {"k": next}
next = 5
print(d["k"] is not None, next)
''',
    'read_in_attribute': '''class Box:
    pass
b = Box()
b.v = next
next = 5
print(b.v is not None, next)
''',
    'read_as_argument': '''def f(v):
    return v is not None
print(f(next))
next = 5
print(next)
''',
    'read_after_delete': '''next = lambda x: 5
del next
print(next(iter([1])))
''',
    'augassign_before_binding': '''next += 1
print(next)
''',
}

MATCHES = {
    'function_read_after_binding': '''def first():
    return next(iter([1]))
next = lambda x: 7
print(first())
''',
    'for_target_binding': '''for next in [1, 2]:
    print(next)
next = 5
print(next)
''',
    'try_binding': '''try:
    next = 5
except Exception:
    next = 6
print(next)
next = 7
print(next)
''',
    'with_binding': '''class C:
    def __enter__(self):
        return 4
    def __exit__(self, a, b, c):
        return False
with C() as next:
    print(next)
next = 8
print(next)
''',
    'match_binding': '''match 5:
    case next:
        print(next)
next = 9
print(next)
''',
    'if_binding_before_read': '''if True:
    next = 5
    print(next)
next = 6
print(next)
''',
    'parameter_and_local': '''def f(next):
    return next + 1
def g():
    next = 5
    return next
print(f(1), g())
next = lambda x: 0
print(next(1))
''',
    'comprehension_variable': '''def f():
    return [next for next in range(3)]
print(f())
next = lambda x: 0
print(next(1))
''',
    'dead_if_false': '''if False:
    print(next(iter([1])))
next = lambda x: 0
print(next(1))
''',
    'delete_last': '''next = lambda x: 5
print(next([1]))
del next
''',
    'delete_rebind': '''next = lambda x: 3
del next
next = lambda x: 7
print(next([1]))
''',
    'augassign_after_binding': '''next = 1
next += 2
print(next)
''',
    'plain_program': '''def f(xs):
    return [x * 2 for x in xs if x > 0]
print(f([1, -2, 3]))
''',
}


@unittest.skipUnless(shutil.which('gcc'), 'needs gcc')
class ReboundBuiltinFallback(unittest.TestCase):
    def test_unsafe_fallback_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'pre250_' + name, text,
                              ('shadows the built-in next', 'write instead'))

    def test_safe_rebinding_matches_cpython(self):
        for name, text in sorted(MATCHES.items()):
            with self.subTest(name):
                check_program(self, 'pre250_' + name, text)


if __name__ == '__main__':
    unittest.main()
