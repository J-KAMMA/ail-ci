import xdrlib

u = xdrlib.Unpacker(bytes.fromhex("0000000100000002"))
print(u.unpack_uint())
try:
    u.done()
except xdrlib.Error as e:
    print(type(e).__name__, str(e))
    print(repr(e))
print(u.get_position())

u = xdrlib.Unpacker(bytes.fromhex("0000000100"))
print(u.unpack_uint())
try:
    u.unpack_uint()
except EOFError as e:
    print(type(e).__name__, str(e))

u = xdrlib.Unpacker(b"")
try:
    u.unpack_double()
except EOFError as e:
    print(type(e).__name__, str(e))
