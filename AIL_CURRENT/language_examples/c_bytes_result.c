/* ail_c_bytes_view is supplied by compile-c. The adapter copies the result. */
ail_c_bytes_view native_tail(const unsigned char *data, size_t size, int64_t skip) {
    if (skip < 0 || (uint64_t)skip >= size) return (ail_c_bytes_view){NULL, 0};
    return (ail_c_bytes_view){data + (size_t)skip, size - (size_t)skip};
}
