from contextlib import contextmanager


class AppError(Exception):
    pass


@contextmanager
def catch_value(label):
    try:
        yield label
    except ValueError as e:
        print("generator saw", label, e)
        return
    finally:
        print("generator finally", label)


@contextmanager
def replace_error(label):
    try:
        yield
    except KeyError:
        print("replacing", label)
        raise AppError(label)


@contextmanager
def no_value():
    yield


with catch_value("kept") as value:
    print("body", value)
    raise ValueError("kept")
print("suppressed")

try:
    with catch_value("missing"):
        raise KeyError("missing")
except KeyError as e:
    print("not suppressed", e)

try:
    with replace_error("new"):
        raise KeyError("old")
except AppError as e:
    print("replaced", e)

with no_value():
    print("no value")

empty = []
with no_value() as nothing:
    empty.append(nothing)
print("nothing", empty, len(empty))

try:
    with catch_value("stop") as value:
        raise StopIteration(value)
except StopIteration as e:
    print("stop", e)

for tag in ("loop0", "loop1"):
    with catch_value(tag) as value:
        if value == "loop1":
            break
        print("loop", value)
