# C?-job-fuzz43-10231200-1: non-str members of a startswith/endswith tuple
try:
    print("abc".startswith((b"a",)))
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    print("abc".endswith((1,)))
except Exception as exc:
    print(type(exc).__name__, str(exc))

class C:
    pass

try:
    print("abc".startswith((C(),)))
except Exception as exc:
    print(type(exc).__name__, str(exc))
print("abc".startswith(("a", b"b")))
print("abc".startswith(("x", "a")))
print("abc".endswith(("x", "c")))
