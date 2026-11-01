import copy

class Node:
    def __init__(self, label: str, children: list) -> None:
        self.label = label
        self.children = children

    def show(self) -> str:
        return self.label + ":" + str(len(self.children))

def main() -> None:
    inner = Node("inner", [])
    outer = Node("outer", [inner])
    clone = copy.deepcopy(outer)
    clone.label = "clone"
    clone.children.append(Node("new", []))
    clone.children[0].label = "inner-clone"
    print(outer.label, outer.show())
    print(clone.label, clone.show())
    print(outer.children[0].label)
    print(clone.children[0].label)
    print(outer.children[0] is clone.children[0])
    print(len(outer.children), len(clone.children))

main()
