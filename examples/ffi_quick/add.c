#include "add.h"

#include <errno.h>

int64_t ail_quick_add(int64_t a, int64_t b)
{
    return a + b;
}

int32_t ail_quick_add32(int32_t a, int32_t b)
{
    return a + b;
}

double ail_quick_average(double a, double b)
{
    return (a + b) / 2.0;
}

size_t ail_quick_strlen(const char *text)
{
    size_t n = 0;
    while (text[n] != '\0')
        n++;
    return n;
}

void ail_quick_reverse(const unsigned char *src, size_t n, unsigned char *dst)
{
    size_t i;
    for (i = 0; i < n; i++)
        dst[i] = src[n - 1 - i];
}

int64_t ail_quick_parse(const char *text)
{
    int64_t value = 0;
    size_t i;

    if (text[0] == '\0') {
        errno = EINVAL;
        return -1;
    }
    for (i = 0; text[i] != '\0'; i++) {
        if (text[i] < '0' || text[i] > '9') {
            errno = EINVAL;
            return -1;
        }
        value = value * 10 + (text[i] - '0');
    }
    return value;
}
