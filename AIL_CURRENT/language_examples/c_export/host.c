/* A C host for libgeometry (built from geometry.py by `ail build --lib geometry`).
 *
 *   cc host.c -I outdir outdir/libgeometry.a -lm -lpthread -o host        (static)
 *   cc host.c -I outdir -L outdir -lgeometry -Wl,-rpath,outdir -o host    (shared)
 *
 * It prints one line per call in the format test_ail_c_export.py produces on CPython, so the two
 * outputs can be compared byte for byte. Run under AddressSanitizer, every result that is not released
 * with geometry_free() is reported as a leak.
 */
#include <inttypes.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "geometry.h"

static void error_line(const char *call, int status) {
    const char *text = geometry_last_error();
    const char *colon = strchr(text, ':');
    if (status == GEOMETRY_ERR_VALUE) printf("%s = !%s\n", call, text);       /* kind and message */
    else printf("%s = !%.*s\n", call, (int)(colon ? colon - text : strlen(text)), text);   /* kind only */
}

/* Each macro makes the call first (C leaves the order of function arguments unspecified), then prints.
 * The call refers to the result as v_ (and the length of a buffer as n_). */
#define INT_LINE(label, call) do { int64_t v_ = 0; int st_ = (call); \
    if (st_) error_line(label, st_); else printf("%s = %" PRId64 "\n", label, v_); } while (0)
#define FLOAT_LINE(label, call) do { double v_ = 0; int st_ = (call); \
    if (st_) error_line(label, st_); else printf("%s = %.6g\n", label, v_); } while (0)
#define BOOL_LINE(label, call) do { bool v_ = false; int st_ = (call); \
    if (st_) error_line(label, st_); else printf("%s = %s\n", label, v_ ? "true" : "false"); } while (0)
#define STR_LINE(label, call) do { char *v_ = NULL; int st_ = (call); \
    if (st_) error_line(label, st_); else { printf("%s = %s\n", label, v_); geometry_free(v_); } } while (0)
#define BYTES_LINE(label, call) do { uint8_t *v_ = NULL; size_t n_ = 0; int st_ = (call); \
    if (st_) error_line(label, st_); \
    else { printf("%s = ", label); for (size_t k_ = 0; k_ < n_; k_++) printf("%02x", v_[k_]); \
           printf("\n"); geometry_free(v_); } } while (0)
#define INTS_LINE(label, call) do { int64_t *v_ = NULL; size_t n_ = 0; int st_ = (call); \
    if (st_) error_line(label, st_); \
    else { printf("%s =", label); for (size_t k_ = 0; k_ < n_; k_++) printf(" %" PRId64, v_[k_]); \
           printf("\n"); geometry_free(v_); } } while (0)
#define FLOATS_LINE(label, call) do { double *v_ = NULL; size_t n_ = 0; int st_ = (call); \
    if (st_) error_line(label, st_); \
    else { printf("%s =", label); for (size_t k_ = 0; k_ < n_; k_++) printf(" %.6g", v_[k_]); \
           printf("\n"); geometry_free(v_); } } while (0)

static void *worker(void *arg) {
    long failures = 0;
    for (int i = 0; i < 300; i++) {
        int64_t one[3] = {i, i + 1, i + 2}, *squares = NULL;
        size_t n = 0;
        if (geometry_squares(one, 3, &squares, &n) || n != 3 || squares[2] != (int64_t)(i + 2) * (i + 2)) failures++;
        geometry_free(squares);
        int64_t quotient = 0;
        if (geometry_divide(i, 0, &quotient) != GEOMETRY_ERR_ZERO_DIVISION ||
            strncmp(geometry_last_error(), "ZeroDivisionError", 17) != 0) failures++;    /* this thread's own error */
        char *text = NULL;
        if (geometry_shout("thread", &text) || strcmp(text, "THREAD!") != 0) failures++;
        geometry_free(text);
    }
    *(long *)arg = failures;
    return NULL;
}

