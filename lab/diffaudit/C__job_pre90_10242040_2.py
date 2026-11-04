# C?-job-pre90-10242040-2: a non-BMP code point reaches chr() only at run time.
def to_code(n):
    return ord(chr(n))

print(to_code(0x10000))
