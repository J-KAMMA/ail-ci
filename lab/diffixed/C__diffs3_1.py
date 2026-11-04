# C?-diffs3-1: __len__ results and a truth test that raises
import sys

class Neg:
    def __len__(self):
        return -1

class Flt:
    def __len__(self):
        return 2.5

class Max:
    def __len__(self):
        return sys.maxsize

class Boom:
    def __bool__(self):
        raise RuntimeError("boom")

class LBoom:
    def __len__(self):
        raise RuntimeError("len boom")

for cls in (Neg, Flt, Boom, LBoom):
    obj = cls()
    try:
        if obj:
            print("true")
    except Exception as exc:
        print(type(exc).__name__, str(exc))
for cls in (Neg, Flt):
    obj = cls()
    try:
        print(len(obj))
    except Exception as exc:
        print(type(exc).__name__, str(exc))
print(len(Max()) == sys.maxsize)
