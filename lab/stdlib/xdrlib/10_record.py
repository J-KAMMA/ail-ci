import xdrlib


def pack_point(p, x, y):
    p.pack_int(x)
    p.pack_int(y)


def unpack_point(u):
    return (u.unpack_int(), u.unpack_int())


p = xdrlib.Packer()
p.pack_string(b"record")
p.pack_uint(3)
p.pack_bool(True)
p.pack_double(2.5)
p.pack_hyper(-7)
p.pack_array([(1, 2), (-3, 4)], lambda pt: pack_point(p, pt[0], pt[1]))
print(p.get_buffer().hex())

u = xdrlib.Unpacker(p.get_buffer())
print(u.unpack_string())
n = u.unpack_uint()
print(n)
print(u.unpack_bool())
print(u.unpack_double())
print(u.unpack_hyper())
print(u.unpack_array(lambda: unpack_point(u)))
print(u.get_position(), len(u.get_buffer()))
u.done()
