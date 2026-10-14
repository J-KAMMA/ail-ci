/* Preserve the independent reference; Windows standard streams must be binary. */
#define main number_reference_main
#include "number_stream_reference.c"
#undef main
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int main(void) {
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) < 0 ||
        _setmode(_fileno(stdout), _O_BINARY) < 0) return 3;
#endif
    return number_reference_main();
}
