# C?-job-rbfuzz42-10240914-1: abs() of a bool returns an int
print(abs(False), abs(True))
print(type(abs(True)).__name__, type(abs(False)).__name__)
print(sorted([True, False], key=abs))
print(list(map(abs, [True, False, -3])))
print(abs(-7), abs(-7.5))
print(abs(False) + 1)
