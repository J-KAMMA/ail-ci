"""rdiff8: formatting and print() differences from CPython 3.12.

* The '0' flag of a format spec with an explicit alignment (`format(5, "<08d")` is '50000000',
  `f"{-5:^08d}"` is '000-5000') and on a str (`f"{s:05}"` is 'ab000') padded with spaces, or put the zeros
  on the wrong side, on the general path (f-strings, format(), str.format). A fill character given before
  the alignment still wins, and printf-style `%-05d` still pads with spaces.
* print() turns its arguments into text only after evaluating all of them: `print(xs, xs.pop())` shows
  the list without the popped element, and `print(s, s.pop())` calls `s.__str__` after the pop. The typed
  path (a list) and the general path (an instance with __str__) printed the earlier state; a list given by
  an expression other than a name, followed by an argument that calls, is refused by name on the typed path.
  The typed path's alias scan also missed a list read by a call after another argument of that call wrote
  it through an alias (`xs = h.items; print(xs, h.take())`): that is the alias refusal now.
* A typed-path refusal message built from an object type (`"(" + repr(self.rows) + ")"` in a method)
  raised TypeError inside the compiler instead of refusing by name (so the default build failed too).
"""
from test_ail_pathlib import Base


ZERO_FLAG = r'''def main() -> None:
    n = 5
    m = -5
    x = -1.5
    s = "ab"
    print(f"{n:<08d}|{m:^08d}|{n:>08d}|{m:x<08d}|{x:<08.2f}|{x:^09.1f}|{n:08d}|{m:=08d}|")
    print(f"{x:<+08.2f}|{n:<#08x}|{n:^#010b}|{n:<05}|{x:<08}|{x:>08}|{n:^05}|")
    print(f"{s:<05}|{s:05}|{s:>05}|{s:^05}|{s:*<05}|")
    print(format(n, "<08d"), format(x, "^09.1f"), format(s, "<05"), format(m, "<06"), format(s, "05"))
    print("{:<08d}|{:^09.1f}|{:<05}|{:05}".format(n, x, s, s))
    print("%-05d|%05d|%-08.2f|%08.2f|%-5s|" % (n, m, x, x, s))


main()
'''

TYPED_ZERO_FLAG = r'''def main() -> None:
    n = 5
    m = -5
    x = -1.5
    print(f"{n:<08d}|{m:^08d}|{n:>08d}|{m:x<08d}|{x:<08.2f}|{x:^09.1f}|{n:08d}|{m:=08d}|")
    print(f"{x:<+08.2f}|{n:<#08x}|{n:^#010b}|{n:<05}|{x:<08}|{x:>08}|{n:^05}|")


main()
'''

PRINT_ORDER = r'''class Stack:
    def __init__(self) -> None:
        self.items: list[int] = []

    def push(self, x: int) -> None:
        self.items.append(x)

    def pop(self) -> int:
        return self.items.pop()

    def __str__(self) -> str:
        return "Stack" + str(len(self.items))

    def __repr__(self) -> str:
        return "S" + str(len(self.items))


def main() -> None:
    s = Stack()
    for i in range(5):
        s.push(i * i)
    print(s, s.pop(), s.pop(), s)
    print(repr(s), s.pop(), s)
    print(f"{s}", s.pop(), str(s), s)
    xs = [1, 2, 3]
    print(xs, xs.pop(), xs)
    ys = [4, 5]
    print(ys, ys.pop(0), ys, sep="|")


main()
'''

PRINT_ORDER_REFUSED = r'''class Holder:
    def __init__(self) -> None:
        self.items = [1, 2, 3]

    def take(self) -> int:
        return self.items.pop()


def main() -> None:
    h = Holder()
    print(h.items, h.take(), h.items)


main()
'''

ALIAS_IN_ONE_STATEMENT = r'''class Holder:
    def __init__(self) -> None:
        self.items = [1, 2, 3]

    def take(self) -> int:
        return self.items.pop()


def main() -> None:
    h = Holder()
    xs = h.items
    print(xs, h.take(), xs)


main()
'''

OBJECT_REPR_FIELD = r'''class Grid:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows

    def __repr__(self) -> str:
        return "Grid(" + repr(self.rows) + ")"


def main() -> None:
    g = Grid([[1, 2], [3]])
    print(repr(g))


main()
'''


class FormattingAndPrint(Base):
    def test_zero_flag_with_an_alignment(self):
        self.compare('rdiff8_zero_default', ZERO_FLAG, mode='default')
        self.compare('rdiff8_zero_general', ZERO_FLAG, mode='gonly')
        self.compare('rdiff8_zero_typed', TYPED_ZERO_FLAG, mode='typed')
        self.compare('rdiff8_zero_typed_general', TYPED_ZERO_FLAG, mode='gonly')

    def test_print_shows_values_after_every_argument_ran(self):
        self.compare('rdiff8_order_typed', PRINT_ORDER, mode='typed')
        self.compare('rdiff8_order_general', PRINT_ORDER, mode='gonly')

    def test_list_expression_before_a_call_is_refused_on_the_typed_path(self):
        self.refused(PRINT_ORDER_REFUSED, 'print() of a list followed by an argument that runs code',
                     'write instead:')
        self.compare('rdiff8_order_refused_default', PRINT_ORDER_REFUSED, mode='default')

    def test_alias_written_and_read_in_one_statement(self):
        self.refused(ALIAS_IN_ONE_STATEMENT, 'makes a second reference to the same container')
        self.compare('rdiff8_alias_default', ALIAS_IN_ONE_STATEMENT, mode='default')

    def test_object_typed_refusal_names_the_type(self):
        self.refused(OBJECT_REPR_FIELD, 'an f-string field of type list[list[int]]')
        self.compare('rdiff8_repr_default', OBJECT_REPR_FIELD, mode='default')
