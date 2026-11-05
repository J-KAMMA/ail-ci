import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "nonl.txt")

print(repr(linecache.getline(path, 1)))
print(repr(linecache.getline(path, 2)))
lines = linecache.getlines(path)
print(repr(lines))
print(len(lines), len(lines[0]))
