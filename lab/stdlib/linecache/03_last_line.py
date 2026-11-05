import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "lines.txt")

lines = linecache.getlines(path)
last = len(lines)
print(repr(linecache.getline(path, last)))
print(repr(linecache.getline(path, last - 1)))
print(last, repr(lines[last - 1]))
