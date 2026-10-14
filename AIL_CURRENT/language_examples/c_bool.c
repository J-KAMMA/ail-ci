#include <stdbool.h>
#include <stddef.h>
#include <string.h>

bool native_contains_nul(const unsigned char *data, size_t size, bool negate) {
    bool found = size != 0 && memchr(data, 0, size) != NULL;
    return found != negate;
}
