import reprlib


def raw_node(self):
    return "Node(%s -> %r)" % (self.name, self.child)


node_render = reprlib.recursive_repr()(raw_node)


def raw_other(self):
    return "Other(%s -> %r)" % (self.name, self.child)


other_render = reprlib.recursive_repr(fillvalue="<cycle>")(raw_other)


class Node:
    def __init__(self, name):
        self.name = name
        self.child = None

    def __repr__(self):
        return node_render(self)


class Other:
    def __init__(self, name):
        self.name = name
        self.child = None

    def __repr__(self):
        return other_render(self)


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
