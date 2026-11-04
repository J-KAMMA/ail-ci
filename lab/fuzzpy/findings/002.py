# CPython: exit 1, no stdout; last stderr line: IndexError: pop from empty list
# AIL default: exit 1, same stdout; last stderr line: pop from empty list
# Cause: the typed/default pop-on-a-local-list trap prints only its text, without the IndexError: prefix;
# passing the list in as a parameter matches CPython.
xs: list[int] = []
print(xs.pop())
