/* Windows console support, linked into every executable the compiler builds on or for Windows
   (pipeline.link_flags adds this file and -D_Exit=ail_wincon_exit). It is a separate translation
   unit on purpose: the generated C, and so the Linux and macOS output, does not change at all.

   Decision Q8 (docs/design/GENERAL_PURPOSE.md): text I/O is UTF-8. A Windows console reads and
   writes through its code page (932, 437, ...), so when -- and only when -- a standard handle is a
   console, this switches that console to CP_UTF8 for the life of the process and puts the old code
   page back at exit. The C library then translates the UTF-8 bytes the runtime writes. Redirected
   handles (pipes, files) are never touched: the bytes the program writes are the bytes that arrive,
   with the text-mode LF -> CRLF translation CPython's sys.stdout also performs on Windows. */
#ifdef _WIN32
#include <windows.h>
#include <stdlib.h>
#undef _Exit

static UINT ail_wincon_out_cp, ail_wincon_in_cp;

static int ail_wincon_is_console(DWORD which) {
    DWORD mode;
    HANDLE h = GetStdHandle(which);
    return h && h != INVALID_HANDLE_VALUE && GetConsoleMode(h, &mode);
}

static void ail_wincon_restore(void) {
    if (ail_wincon_out_cp) SetConsoleOutputCP(ail_wincon_out_cp);
    if (ail_wincon_in_cp) SetConsoleCP(ail_wincon_in_cp);
    ail_wincon_out_cp = ail_wincon_in_cp = 0;
}

__attribute__((noreturn)) void ail_wincon_exit(int status) {
    ail_wincon_restore();
    _exit(status);
}

__attribute__((constructor)) static void ail_wincon_init(void) {
    if (ail_wincon_is_console(STD_OUTPUT_HANDLE) || ail_wincon_is_console(STD_ERROR_HANDLE)) {
        UINT cp = GetConsoleOutputCP();
        if (cp && cp != CP_UTF8 && SetConsoleOutputCP(CP_UTF8)) ail_wincon_out_cp = cp;
    }
    if (ail_wincon_is_console(STD_INPUT_HANDLE)) {
        UINT cp = GetConsoleCP();
        if (cp && cp != CP_UTF8 && SetConsoleCP(CP_UTF8)) ail_wincon_in_cp = cp;
    }
    if (ail_wincon_out_cp || ail_wincon_in_cp) atexit(ail_wincon_restore);
}
#endif
