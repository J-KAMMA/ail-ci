from contextlib import ExitStack


class Track:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        print("enter", self.name)
        return self.name.upper()

    def __exit__(self, exc_type, exc, tb):
        print("exit", self.name, exc_type is None)
        return False


def build(names):
    stack = ExitStack()
    for name in names:
        stack.enter_context(Track(name))
    return stack


def open_outer(name):
    stack = ExitStack()
    stack.push(Track(name))
    return stack


with ExitStack() as outer:
    outer.enter_context(Track("first"))
    inner = build(["second", "third"])
    held = outer.pop_all()
    with held as reopened:
        reopened.enter_context(Track("fourth"))
    print("outer body")
print("after outer")

box = {"stack": build(["dict"])}
with box["stack"] as stack:
    stack.enter_context(Track("dict-extra"))
print("after dict")

for name in ["loop0", "loop1"]:
    stack = open_outer(name)
    with stack:
        stack.enter_context(Track(name + "-inner"))
        if name == "loop0":
            continue
    print("after", name)
