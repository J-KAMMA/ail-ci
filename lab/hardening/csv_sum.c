#include <stdio.h>

int main(void) {
    long long total = 0, field = 0, minimum = 0, maximum = 0;
    int rows = 0, negative = 0, have = 0, c;
    for (;;) {
        int at_end = 0;
        c = getchar();
        if (c == EOF) {
            at_end = 1;
        } else if (c == ',' || c == '\n' || c == '\r') {
            at_end = 0;
        } else {
            if (c == '-') {
                negative = 1;
            } else if (c >= '0' && c <= '9') {
                field = field * 10 + (c - '0');
                have = 1;
            }
            continue;
        }
        if (have) {
            if (negative) {
                field = -field;
            }
            total += field;
            if (rows == 0) {
                minimum = field;
                maximum = field;
            } else {
                if (field < minimum) minimum = field;
                if (field > maximum) maximum = field;
            }
            rows += 1;
        }
        field = 0;
        negative = 0;
        have = 0;
        if (at_end) break;
    }
    printf("rows=%d sum=%lld min=%lld max=%lld\n", rows, total, minimum, maximum);
    return 0;
}
