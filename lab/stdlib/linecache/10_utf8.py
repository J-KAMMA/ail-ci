import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "utf8.txt")

for lineno in (1, 2, 3, 4):
    line = linecache.getline(path, lineno)
    print(lineno, repr(line), len(line))
print(repr(linecache.getlines(path)))
