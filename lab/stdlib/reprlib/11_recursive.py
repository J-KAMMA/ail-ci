import reprlib


class Node:
    def __init__(self, name):
        self.name = name
        self.child = None

    @reprlib.recursive_repr()
    def __repr__(self):
        return "Node(%s -> %r)" % (self.name, self.child)


class Other:
    def __init__(self, name):
        self.name = name
        self.child = None

    @reprlib.recursive_repr(fillvalue="<cycle>")
    def __repr__(self):
        return "Other(%s -> %r)" % (self.name, self.child)


def main():
    a = Node("a")
    b = Node("b")
    a.child = b
    b.child = a
    print("default", repr(a))
    print("other", repr(b))
    x = Other("x")
    y = Other("y")
    x.child = y
    y.child = x
    print("custom", repr(x))
    print("custom again", repr(y))
    plain = Node("plain")
    print("plain", repr(plain))


main()
