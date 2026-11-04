# CPython: exit 1, no stdout; last stderr line: IndexError: string index out of range
# AIL default: exit 1, same stdout; last stderr line: string index out of range
# Cause: the typed/default string-index trap prints only the message text, without the IndexError: prefix
# (ValueError and TypeError keep theirs). An out-of-range list index looks the same, minus the prefix.
x: str = "a"
print(x[3])
