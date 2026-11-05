import os

rows = []
with os.scandir("data") as it:
    for entry in it:
        st = entry.stat()
        rows.append(entry.name + ":" + str(st.st_size) + ":" + str(st.st_mode))
print(sorted(rows))
print(len(rows))
