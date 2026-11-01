import io
import sys
from contextlib import redirect_stderr


def warn(label):
    print("warning", label, file=sys.stderr)
    print("still", label)


buffer = io.StringIO()
with redirect_stderr(buffer):
    warn("first")
    sys.stderr.write("direct write\n")
print("stderr lines", len(buffer.getvalue().splitlines()))
print(buffer.getvalue(), end="")

try:
    with redirect_stderr(io.StringIO()) as target:
        print("before", file=sys.stderr)
        raise RuntimeError("kept")
except RuntimeError as e:
    print("caught", e)
    print("has stream", target is not None)
