import os

def show(name: str) -> None:
    st = os.stat(name)
    print(name, st.st_size)

show("data/a.txt")
show("data/b.bin")
show("data/empty.txt")
show("data/sub")
show("data/sub/inner.txt")
