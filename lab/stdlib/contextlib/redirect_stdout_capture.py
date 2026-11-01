import io
from contextlib import redirect_stdout


def noisy(label):
    print("start", label)
    print("value", label.upper())
    return label


buffer = io.StringIO()
with redirect_stdout(buffer):
    noisy("one")
    print("two", 2)
captured = buffer.getvalue()
print("captured lines", len(captured.splitlines()))
print(captured, end="")

outer = io.StringIO()
inner = io.StringIO()
with redirect_stdout(outer):
    print("outer before")
    with redirect_stdout(inner):
        print("inner only")
    print("outer after")
print("outer", outer.getvalue().splitlines())
print("inner", inner.getvalue().splitlines())

try:
    with redirect_stdout(io.StringIO()) as target:
        print("error body")
        raise ValueError("after capture")
except ValueError as e:
    print("error", e)
    print("target is stream", target is not None)
