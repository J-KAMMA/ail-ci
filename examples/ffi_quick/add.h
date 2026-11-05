#ifndef AIL_QUICK_ADD_H
#define AIL_QUICK_ADD_H

#include <stddef.h>
#include <stdint.h>

int64_t ail_quick_add(int64_t a, int64_t b);
int32_t ail_quick_add32(int32_t a, int32_t b);
double ail_quick_average(double a, double b);
size_t ail_quick_strlen(const char *text);
void ail_quick_reverse(const unsigned char *src, size_t n, unsigned char *dst);
int64_t ail_quick_parse(const char *text);

#endif
