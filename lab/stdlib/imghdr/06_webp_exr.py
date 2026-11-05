import imghdr

# WebP is RIFF....WEBP.
webp = b'RIFF' + b'\x24\x00\x00\x00' + b'WEBP' + b'VP8 ' + b'\x00' * 16
print(imghdr.what(None, webp))

# OpenEXR.
exr = b'\x76\x2f\x31\x01' + b'\x00' * 28
print(imghdr.what(None, exr))

# A RIFF container that is not WebP matches nothing.
print(imghdr.what(None, b'RIFF' + b'\x24\x00\x00\x00' + b'WAVE' + b'\x00' * 16))
