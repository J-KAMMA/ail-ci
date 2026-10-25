"""pre208: a module-level shadow of a built-in keeps Python's fallback to the built-in.

The pre-existing difference recorded after job rbpre142 (`p4_scope`): a module-level
rebinding such as `next = next`, or a read of `next` before the rebinding it later gets,
failed on both builds with `NameError: name 'py_next' is not defined` where CPython uses
the built-in.  The shadowing pass renames such a binding to `py_next`, and `py_next` has no
built-in fallback: CPython's module LOAD_NAME checks the built-in when the global is not
bound, and a `del` of the shadow makes it unbound again.  Those shapes are now refused by
name at compile time (`shadows the built-in next`), while an ordinary rebinding that is
only read after it is bound still matches CPython on both builds.
"""
import shutil
import unittest

from test_ail_silent1 import check_program, check_refused

REFUSED = {
    'self_rebind': '''next = next
print(next is not None)
''',
    'read_before_binding': '''print(next(iter([1])))
next = lambda x: 0
''',
    'before_binding_in_function': '''def first():
    return next(iter([1]))

print(first())
next = lambda x: 0
''',
    'delete_after_binding': '''next = lambda x: 5
print(next([1]))
del next
print(next([1]))
''',
    'delete_then_builtin': '''def next(x):
    return x

del next
print(next(iter([1])))
''',
    'delete_through_alias': '''next = lambda x: 5
saved = next
del next
print(saved([1]))
print(next([1]))
''',
}

MATCHES = {
    'plain_rebind': '''next = lambda xs: -1
print(next([1, 2]))
''',
    'constant_rebind': '''next = 3
print(next + 1)
''',
    'read_after_binding': '''def first():
    return next(iter([1]))

next = lambda x: 7
print(first())
''',
    'def_binding': '''def next(x):
    return 42

print(next([1]))
''',
    'global_builtin': '''def main():
    global next
    print(next(iter([1])))

main()
''',
}


@unittest.skipUnless(shutil.which('gcc'), 'needs gcc')
class ReboundBuiltinFallback(unittest.TestCase):
    def test_unsafe_fallback_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'pre208_' + name, text,
                              ('shadows the built-in next', 'write instead'))

    def test_safe_rebinding_matches_cpython(self):
        for name, text in sorted(MATCHES.items()):
            with self.subTest(name):
                check_program(self, 'pre208_' + name, text)


if __name__ == '__main__':
    unittest.main()
