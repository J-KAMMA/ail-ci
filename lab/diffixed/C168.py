# C168: None start/end bounds for str search methods
s = "hello"
lo = None
hi = None
print(s.find("l", None, None), s.find("l"))
print(s.find("l", lo, hi))
args = [None, None]
print(s.find("l", args[0], args[1]))
d = {"lo": None, "hi": None}
print(s.find("l", d["lo"], d["hi"]))

def f(a, b):
    return s.find("l", a, b)

print(f(None, None))
print(s.rfind("l", None, None), s.count("l", None, None))
print(s.startswith("he", None, None), s.endswith("lo", None, None))
print(s.index("l", None, None), s.rindex("l", None, None))
print(s.find("l", 1, None), s.find("l", None, 4))
