# CPython: exit 1, no stdout; last stderr line: ValueError: substring not found
# AIL default: exit 1, same stdout; last stderr line: ValueError
# Cause: the typed/default str.index trap prints only the class name, with no message text.
s: str = "abc"
print(s.index("z"))
