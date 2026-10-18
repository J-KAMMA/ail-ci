/* G5a: the few zlib calls that need a z_stream, as plain functions (see zlib.py). A call leaves its result
   (or its CPython-worded error message) inside the glue; zglue_size/zglue_take/zglue_errmsg read it. */
#include <stddef.h>

int zglue_deflate(int level, int wbits, const unsigned char *src, size_t n);
int zglue_inflate(int wbits, const unsigned char *src, size_t n, size_t bufsize);
size_t zglue_size(void);
int zglue_take(unsigned char *dst, size_t n);
const char *zglue_errmsg(void);
