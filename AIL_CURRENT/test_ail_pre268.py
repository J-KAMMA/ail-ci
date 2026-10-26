"""pre268: any()/all() must close a generator-function iterable at the deciding element.

The pre-existing difference recorded from job rbpre42's lineage (r89): the non-fused
any()/all() path stopped at the first deciding element but dropped only the iterator, so
CPython's generator deallocation -- which runs the generator's finally block -- never
happened.  A generator passed directly, as a fresh call through an argument, or as the
iterable of a fused generator expression now runs that cleanup before the call returns.
The same object reached through a Name local, a list item, an attribute or a dict value
is not closed early, because that reference keeps it alive in CPython too; consuming it
fully still prints the cleanup exactly once.
"""
import unittest

from test_ail_silent1 import check_program


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
    return any(it)


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


def all_false(tag):
    try:
        yield 0
        yield 0
    finally:
        print("cleanup", tag)


class Box:
    def __init__(self, it):
        self.it = it


def main() -> None:
    it = one_two("local")
    print("early", any(it))
    print("mid")
    print("rest", all(it))
    xs = [all_false("item")]
    print("item", any(xs[0]))
    box = Box(all_false("attr"))
    print("attr", any(box.it))
    d = {"k": all_false("dict")}
    print("dict", any(d["k"]))
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

    def test_non_generator_iterables_unchanged(self):
        check_program(self, 'pre268_control', CONTROL)


if __name__ == '__main__':
    unittest.main()
