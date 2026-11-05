path = "data.txt"
with open(path, "w", encoding="utf-16") as f:
    f.write("hi")
with open(path, "r", encoding="utf-16") as f:
    print(f.read())
