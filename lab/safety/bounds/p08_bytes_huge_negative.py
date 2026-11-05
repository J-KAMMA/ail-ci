def byte_at(data: bytes, i: int) -> int:
    return data[i]


data: bytes = b"safe"
print("len", len(data), "first", data[0])
print("last", data[-1])
print("huge negative", byte_at(data, -(2 ** 62)))
