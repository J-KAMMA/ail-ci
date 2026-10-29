"""rdiff7: class features on the general path, compared with CPython 3.12.

* `__slots__`: assigning a name outside the slots of a class whose whole base chain has `__slots__` (no
  `__dict__`) silently created the attribute; CPython raises AttributeError ("'C' object has no attribute
  'x'", or "... attribute 'x' is read-only" for a class attribute). Plain stores, augmented stores and
  `setattr(obj, "name", v)` check; a computed `setattr` name in such a program is refused by name.
* The default repr of an instance (no __repr__ / __str__) was `<C object>`; CPython's is
  `<__main__.C object at 0x...>` (the address differs between any two runs, the shape now agrees).
* `a > b`, `a <= b`, `a >= b` on instances whose class defines only `__gt__` / `__le__` / `__ge__` (no
  __lt__) raised TypeError; they call the method (or the reflected one of the right operand).
The typed path refuses these programs (AttributeError, a printed object) or already agreed; the comparison
program is checked there too.
"""
from test_ail_pathlib import Base


SLOTS = r'''class Base:
    __slots__ = ("x",)
    LIMIT = 10

    def __init__(self, x: int) -> None:
        self.x = x


class Child(Base):
    __slots__ = ("y",)

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x)
        self.y = y


class Open(Base):
    def __init__(self, x: int) -> None:
        super().__init__(x)
        self.z = 1


class Empty:
    __slots__ = ()


class Single:
    __slots__ = "only"

    def __init__(self) -> None:
        self.only = 0


class Plain:
    def __init__(self) -> None:
        self.a = 1


def main() -> None:
    c = Child(1, 2)
    c.x += 10
    c.y = c.y * 3
    print(c.x, c.y)
    try:
        c.z = 3
    except AttributeError as e:
        print("child:", e)
    try:
        c.LIMIT = 3
    except AttributeError as e:
        print("limit:", e)
    o = Open(4)
    o.w = 9
    print(o.x, o.z, o.w)
    try:
        setattr(Empty(), "q", 5)
    except AttributeError as e:
        print("empty:", e)
    s = Single()
    s.only += 1
    print(s.only)
    try:
        s.other = 2
    except AttributeError as e:
        print("single:", e)
    items = [Base(1), Child(2, 3), Open(4)]
    for it in items:
        try:
            it.tag = "t"
            print(type(it).__name__, "tagged")
        except AttributeError as e:
            print(type(it).__name__, "refused", e)
    p = Plain()
    p.b = 2
    print(p.a, p.b)


main()
'''

COMPUTED_SETATTR = r'''class P:
    __slots__ = ("a",)

    def __init__(self) -> None:
        self.a = 1


def main() -> None:
    name = "a" if len("x") == 1 else "b"
    setattr(P(), name, 2)
    print("done")


main()
'''

DEFAULT_REPR = r'''class Plain:
    def __init__(self, v: int) -> None:
        self.v = v


def main() -> None:
    x = Plain(1)
    r = repr(x)
    print(r[:28], r.endswith(">"), str(x) == r, f"{x}" == r, "%s" % x == r, str([x]) == "[" + r + "]")


main()
'''

RICH_COMPARE = r'''class G:
    def __init__(self, v: int) -> None:
        self.v = v

    def __gt__(self, o: "G") -> bool:
        return self.v > o.v

    def __le__(self, o: "G") -> bool:
        return self.v <= o.v

    def __ge__(self, o: "G") -> bool:
        return self.v >= o.v


class H(G):
    def __gt__(self, o: "G") -> bool:
        print("H.gt")
        return True


def main() -> None:
    x = G(1)
    y = G(2)
    print(x > y, y > x, x <= y, y <= x, x >= y, y >= x, x < y)
    pairs = [(G(1), G(2)), (H(1), G(5)), (G(3), H(0))]
    for a, b in pairs:
        print(a > b, a < b, a <= b, a >= b)


main()
'''


class ClassFeatures(Base):
    def test_slots_reject_other_names(self):
        self.compare('rdiff7_slots_default', SLOTS, mode='default')
        self.compare('rdiff7_slots_general', SLOTS, mode='gonly')

    def test_computed_setattr_with_slots_is_refused(self):
        self.refused(COMPUTED_SETATTR, 'setattr() with a computed name in a program with a __slots__ class',
                     mode='gonly')

    def test_default_instance_repr(self):
        self.compare('rdiff7_repr_general', DEFAULT_REPR, mode='gonly')

    def test_greater_and_less_equal_methods(self):
        self.compare('rdiff7_cmp_general', RICH_COMPARE, mode='gonly')
        self.compare('rdiff7_cmp_default', RICH_COMPARE, mode='default')
