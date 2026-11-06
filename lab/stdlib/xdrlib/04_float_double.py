import xdrlib

p = xdrlib.Packer()
p.pack_float(1.5)
p.pack_float(-2.25)
p.pack_float(0.0)
p.pack_float(0.1)
print(p.get_buffer().hex())

p = xdrlib.Packer()
p.pack_double(1.5)
p.pack_double(-2.25)
p.pack_double(0.1)
p.pack_double(1e300)
print(p.get_buffer().hex())

u = xdrlib.Unpacker(bytes.fromhex("3fc00000c0100000000000003dcccccd"))
print(u.unpack_float())
print(u.unpack_float())
print(u.unpack_float())
print(u.unpack_float())
u.done()

u = xdrlib.Unpacker(bytes.fromhex("3ff8000000000000c002000000000000"
                                   "3fb999999999999a7e37e43c8800759c"))
print(u.unpack_double())
print(u.unpack_double())
print(u.unpack_double())
print(u.unpack_double())
u.done()
