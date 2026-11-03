# CPython: exit 1, no stdout; last stderr line: ZeroDivisionError: float division by zero
# AIL default: exit 1, same stdout; last stderr line: division by zero
# Cause: the typed/default float-division trap drops both the ZeroDivisionError: prefix and the word "float".
x: float = 1.0
y: float = 0.0
print(x / y)
