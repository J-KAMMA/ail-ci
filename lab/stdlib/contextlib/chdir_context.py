import os
from contextlib import chdir


base = os.getcwd()
folder = "ctx_chdir_work"
if not os.path.exists(folder):
    os.makedirs(folder)

try:
    with chdir(folder) as result:
        inside = os.getcwd()
        print("inside", os.path.basename(inside) == folder, result)
        with open("note.txt", "w") as handle:
            handle.write("hello from chdir\n")
        with open("note.txt") as handle:
            print("read", handle.read().strip())
    print("outside", os.getcwd() == base)

    try:
        with chdir("ctx_missing_folder"):
            print("unreachable")
    except FileNotFoundError:
        print("missing caught")
    print("still", os.getcwd() == base)

    with chdir(folder):
        with chdir(".."):
            print("twice", os.getcwd() == base)
            with chdir(folder):
                print("back", os.getcwd() == inside)
        print("middle", os.getcwd() == base)
    print("end", os.getcwd() == base)
finally:
    note = os.path.join(folder, "note.txt")
    if os.path.exists(note):
        os.remove(note)
    if os.path.exists(folder):
        os.rmdir(folder)
