# C?-job-pre101-10242138-1: itertools.permutations with a None r
import itertools


class Box:
    pass


box = Box()
box.r = None
xs = ["a", "b"]
print(list(itertools.permutations(xs, None)))
print(list(itertools.permutations(xs, r=None)))
print(list(itertools.permutations(xs)))
print(len(list(itertools.permutations(xs, None))))
r = None
print(list(itertools.permutations(xs, r)))
print(list(itertools.permutations(xs, box.r)))
d = {"r": None}
print(list(itertools.permutations(xs, d["r"])))


def perm(n):
    return list(itertools.permutations(xs, n))


print(perm(None))
print(list(itertools.permutations(xs, 1)))
