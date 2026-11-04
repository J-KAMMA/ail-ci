# C?-job-qtest1-10241455-2: __index__ returning None for a str search bound
class N:
    def __index__(self):
        return None

s = "abcabc"
for call in (lambda: s.startswith(("bc",), N()),
             lambda: s.find("bc", N()),
             lambda: s.count("bc", N()),
             lambda: s.index("bc", N())):
    try:
        print(repr(call()))
    except Exception as exc:
        print(type(exc).__name__, str(exc))
print(s.startswith("ab", None))
print(s.find("bc", None))
