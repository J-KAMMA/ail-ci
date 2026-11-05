import os
import stat

def kind(name: str) -> None:
    st = os.stat(name)
    print(name, stat.S_ISREG(st.st_mode), stat.S_ISDIR(st.st_mode), stat.S_ISLNK(st.st_mode))

kind("data/a.txt")
kind("data/sub")
kind("data/link.txt")
