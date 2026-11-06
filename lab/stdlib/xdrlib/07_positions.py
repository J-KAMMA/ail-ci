import xdrlib

p = xdrlib.Packer()
p.pack_uint(1)
p.pack_uint(2)
print(p.get_buffer().hex())
print(p.get_buf().hex())

p.reset()
p.pack_uint(9)
print(p.get_buffer().hex())

u = xdrlib.Unpacker(p.get_buffer())
print(u.get_position(), u.get_buffer().hex())
print(u.unpack_uint())
print(u.get_position())
u.set_position(0)
print(u.get_position())
print(u.unpack_uint())
u.done()
print(u.get_position())
