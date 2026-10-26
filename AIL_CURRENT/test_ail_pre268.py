"""pre268: any()/all() must close a generator-function iterable at the deciding element.

The pre-existing difference recorded from job rbpre42's lineage (r89): the non-fused
any()/all() path stopped at the first deciding element but dropped only the iterator, so
CPython's generator deallocation -- which runs the generator's finally block -- never
happened.  A fresh generator call, directly or as the iterable of a fused generator
expression, now runs that cleanup before the call returns.  An object reached through a
parameter, a Name local, a list item, an attribute or a dict value is not closed early,
because that reference keeps it alive in CPython too; a parameter stays resumable after
any()/all() returns, and consuming the generator fully still prints the cleanup once.  An
exception raised by the finally block during this implicit cleanup is ignored, as CPython
ignores it during generator deallocation.
"""
import tempfile
import unittest

from test_ail_silent1 import _build_run, _cpython, check_program


def check_stdout(test, name, text, modes=(True, False), rc=0):
    """Like check_program, but stderr is not compared: CPython writes its
    "Exception ignored in:" notice while deallocating the generator, which is not
    part of the program's output; stdout and the exit status must still match."""
    with tempfile.TemporaryDirectory(prefix='ail-pre268-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got[0], want[0], '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got[1], want[1], '%s (general=%s)\n%s' % (text[:3000], general, err))


CLEANUP = r'''def g(tag):
    try:
        print("start", tag)
        yield 1
        print("after1", tag)
        yield 2
        print("after2", tag)
        yield 3
    finally:
        print("cleanup", tag)


def h(tag):
    try:
        yield 0
        yield 1
        yield 2
    finally:
        print("cleanup", tag)


def take(it):
    r = any(it)
    rest = list(it)
    print("arg-rest", rest)
    return r


def main() -> None:
    print("direct-any", any(g("direct-any")))
    print("direct-all", all(h("direct-all")))
    print("genexpr-any", any(x for x in g("genexpr-any")))
    print("genexpr-all", all(x for x in h("genexpr-all")))
    print("filter-any", any(x for x in g("filter-any") if x > 0))
    print("filter-all", all(x for x in h("filter-all") if x >= 0))
    print("arg", take(g("arg")))
    print("done")


main()
'''

KEPT_REFERENCES = r'''def one_two(tag):
    try:
        yield 1
        yield 2
    finally:
        print("cleanup", tag)


class Box:
    def __init__(self, it):
        self.it = it


def take(it):
    r = any(it)
    print("after-any")
    rest = list(it)
    print("rest", rest)
    return r


def main() -> None:
    it = one_two("local")
    print("local-any", any(it))
    print("local-rest", list(it))
    xs = [one_two("item")]
    print("item-any", any(xs[0]))
    print("item-rest", list(xs[0]))
    box = Box(one_two("attr"))
    print("attr-any", any(box.it))
    print("attr-rest", list(box.it))
    d = {"k": one_two("dict")}
    print("dict-any", any(d["k"]))
    print("dict-rest", list(d["k"]))
    alias = one_two("alias")
    print("alias-result", take(alias))
    print("caller-rest", list(alias))
    print("done")


main()
'''

EDGES = r'''def empty(tag):
    try:
        if False:
            yield 1
    finally:
        print("cleanup", tag)


def raising(tag):
    try:
        yield 1
        raise ValueError("boom " + tag)
    finally:
        print("cleanup", tag)


def main() -> None:
    print("empty-any", any(empty("e1")))
    print("empty-all", all(empty("e2")))
    print("empty-genexpr", any(x for x in empty("e3")))
    try:
        print(any(raising("r1")))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(any(x for x in raising("r2")))
    except ValueError as e:
        print("ValueError", e)
    print("done")


main()
'''

FINALLY_RAISES = r'''def g(tag):
    try:
        print("start", tag)
        yield 1
        yield 2
    finally:
        print("cleanup", tag)
        raise ValueError("boom " + tag)


def h(tag):
    try:
        print("start", tag)
        yield 0
        yield 1
    finally:
        print("cleanup", tag)
        raise ValueError("boom " + tag)


def main() -> None:
    print("direct-any", any(g("d")))
    print("direct-all", all(h("a")))
    print("genexpr-any", any(x for x in g("e")))
    print("filter-all", all(x for x in h("f") if x >= 0))
    print("done")


main()
'''

CONTROL = r'''def f(x):
    return x


def main() -> None:
    print(any([0, 1, 2]), all([1, 2, 3]), any([]), all([]))
    print(any(f(x) for x in [0, 1, 2]), all(f(x) for x in [1, 0, 2]))
    it = iter([1, 2, 3])
    print(any(it), list(it))
    print("done")


main()
'''


class GeneratorIterableCleanup(unittest.TestCase):
    def test_early_exit_closes_generator(self):
        check_program(self, 'pre268_cleanup', CLEANUP)

    def test_external_references_are_not_closed_early(self):
        check_program(self, 'pre268_kept', KEPT_REFERENCES)

    def test_empty_raising_and_nested_filter(self):
        check_program(self, 'pre268_edges', EDGES)

    def test_finally_exception_during_cleanup_is_ignored(self):
        check_stdout(self, 'pre268_finally', FINALLY_RAISES)

    def test_non_generator_iterables_unchanged(self):
        check_program(self, 'pre268_control', CONTROL)


if __name__ == '__main__':
    unittest.main()
