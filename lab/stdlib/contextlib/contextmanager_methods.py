from contextlib import contextmanager


class Workspace:
    def __init__(self):
        self.log = []
        self.open = 0

    @contextmanager
    def section(self, name, swallow=False):
        self.open += 1
        self.log.append("open " + name)
        try:
            yield self
        except ValueError as e:
            self.log.append("saw " + name + " " + str(e))
            if not swallow:
                raise
        finally:
            self.open -= 1
            self.log.append("close " + name)


def nested(space):
    with space.section("outer") as outer:
        with space.section("inner"):
            print("nested", outer is space, space.open)
        print("after inner", space.open)
    print("after outer", space.open)


space = Workspace()
nested(space)
try:
    with space.section("strict"):
        raise ValueError("strict")
except ValueError as e:
    print("outer caught", e)
with space.section("gentle", swallow=True):
    raise ValueError("gentle")
print("open now", space.open)
print("log", space.log)

items = [space]
with items[0].section("list") as got:
    print("list", got is space)
print("list state", space.open)
