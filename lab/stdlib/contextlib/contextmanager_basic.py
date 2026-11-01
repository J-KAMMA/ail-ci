from contextlib import contextmanager


@contextmanager
def section(name):
    print("enter", name)
    try:
        yield name.upper()
    finally:
        print("leave", name)


def work(label, fail):
    with section(label) as tag:
        print("work", tag)
        if fail:
            raise ValueError(label)
    print("done", label)


work("a", False)
try:
    work("b", True)
except ValueError as e:
    print("caught", e)

for i in range(3):
    with section("loop%d" % i):
        if i == 1:
            continue
        if i == 2:
            break
        print("body", i)


def early(flag):
    with section("early"):
        if flag:
            return "returned"
    return "fell"


print(early(True), early(False))
