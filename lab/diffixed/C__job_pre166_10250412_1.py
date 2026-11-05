# C?-job-pre166-10250412-1: next() of a generator expression and of non-iterators
g = (x * 2 for x in [1, 2, 3])
print(next(g), next(g))
print(list(g))
h = (x for x in [4, 5, 6])
print(next(h), 5 in h, list(h))
k = (x for x in [7, 8])
for value, present in [(9, 9), (8, 8)]:
    print(value, value in k)
print(list(k))
for bad in ([1, 2], "abc", 3):
    try:
        next(bad)
    except Exception as exc:
        print(type(exc).__name__, str(exc))
