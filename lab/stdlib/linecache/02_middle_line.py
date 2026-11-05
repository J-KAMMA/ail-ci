import os
import linecache

here = os.path.dirname(__file__)
path = os.path.join(here, "data", "lines.txt")

for lineno in (2, 3, 4):
    line = linecache.getline(path, lineno)
    print(lineno, repr(line), line.strip().upper())
