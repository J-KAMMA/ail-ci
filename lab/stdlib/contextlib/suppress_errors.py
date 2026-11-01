from contextlib import suppress


data = [10, 20]
for idx in [0, 5, -1]:
    with suppress(IndexError):
        print("value", data[idx])

with suppress():
    print("empty suppress")


with suppress(KeyError, ValueError):
    d = {"a": 1}
    print(d["missing"])
    int("x")
print("after missing keys")

try:
    with suppress(KeyError):
        raise ValueError("kept")
except ValueError as e:
    print("kept", e)

with suppress(TypeError):
    raise TypeError("direct")
print("direct swallowed")

class Box:
    def __init__(self):
        self.value = 3


box = Box()
try:
    with suppress(KeyError):
        print(box.value + "text")
except TypeError as e:
    print("attribute kept", type(e).__name__)

errors = {"label": "dict"}
try:
    with suppress(KeyError):
        raise ValueError(errors["label"])
except ValueError as e:
    print("dict kept", e)
