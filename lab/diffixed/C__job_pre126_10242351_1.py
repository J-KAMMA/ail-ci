# C?-job-pre126-10242351-1: itertools r argument is checked
import itertools

for bad in (-1, 1.5, "2", [2], (2,), b"2"):
    try:
        print(list(itertools.permutations([1, 2], bad)))
    except Exception as exc:
        print(type(exc).__name__, str(exc))
print(list(itertools.permutations([1, 2], None)))
print(list(itertools.combinations([1, 2, 3], 2)))
print(list(itertools.permutations([1, 2], 1)))
