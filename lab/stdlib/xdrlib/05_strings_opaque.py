import xdrlib

p = xdrlib.Packer()
p.pack_fstring(3, b"abc")
p.pack_fstring(4, b"de")
p.pack_fopaque(5, b"\x00\x01\x02")
p.pack_string(b"hello")
p.pack_opaque(b"")
p.pack_bytes(b"xy")
print(p.get_buffer().hex())

u = xdrlib.Unpacker(p.get_buffer())
print(u.unpack_fstring(3).hex())
print(u.unpack_fstring(4).hex())
print(u.unpack_fopaque(5).hex())
print(u.unpack_string())
print(u.unpack_opaque())
print(u.unpack_bytes())
u.done()
