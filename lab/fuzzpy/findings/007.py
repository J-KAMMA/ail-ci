# CPython: exit 1, no stdout; last stderr line: ValueError: min() iterable argument is empty
# AIL default: exit 1, same stdout; last stderr line: min() of an empty sequence
# Cause: min()/max() over an empty list parameter raise a differently worded trap with no ValueError: prefix; a local list or a literal [] matches CPython.
def small(xs: list[int]) -> int:
    return min(xs)
print(small([]))
