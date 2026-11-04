# CPython: exit 1, no stdout; last stderr line: KeyError: 'a'
# AIL default: exit 1, same stdout; last stderr line: key error
# Cause: the typed/default missing-key trap emits the generic text "key error" instead of CPython's key repr,
# and no KeyError: prefix. Only a local dict differs; a dict passed as a parameter matches CPython.
d: dict[str, int] = {}
print(d['a'])
