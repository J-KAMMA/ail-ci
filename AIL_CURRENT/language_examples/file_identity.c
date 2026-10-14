#include <stddef.h>
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>

static wchar_t *identity_path(const unsigned char *data, size_t n) {
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                   (const char *)data, (int)n, NULL, 0);
    if (length <= 0 || (size_t)length > SIZE_MAX / sizeof(wchar_t) - 1)
        return NULL;
    wchar_t *path = (wchar_t *)malloc(((size_t)length + 1) * sizeof *path);
    if (!path) return NULL;
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)data,
                            (int)n, path, length) != length) {
        free(path);
        return NULL;
    }
    path[length] = L'\0';
    return path;
}
#else
#include <errno.h>
#include <sys/stat.h>

static char *identity_path(const unsigned char *data, size_t n) {
    if (n == SIZE_MAX) return NULL;
    char *path = (char *)malloc(n + 1);
    if (!path) return NULL;
    memcpy(path, data, n);
    path[n] = '\0';
    return path;
}
#endif

int64_t native_file_identity_status(const unsigned char *input, size_t input_n,
                                  const unsigned char *output, size_t output_n) {
    if (!input || !output || !input_n || !output_n ||
            input_n > INT_MAX || output_n > INT_MAX ||
            memchr(input, 0, input_n) || memchr(output, 0, output_n))
        return -1;
#ifdef _WIN32
    wchar_t *input_path = identity_path(input, input_n);
    wchar_t *output_path = identity_path(output, output_n);
#else
    char *input_path = identity_path(input, input_n);
    char *output_path = identity_path(output, output_n);
#endif
    if (!input_path || !output_path) {
        free(input_path);
        free(output_path);
        return -1;
    }
    int64_t status = -1;
#ifdef _WIN32
    HANDLE input_file = CreateFileW(input_path, FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (input_file != INVALID_HANDLE_VALUE) {
        BY_HANDLE_FILE_INFORMATION input_info, output_info;
        if (GetFileInformationByHandle(input_file, &input_info)) {
            HANDLE output_file = CreateFileW(output_path, FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
            if (output_file == INVALID_HANDLE_VALUE) {
                DWORD error = GetLastError();
                if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND)
                    status = 0;
            } else {
                if (GetFileInformationByHandle(output_file, &output_info))
                    status = input_info.dwVolumeSerialNumber == output_info.dwVolumeSerialNumber &&
                             input_info.nFileIndexHigh == output_info.nFileIndexHigh &&
                             input_info.nFileIndexLow == output_info.nFileIndexLow;
                CloseHandle(output_file);
            }
        }
        CloseHandle(input_file);
    }
#else
    struct stat input_info, output_info;
    if (stat(input_path, &input_info) == 0) {
        if (stat(output_path, &output_info) == 0)
            status = input_info.st_dev == output_info.st_dev &&
                     input_info.st_ino == output_info.st_ino;
        /* Like Windows ERROR_PATH_NOT_FOUND, a parent file means no output object. */
        else if (errno == ENOENT || errno == ENOTDIR)
            status = 0;
    }
#endif
    free(input_path);
    free(output_path);
    return status;
}
