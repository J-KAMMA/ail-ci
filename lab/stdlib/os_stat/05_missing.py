import os

def probe(name: str) -> None:
    try:
        st = os.stat(name)
        print("built", st.st_size)
    except FileNotFoundError as e:
        print("missing:", e)

probe("data/nope.txt")
probe("data/a.txt")
try:
    os.lstat("data/nope.txt")
except FileNotFoundError as e:
    print("lstat:", e)
