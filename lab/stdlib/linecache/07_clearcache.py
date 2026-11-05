import os
import linecache

here = os.path.dirname(__file__)
lines_path = os.path.join(here, "data", "lines.txt")
utf8_path = os.path.join(here, "data", "utf8.txt")

linecache.getline(lines_path, 1)
linecache.getline(utf8_path, 1)
print(len(linecache.cache))
linecache.clearcache()
print(len(linecache.cache))
print("cached", lines_path in linecache.cache)
print(repr(linecache.getline(lines_path, 5)))
print(len(linecache.cache))
