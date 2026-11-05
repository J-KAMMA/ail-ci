import os

names = []
kinds = []
for entry in os.scandir("data"):
    names.append(entry.name)
    if entry.is_dir():
        kinds.append(entry.name + ":dir")
    elif entry.is_symlink():
        kinds.append(entry.name + ":link")
    else:
        kinds.append(entry.name + ":file")
print(sorted(names))
print(sorted(kinds))
for entry in os.scandir("data/sub"):
    print(entry.name, entry.path, entry.is_file())
