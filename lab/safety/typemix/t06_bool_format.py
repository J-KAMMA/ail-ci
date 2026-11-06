def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("yes")
print("literal", f"{True:d}")
print("false", f"{False:d}")
print("pad", f"{True:05d}")
print("text", f"{flag:d}")
print("format", format(True, "d"))
