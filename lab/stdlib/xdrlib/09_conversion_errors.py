import xdrlib

p = xdrlib.Packer()
try:
    p.pack_uint(-1)
except xdrlib.ConversionError as e:
    print(type(e).__name__, str(e))

try:
    p.pack_int(2147483648)
except xdrlib.ConversionError as e:
    print(type(e).__name__, str(e))

try:
    p.pack_uint(4294967296)
except xdrlib.ConversionError as e:
    print(type(e).__name__, str(e))

try:
    p.pack_farray(2, [1], lambda v: p.pack_uint(v))
except ValueError as e:
    print(type(e).__name__, str(e))

try:
    p.pack_fstring(-1, b"x")
except ValueError as e:
    print(type(e).__name__, str(e))

print(p.get_buffer().hex())
