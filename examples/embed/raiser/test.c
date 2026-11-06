#include <stdio.h>
#include <string.h>
#include "raiser.h"

int main(void) {
    int64_t v = 0;
    int st;
    int ok = 1;

    st = raiser_checked_div(7, 2, &v);
    printf("checked_div(7, 2) = %lld\n", (long long)v);
    ok &= st == 0 && v == 3;

    st = raiser_checked_div(1, 0, &v);
    if (st == 1 && strcmp(raiser_last_error(), "ValueError: division by zero") == 0)
        printf("error: %s\n", raiser_last_error());
    else
        ok = 0;

    st = raiser_require_positive(-3, &v);
    if (st == 1 && strcmp(raiser_last_error(), "ValueError: value must be positive") == 0)
        printf("error: %s\n", raiser_last_error());
    else
        ok = 0;

    st = raiser_require_positive(5, &v);
    printf("require_positive(5) = %lld\n", (long long)v);
    ok &= st == 0 && v == 5;

    raiser_shutdown();
    return ok ? 0 : 1;
}
