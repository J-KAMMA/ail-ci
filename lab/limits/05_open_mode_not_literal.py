mode = "r"
with open("/dev/null", mode) as f:
    text = f.read()
print(text == "")
