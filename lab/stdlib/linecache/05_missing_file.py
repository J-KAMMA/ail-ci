import os
import linecache

here = os.path.dirname(__file__)

missing = os.path.join(here, "data", "no-such-file.txt")
print(repr(linecache.getline(missing, 1)))
print(linecache.getlines(missing))
print("cached", missing in linecache.cache)
print(repr(linecache.getline("<string>", 1)))
print(repr(linecache.getline("", 1)))
print(repr(linecache.getline(os.path.join(here, "data"), 1)))
