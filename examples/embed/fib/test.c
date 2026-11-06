#include <stdio.h>
#include <string.h>
#include "fib.h"

static int check(int condition, const char *what) {
    if (!condition) {
        fprintf(stderr, "fib example: %s failed\n", what);
        return 0;
    }
    return 1;
}

int main(void) {
    int64_t v = 0;
    int st;
    int ok = 1;

    st = fib_fib(0, &v);
    printf("fib(0) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 0, "fib(0)");

    st = fib_fib(1, &v);
    printf("fib(1) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 1, "fib(1)");

    st = fib_fib(10, &v);
    printf("fib(10) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 55, "fib(10)");

    st = fib_fib(92, &v);
    printf("fib(92) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 7540113804746346429LL, "fib(92)");

    st = fib_gcd(48, 18, &v);
    printf("gcd(48, 18) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 6, "gcd(48, 18)");

    st = fib_gcd(-48, 18, &v);
    printf("gcd(-48, 18) = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 6, "gcd(-48, 18)");

    st = fib_sum_line("a12 b34 c5", strlen("a12 b34 c5"), &v);
    printf("sum_line(\"a12 b34 c5\") = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 51, "sum_line digits");

    st = fib_sum_line("no digits", strlen("no digits"), &v);
    printf("sum_line(\"no digits\") = %lld\n", (long long)v);
    ok &= check(st == 0 && v == 0, "sum_line empty");

    st = fib_fib(93, &v);
    ok &= check(st == 1 && strncmp(fib_last_error(), "OverflowError: ", 15) == 0,
                "fib(93) overflow is status 1 with OverflowError");

    fib_shutdown();
    return ok ? 0 : 1;
}
