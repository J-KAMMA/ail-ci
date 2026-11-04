import reprlib


class Widget:
    def __repr__(self):
        return "Widget(with a long descriptive representation)"


def main():
    r = reprlib.Repr(maxlist=2, maxstring=8, maxdict=1, maxlevel=2,
                     maxother=5, fillvalue="~")
    print("list", r.repr([1, 2, 3, 4, 5]))
    print("string", r.repr("abcdefghijklmnop"))
    print("dict", r.repr({"a": 1, "b": 2, "c": 3}))
    print("tuple", r.repr((1, 2, 3, 4, 5, 6, 7)))
    print("set", r.repr({1, 2, 3, 4, 5, 6, 7, 8}))
    print("frozenset", r.repr(frozenset({1, 2, 3, 4, 5, 6, 7, 8})))
    print("nested", r.repr({"k": [1, 2, 3, 4]}))
    print("other", r.repr(Widget()))
    t = reprlib.Repr(maxtuple=3, maxset=2, maxfrozenset=2, maxarray=1)
    print("tuple 3", t.repr((1, 2, 3, 4, 5)))
    print("set 2", t.repr({1, 2, 3, 4, 5}))
    print("frozen 2", t.repr(frozenset({1, 2, 3, 4, 5})))


main()
