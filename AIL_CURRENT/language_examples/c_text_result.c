/* Borrow the value after the first '='; preserve UTF-8 bytes and embedded NUL. */
ail_c_utf8_view native_value(const unsigned char *data, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        if (data[i] == '=') return (ail_c_utf8_view){data + i + 1, size - i - 1};
    }
    return (ail_c_utf8_view){NULL, 0};
}
