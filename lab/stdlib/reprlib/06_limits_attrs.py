import reprlib


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return "Point(%d, %d, with a long annotation)" % (self.x, self.y)


def main():
    r = reprlib.Repr()
    r.maxlist = 3
    r.maxstring = 10
    r.maxdict = 2
    r.maxlevel = 2
    r.maxother = 8
    r.fillvalue = "<...>"
    print("list", r.repr(list(range(10))))
    print("string", r.repr("abcdefghijklmnop"))
    print("dict", r.repr({1: "one", 2: "two", 3: "three"}))
    print("other", r.repr(Point(1, 2)))
    print("nested", r.repr([{"a": [1, 2, 3, 4]}]))
    print("defaults", reprlib.Repr().maxlist, reprlib.Repr().maxstring,
          reprlib.Repr().maxdict, reprlib.Repr().maxlevel,
          reprlib.Repr().maxother, reprlib.Repr().fillvalue)


main()
