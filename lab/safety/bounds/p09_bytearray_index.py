def middle(buf: bytearray) -> int:
    return buf[1]


buf: bytearray = bytearray(b"xyz")
buf.append(33)
print("buf", buf, "len", len(buf))
print("middle", middle(buf))
print("past", buf[len(buf)])
