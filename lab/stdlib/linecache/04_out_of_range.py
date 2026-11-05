import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "lines.txt")

for lineno in (0, -1, -100, 6, 1000):
    line = linecache.getline(path, lineno)
    print(lineno, repr(line), len(line))
print("cached", path in linecache.cache)
