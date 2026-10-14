/* Result byte 0 is status: 0 success, 1 invalid arguments, 2 I/O, 3 allocation.
 * The AIL adapter copies this per-thread borrowed result before the next call. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/types.h>
#endif

ail_c_bytes_view native_binary_range(const unsigned char *path, size_t size,
                                   int64_t offset, int64_t count) {
    static _Thread_local unsigned char output[65537];
    output[0] = 1;
    if (!path || !size || size >= INT_MAX || memchr(path, 0, size) ||
        offset < 0 || count < 0 || count > 65536)
        return (ail_c_bytes_view){output, 1};
    char *name = malloc(size + 1);
    if (!name) { output[0] = 3; return (ail_c_bytes_view){output, 1}; }
    memcpy(name, path, size); name[size] = 0;
    FILE *stream = NULL;
#ifdef _WIN32
    int units = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, NULL, 0);
    wchar_t *wide = units > 0 && (size_t)units <= SIZE_MAX / sizeof(wchar_t)
        ? malloc((size_t)units * sizeof(wchar_t)) : NULL;
    if (units > 0 && !wide) {
        free(name); output[0] = 3; return (ail_c_bytes_view){output, 1};
    }
    if (wide && MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, wide, units))
        stream = _wfopen(wide, L"rb");
    free(wide);
#else
    stream = fopen(name, "rb");
#endif
    free(name);
    output[0] = 2;
    if (!stream) return (ail_c_bytes_view){output, 1};
#ifdef _WIN32
    int failed = _fseeki64(stream, offset, SEEK_SET);
#else
    off_t position = (off_t)offset;
    int failed = (int64_t)position != offset || fseeko(stream, position, SEEK_SET);
#endif
    size_t read = failed ? 0 : fread(output + 1, 1, (size_t)count, stream);
    failed = failed || ferror(stream);
    if (fclose(stream)) failed = 1;
    if (failed) return (ail_c_bytes_view){output, 1};
    output[0] = 0;
    return (ail_c_bytes_view){output, read + 1};
}
