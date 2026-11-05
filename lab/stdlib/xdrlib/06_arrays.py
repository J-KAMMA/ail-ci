import xdrlib

p = xdrlib.Packer()
p.pack_list([2, -3, 4], lambda v: p.pack_int(v))
p.pack_array([10, 20], lambda v: p.pack_uint(v))
p.pack_farray(3, [b"a", b"bc", b""], lambda v: p.pack_string(v))
print(p.get_buffer().hex())

u = xdrlib.Unpacker(p.get_buffer())
print(u.unpack_list(lambda: u.unpack_int()))
print(u.unpack_array(lambda: u.unpack_uint()))
print(u.unpack_farray(3, lambda: u.unpack_string()))
u.done()
print(u.get_position())
