# C?-diffs3-2: b += b on a bytearray
b = bytearray(b"ab")
try:
    b += b
    print(b)
except Exception as exc:
    print(type(exc).__name__, str(exc))
b = bytearray(b"ab")
b.extend(b)
print(b)
b = bytearray(b"ab")
b[len(b):] = b
print(b)
b = bytearray(b"ab")
b[0:0] = b
print(b)
b = bytearray(b"ab")
try:
    b += b
except Exception as exc:
    print(type(exc).__name__, str(exc))
print(b)
