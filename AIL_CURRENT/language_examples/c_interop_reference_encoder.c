
static size_t ail_c_encode(ail_str s, unsigned char *out) {
    size_t n = 0;
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = ail_chr(s, i);
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < s.n &&
                ail_chr(s, i + 1) >= 0xDC00 && ail_chr(s, i + 1) < 0xE000) {
            c = 0x10000u + ((c - 0xD800u) << 10) + (ail_chr(s, ++i) - 0xDC00u);
        }
        if (c >= 0xD800 && c < 0xE000) c = 0xFFFDu;
        if (c < 0x80) out[n++] = (unsigned char)c;
        else if (c < 0x800) {
            out[n++] = (unsigned char)(0xC0 | (c >> 6));
            out[n++] = (unsigned char)(0x80 | (c & 63));
        } else if (c < 0x10000) {
            out[n++] = (unsigned char)(0xE0 | (c >> 12));
            out[n++] = (unsigned char)(0x80 | ((c >> 6) & 63));
            out[n++] = (unsigned char)(0x80 | (c & 63));
        } else {
            out[n++] = (unsigned char)(0xF0 | (c >> 18));
            out[n++] = (unsigned char)(0x80 | ((c >> 12) & 63));
            out[n++] = (unsigned char)(0x80 | ((c >> 6) & 63));
            out[n++] = (unsigned char)(0x80 | (c & 63));
        }
    }
    return n;
}

