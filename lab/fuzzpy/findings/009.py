# CPython: exit 1, no stdout; last stderr line: IndexError: index out of range
# AIL default: exit 1, same stdout; last stderr line: bytes index out of range
# Cause: the typed/default bytes-index trap prints "bytes index out of range" instead of "index out of range" and drops the IndexError: prefix.
b: bytes = b"a"
print(b[5])
