import imghdr

print(len(imghdr.tests))

# The test functions, in the order `what` runs them.  This compiler cannot read
# `function.__name__` and function identity is not stable, so recognize each test
# by the byte signature it accepts; the labels are CPython's function names.
samples = [
    (b'\xff\xd8\xff\xe0\x00\x10JFIF\x00', "test_jpeg"),
    (b'\211PNG\r\n\032\n', "test_png"),
    (b'GIF89a', "test_gif"),
    (b'MM\x00\x2a', "test_tiff"),
    (b'\001\332', "test_rgb"),
    (b'P1\n', "test_pbm"),
    (b'P2\n', "test_pgm"),
    (b'P3\n', "test_ppm"),
    (b'\x59\xa6\x6a\x95', "test_rast"),
    (b'#define x', "test_xbm"),
    (b'BM', "test_bmp"),
    (b'RIFF0000WEBP', "test_webp"),
    (b'\x76\x2f\x31\x01', "test_exr"),
]
names = []
for tf in imghdr.tests:
    for h, label in samples:
        if tf(h, None):
            names.append(label)
            break
print(names)
