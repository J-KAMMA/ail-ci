import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "lines.txt")

first = linecache.getline(path, 1)
print(repr(first))
print(len(first), first.strip())
print(repr(linecache.getline(path, 1)))
