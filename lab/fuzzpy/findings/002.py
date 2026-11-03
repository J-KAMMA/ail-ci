# CPython: exit 1, no stdout; last stderr line: IndexError: pop from empty list
# AIL default: exit 1, same stdout; last stderr line: pop from empty list
# Cause: the typed/default pop trap prints only its text, without the IndexError: prefix.
xs: list[int] = []
print(xs.pop())