int main(void) {
    INT_LINE("add(2, 3)", geometry_add(2, 3, &v_));
    INT_LINE("add(-7, 4)", geometry_add(-7, 4, &v_));
    FLOAT_LINE("scaled(1.5)", geometry_scaled(1.5, &v_));
    INT_LINE("divide(7, 2)", geometry_divide(7, 2, &v_));
    INT_LINE("divide(-7, 2)", geometry_divide(-7, 2, &v_));
    INT_LINE("divide(7, 0)", geometry_divide(7, 0, &v_));
    INT_LINE("parse_digit('7')", geometry_parse_digit("7", &v_));
    INT_LINE("parse_digit('x')", geometry_parse_digit("x", &v_));
    INT_LINE("parse_digit('')", geometry_parse_digit("", &v_));
    BOOL_LINE("negate(True)", geometry_negate(true, &v_));
    BOOL_LINE("negate(False)", geometry_negate(false, &v_));
    STR_LINE("shout('h\xc3\xa9llo')", geometry_shout("h\xc3\xa9llo", &v_));
    STR_LINE("shout('')", geometry_shout("", &v_));
    STR_LINE("shout('a\xf0\x9f\x98\x80')", geometry_shout("a\xf0\x9f\x98\x80", &v_));
    {
        const uint8_t data[] = {1, 2, 3, 0, 255};
        BYTES_LINE("reverse_bytes(01020300ff)", geometry_reverse_bytes(data, sizeof data, &v_, &n_));
        BYTES_LINE("reverse_bytes()", geometry_reverse_bytes(NULL, 0, &v_, &n_));
    }
    {
        const int64_t values[] = {1, 2, 3, 4};
        INT_LINE("total([1, 2, 3, 4])", geometry_total(values, 4, &v_));
        INT_LINE("total([])", geometry_total(NULL, 0, &v_));
        INTS_LINE("squares([1, 2, 3, 4])", geometry_squares(values, 4, &v_, &n_));
        INTS_LINE("squares([])", geometry_squares(NULL, 0, &v_, &n_));
        INT_LINE("first_item([1, 2, 3, 4])", geometry_first_item(values, 4, &v_));
        INT_LINE("first_item([])", geometry_first_item(NULL, 0, &v_));
    }
    {
        const double values[] = {1.0, 2.0, 4.5};
        FLOAT_LINE("mean([1.0, 2.0, 4.5])", geometry_mean(values, 3, &v_));
        FLOAT_LINE("mean([])", geometry_mean(NULL, 0, &v_));
        FLOATS_LINE("halves([1.0, 2.0, 4.5])", geometry_halves(values, 3, &v_, &n_));
    }
    {
        geometry_Point shown = {2, 1.5, true}, hidden = {2, 1.5, false};
        FLOAT_LINE("weight(Point(2, 1.5, True))", geometry_weight(&shown, &v_));
        FLOAT_LINE("weight(Point(2, 1.5, False))", geometry_weight(&hidden, &v_));
    }
    {
        int rc = geometry_count_up(3);
        if (rc) error_line("count_up(3)", rc); else printf("count_up(3) = None\n");
        rc = geometry_count_up(-1);
        if (rc) error_line("count_up(-1)", rc); else printf("count_up(-1) = None\n");
    }

    /* C-only: a bad call is a status, never a crash, and a failed call leaves the results alone */
    int64_t i = 77;
    double d = 0;
    char *s = NULL;
    printf("add(NULL out) = %d\n", geometry_add(1, 2, NULL));
    printf("shout(NULL) = %d\n", geometry_shout(NULL, &s));
    printf("total(NULL, 3) = %d\n", geometry_total(NULL, 3, &i));
    printf("weight(NULL) = %d\n", geometry_weight(NULL, &d));
    printf("untouched = %" PRId64 "\n", i);
    printf("last_error = %s\n", geometry_last_error());
    geometry_add(1, 2, &i);
    printf("last_error after success = '%s'\n", geometry_last_error());
    geometry_free(NULL);

    pthread_t threads[4];
    long failures[4];
    for (int t = 0; t < 4; t++) pthread_create(&threads[t], NULL, worker, &failures[t]);
    long total_failures = 0;
    for (int t = 0; t < 4; t++) { pthread_join(threads[t], NULL); total_failures += failures[t]; }
    printf("threads: %ld failures\n", total_failures);
    return total_failures != 0;
}
