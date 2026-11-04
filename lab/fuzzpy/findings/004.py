# CPython: exit 1, no stdout; last stderr line: ZeroDivisionError: integer modulo by zero
# AIL default: exit 1, same stdout; last stderr line: integer modulo by zero
# Cause: the typed/default integer-modulo trap prints only its text, without the ZeroDivisionError: prefix.
# Reproduced from a local, an argument and a list item.
a: int = 1
b: int = 0
print(a % b)
