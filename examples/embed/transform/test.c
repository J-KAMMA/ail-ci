#include <stdio.h>
#include <string.h>
#include "transform.h"

static int show(const char *value) {
    char out[64];
    size_t len = 0;
    int st = transform_transform(value, strlen(value), out, sizeof out, &len);
    if (st != 0) {
        fprintf(stderr, "transform example: status %d for %s: %s\n", st, value, transform_last_error());
        return 0;
    }
    printf("transform(\"%s\") = \"%.*s\"\n", value, (int)len, out);
    return 1;
}

int main(void) {
    char small[4];
    size_t len = 0;
    int ok = 1;
    int st;

    ok &= show("Hello World 42");
    ok &= show("ail embed");
    ok &= show("");
    ok &= show("already UPPER");
    ok &= show("héllo wörld");

    st = transform_transform("Hello World 42", strlen("Hello World 42"), small, sizeof small, &len);
    if (!(st == 2 && len == 14)) {
        fprintf(stderr, "transform example: buffer-too-small status %d len %zu\n", st, len);
        ok = 0;
    }

    transform_shutdown();
    return ok ? 0 : 1;
}
