import os
import os.path

print(os.path.normcase("AbC/DeF") == "AbC/DeF")
print(os.path.normcase("") == "")
a = "data/a.txt"
print(os.path.getmtime(a) == os.stat(a).st_mtime)
print(os.path.getatime(a) == os.stat(a).st_atime)
print(os.path.getctime(a) == os.stat(a).st_ctime)
print(os.path.getsize(a) == os.stat(a).st_size)
