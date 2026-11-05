#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    int parts_count = 0, i;
    long long hash = 0, size;
    char **parts = malloc(sizeof(char *) * 4000);
    char *text;
    for (i = 0; i < 2000; i++) {
        char *row = malloc(32);
        snprintf(row, 32, "row-%d:", i);
        parts[parts_count++] = row;
        if (i % 3 == 0) {
            char *tag = malloc(8);
            snprintf(tag, 8, "fizz");
            parts[parts_count++] = tag;
        } else if (i % 5 == 0) {
            char *tag = malloc(8);
            snprintf(tag, 8, "buzz");
            parts[parts_count++] = tag;
        }
    }
    text = malloc((size_t)parts_count * 33 + 1);
    text[0] = '\0';
    for (i = 0; i < parts_count; i++) {
        strcat(text, parts[i]);
        strcat(text, ",");
        free(parts[i]);
    }
    free(parts);
    for (i = 0; text[i] != '\0'; i++) {
        hash = (hash * 31 + (unsigned char)text[i]) % 1000000007;
    }
    size = (long long)strlen(text);
    printf("parts=%d bytes=%lld hash=%lld\n", parts_count, size, hash);
    free(text);
    return 0;
}
