import os
import linecache

here = os.path.dirname(__file__)
lines_path = os.path.join(here, "data", "lines.txt")
utf8_path = os.path.join(here, "data", "utf8.txt")

a = linecache.getlines(lines_path)
b = linecache.getlines(lines_path)
print(repr(a))
print(len(a), a == b)
print(repr(linecache.getline(utf8_path, 2)))
print(len(linecache.cache))
