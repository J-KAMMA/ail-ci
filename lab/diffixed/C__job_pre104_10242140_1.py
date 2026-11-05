# C?-job-pre104-10242140-1: one-argument round() of nan/inf raises catchable CPython errors
import math


class Box:
    pass


for value in (float("nan"), float("inf"), float("-inf")):
    try:
        round(value)
    except ValueError as exc:
        print("ValueError", exc)
    except OverflowError as exc:
        print("OverflowError", exc)
    else:
        print("no error", value)

box = Box()
box.v = float("inf")
try:
    round(box.v)
except OverflowError as exc:
    print("OverflowError", exc)

try:
    round(math.nan)
except ValueError as exc:
    print("ValueError", exc)

print(round(2.5), round(-2.5), round(2.675, 2))
print(round(7), round(True))
