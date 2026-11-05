import imghdr

# Write a PNG in the current directory and sniff it by name.
name = "imghdr_sample.png"
data = b'\211PNG\r\n\032\n' + b'\x00' * 40
with open(name, "wb") as f:
    f.write(data)
print(imghdr.what(name))

# The same file through a "rb" handle read 32 bytes at a time.
with open(name, "rb") as f:
    print(imghdr.what(None, f.read(32)))

# And through the file object itself, which what() rewinds.
with open(name, "rb") as f:
    print(imghdr.what(f))
    print(f.tell())
