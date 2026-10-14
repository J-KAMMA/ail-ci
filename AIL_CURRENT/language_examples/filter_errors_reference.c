/* Straightforward byte-stream comparator for valid BMP UTF-8 input. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static int emit_line(const char *line, size_t len, uint64_t *count) {
    if (len >= 4 && memcmp(line, "ERR:", 4) == 0) {
        if (*count == UINT64_MAX || fwrite(line, 1, len, stdout) != len)
            return -1;
        ++*count;
    }
    return 0;
}

int main(void) {
    char *line = NULL;
    size_t len = 0, cap = 0;
    uint64_t count = 0;
    int ch, rc = 0;
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 ||
        _setmode(_fileno(stdout), _O_TEXT) == -1)
        return 2;
#endif
    while ((ch = fgetc(stdin)) != EOF) {
#ifdef _WIN32
        if (ch == '\r') {
            int next = fgetc(stdin);
            if (next != '\n' && next != EOF && ungetc(next, stdin) == EOF) {
                rc = 2;
                goto done;
            }
            ch = '\n';
        }
#endif
        if (len == cap) {
            if (cap > SIZE_MAX / 2) {
                rc = 2;
                goto done;
            }
            size_t next = cap ? cap * 2 : 256;
            char *grown = realloc(line, next);
            if (!grown) {
                rc = 2;
                goto done;
            }
            line = grown;
            cap = next;
        }
        line[len++] = (char)ch;
        if (ch == '\n') {
            if (emit_line(line, len, &count) < 0) {
                rc = 2;
                goto done;
            }
            len = 0;
        }
    }
    if (ferror(stdin) || (len && emit_line(line, len, &count) < 0) ||
        printf("%" PRIu64 "\n", count) < 0)
        rc = 2;
done:
    free(line);
    return rc;
}
