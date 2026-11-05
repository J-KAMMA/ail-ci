import reprlib


class Node:

    def __init__(self, name):
        self.name = name
        self.items = []

    @reprlib.recursive_repr()
    def __repr__(self):
        return "Node(" + self.name + ", " + repr(self.items) + ")"


def main():
    node = Node("root")
    node.items.append(node)
    print(reprlib.repr(node))
    print(repr(node))
    outer = Node("outer")
    inner = Node("inner")
    outer.items.append(inner)
    inner.items.append(outer)
    print(reprlib.repr(outer))
    print(reprlib.repr([node, outer]))


main()
