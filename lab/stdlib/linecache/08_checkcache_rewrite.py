import os
import linecache

path = "checkcache_rewrite.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write("alpha\nbeta\n")
print(repr(linecache.getline(path, 2)))
print(len(linecache.getlines(path)))

with open(path, "w", encoding="utf-8") as f:
    f.write("alpha\ngamma\ndelta\n")

linecache.checkcache(path)
print(repr(linecache.getline(path, 2)))
print(len(linecache.getlines(path)))

linecache.checkcache()
print(repr(linecache.getline(path, 3)))

os.remove(path)
linecache.checkcache(path)
print("cached", path in linecache.cache)
print(repr(linecache.getline(path, 1)))
