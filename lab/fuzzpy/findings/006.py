# CPython: exit 1, no stdout; last stderr line: ZeroDivisionError: integer division or modulo by zero
# AIL default: exit 1, same stdout; last stderr line: integer division by zero
# Cause: the typed/default floor-division trap drops the ZeroDivisionError: prefix and the words "or modulo".
a: int = 1
b: int = 0
print(a // b)
