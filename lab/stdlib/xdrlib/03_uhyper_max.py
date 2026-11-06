import xdrlib

p = xdrlib.Packer()
p.pack_uhyper(9223372036854775807)
print(p.get_buffer().hex())

u = xdrlib.Unpacker(p.get_buffer())
print(u.unpack_uhyper())
u.done()

u = xdrlib.Unpacker(bytes.fromhex("ffffffffffffffff"))
print(u.unpack_uhyper())
u.done()
