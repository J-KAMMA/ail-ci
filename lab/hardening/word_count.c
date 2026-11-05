#include <stdio.h>

int main(void) {
    long long bytes = 0;
    int newlines = 0, words = 0, in_word = 0, last = -1, c;
    while ((c = getchar()) != EOF) {
        bytes += 1;
        last = c;
        if (c == '\n') {
            newlines += 1;
            if (in_word) {
                words += 1;
                in_word = 0;
            }
        } else if (c == ' ' || c == '\t' || c == '\r') {
            if (in_word) {
                words += 1;
                in_word = 0;
            }
        } else {
            in_word = 1;
        }
    }
    if (in_word) words += 1;
    if (bytes > 0 && last != '\n') newlines += 1;
    printf("bytes=%lld lines=%d words=%d\n", bytes, newlines, words);
    return 0;
}
