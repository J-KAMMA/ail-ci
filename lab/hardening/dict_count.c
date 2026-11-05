#include <stdio.h>
#include <string.h>

#define MAX_WORDS 4096
#define MAX_LEN 64

int main(void) {
    static char words[MAX_WORDS][MAX_LEN];
    static int counts[MAX_WORDS];
    char current[MAX_LEN];
    int distinct = 0, total = 0, have = 0, len = 0, c, i, j;

    while ((c = getchar()) != EOF) {
        if (c == ' ' || c == '\n' || c == '\t' || c == '\r') {
            if (have) {
                current[len] = '\0';
                for (i = 0; i < distinct; i++) {
                    if (strcmp(words[i], current) == 0) break;
                }
                if (i == distinct) {
                    strcpy(words[distinct], current);
                    counts[distinct] = 0;
                    distinct += 1;
                }
                counts[i] += 1;
                total += 1;
                have = 0;
                len = 0;
            }
        } else if (len < MAX_LEN - 1) {
            current[len++] = (char)c;
            have = 1;
        }
    }
    if (have) {
        current[len] = '\0';
        for (i = 0; i < distinct; i++) {
            if (strcmp(words[i], current) == 0) break;
        }
        if (i == distinct) {
            strcpy(words[distinct], current);
            counts[distinct] = 0;
            distinct += 1;
        }
        counts[i] += 1;
        total += 1;
    }
    for (i = 1; i < distinct; i++) {
        j = i;
        while (j > 0 && strcmp(words[j - 1], words[j]) > 0) {
            char tmp[MAX_LEN];
            int count;
            strcpy(tmp, words[j - 1]);
            strcpy(words[j - 1], words[j]);
            strcpy(words[j], tmp);
            count = counts[j - 1];
            counts[j - 1] = counts[j];
            counts[j] = count;
            j -= 1;
        }
    }
    printf("distinct=%d words=%d\n", distinct, total);
    for (i = 0; i < distinct; i++) {
        printf("%s %d\n", words[i], counts[i]);
    }
    return 0;
}
