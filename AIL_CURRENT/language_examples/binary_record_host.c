/* C owns the input and releases successful AIL results with record_free. */
#include "record.h"
#include <stdio.h>
#include <string.h>

int main(void) {
    unsigned char input[256];
    for (size_t i = 0; i < sizeof input; i++) input[i] = (unsigned char)i;
    record_buffer packed = {0}, restored = {0}, unchanged = {0};
    record_error error;
    int status = record_pack_record((record_view){input, sizeof input}, &packed, &error);
    if (!status) status = record_unpack_record((record_view){packed.data, packed.size}, &restored, &error);
    if (status) {
        fprintf(stderr, "%d: %s\n", status, error.message);
        record_free(packed.data);
        return 1;
    }
    int correct = packed.size == 264 && !memcmp(packed.data, "AIL1\0\1\0\0", 8)
        && !memcmp(packed.data + 8, input, sizeof input)
        && restored.size == sizeof input && !memcmp(restored.data, input, sizeof input);
    int invalid = record_unpack_record((record_view){input, 3}, &unchanged, &error);
    printf("packed=%zu restored=%zu invalid=%d\n", packed.size, restored.size, invalid);
    record_free(restored.data);
    record_free(packed.data);
    return !(correct && invalid == 1 && !unchanged.data && !unchanged.size);
}
