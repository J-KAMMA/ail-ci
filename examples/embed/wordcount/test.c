#include <stdio.h>
#include <string.h>
#include "wordcount.h"

static int show(const char *label, const char *text) {
    int64_t count = 0;
    int st = wordcount_word_count(text, strlen(text), &count);
    if (st != 0) {
        fprintf(stderr, "wordcount example: status %d: %s\n", st, wordcount_last_error());
        return 0;
    }
    printf("word_count(\"%s\") = %lld\n", label, (long long)count);
    return 1;
}

int main(void) {
    int ok = 1;
    ok &= show("", "");
    ok &= show("one", "one");
    ok &= show("  one two\\tthree\\nfour  ", "  one two\tthree\nfour  ");
    ok &= show("a,b c-d", "a,b c-d");
    wordcount_shutdown();
    return ok ? 0 : 1;
}
