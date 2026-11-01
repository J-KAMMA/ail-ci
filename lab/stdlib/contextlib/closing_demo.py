from contextlib import closing


class Session:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def close(self):
        self.closed = True
        print("close", self.name)


def run(name, fail):
    s = Session(name)
    try:
        with closing(s) as got:
            print("open", got.name, got is s, s.closed)
            if fail:
                raise RuntimeError(name)
    except RuntimeError as e:
        print("error", e)
    print("state", s.closed)


run("a", False)
run("b", True)

cm = closing(Session("value"))
with cm as s2:
    print("value", s2.name)
print("value state", s2.closed)

with closing(Session("x")), closing(Session("y")):
    print("nested")

box = []
with closing(Session("list")) as s3:
    box.append(s3)
print("box", box[0].name, box[0].closed)

holder = {"cm": closing(Session("dict"))}
with holder["cm"] as s4:
    print("dict", s4.name)
print("dict state", s4.closed)
