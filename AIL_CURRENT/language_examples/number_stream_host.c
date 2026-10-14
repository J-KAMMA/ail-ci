#include "number_io.h"
#include <stdio.h>

int main(void) {
    number_io_error error;
    int status = number_io_number_pipe(1, 8192, &error);
    if (status) fprintf(stderr, "number_pipe failed: %d\n", status);
    return status;
}
