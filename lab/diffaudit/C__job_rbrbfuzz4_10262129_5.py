# C?-job-rbrbfuzz4-10262129-5: reversed(d) and d1 | d2 (dict operators).
d = {1: "a", 2: "b"}
r = reversed(d)
print(type(r).__name__)
print(next(r))
d1 = {1: "a"}
d2 = {2: "b"}
print(d1 | d2)
