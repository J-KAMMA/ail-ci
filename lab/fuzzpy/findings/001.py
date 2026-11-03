# CPython: exit 1, no stdout; last stderr line: IndexError: string index out of range
# AIL default: exit 1, same stdout; last stderr line: string index out of range
# Cause: an uncaught trap on the typed/default path prints only the message text, without the exception class prefix.
x: str = "a"
print(x[3])
