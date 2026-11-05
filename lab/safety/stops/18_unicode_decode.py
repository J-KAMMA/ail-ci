def decode(data: bytes) -> str:
    return data.decode("utf-8")


print("prefix", decode(b"hello"))
print("accent", decode("café".encode("utf-8")))
print("next", decode(b"\xff"))
