/* G5a: zlib.compress / zlib.decompress as CPython 3.12 runs them (Modules/zlibmodule.c): the same
   deflateInit2/inflateInit2 arguments, the same loops, and the same error wording. */
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include "zlib_glue.h"

static unsigned char *result;
static size_t result_n;
static char message[512];

/* zlib_error() of zlibmodule.c */
static void report(int err, const z_stream *zs, const char *what) {
    const char *zmsg = NULL;
    if (err == Z_VERSION_ERROR) zmsg = "library version mismatch";
    if (zmsg == NULL) zmsg = zs->msg;
    if (zmsg == NULL) {
        switch (err) {
        case Z_BUF_ERROR: zmsg = "incomplete or truncated stream"; break;
        case Z_STREAM_ERROR: zmsg = "inconsistent stream state"; break;
        case Z_DATA_ERROR: zmsg = "invalid input data"; break;
        }
    }
    if (zmsg == NULL) snprintf(message, sizeof message, "Error %d %s", err, what);
    else snprintf(message, sizeof message, "Error %d %s: %.200s", err, what, zmsg);
}

static void clear(void) {
    free(result);
    result = NULL;
    result_n = 0;
    message[0] = 0;
}

static int grow(unsigned char **buf, size_t *cap) {
    size_t next = *cap ? *cap * 2 : 16384;
    if (next < *cap) return 0;
    unsigned char *bigger = realloc(*buf, next);
    if (!bigger) return 0;
    *buf = bigger;
    *cap = next;
    return 1;
}

static int nomem(const char *what) {
    snprintf(message, sizeof message, "Out of memory while %s data", what);
    return Z_MEM_ERROR;
}

int zglue_deflate(int level, int wbits, const unsigned char *src, size_t n) {
    z_stream zs;
    memset(&zs, 0, sizeof zs);
    clear();
    int err = deflateInit2(&zs, level, Z_DEFLATED, wbits, 8, Z_DEFAULT_STRATEGY);
    if (err == Z_MEM_ERROR) return nomem("compressing");
    if (err == Z_STREAM_ERROR) {
        snprintf(message, sizeof message, "Bad compression level");
        return err;
    }
    if (err != Z_OK) {
        deflateEnd(&zs);
        report(err, &zs, "while compressing data");
        return err;
    }
    unsigned char *out = NULL;
    size_t cap = 0, used = 0, left = n;
    const unsigned char *p = src;
    int flush;
    do {
        size_t take = left > UINT_MAX ? UINT_MAX : left;
        zs.next_in = (Bytef *)p;
        zs.avail_in = (uInt)take;
        p += take;
        left -= take;
        flush = left == 0 ? Z_FINISH : Z_NO_FLUSH;
        do {
            if (used == cap && !grow(&out, &cap)) {
                deflateEnd(&zs);
                free(out);
                return nomem("compressing");
            }
            size_t room = cap - used;
            if (room > UINT_MAX) room = UINT_MAX;
            zs.next_out = out + used;
            zs.avail_out = (uInt)room;
            err = deflate(&zs, flush);
            used += room - zs.avail_out;
            if (err == Z_STREAM_ERROR) {
                deflateEnd(&zs);
                free(out);
                report(err, &zs, "while compressing data");
                return err;
            }
        } while (zs.avail_out == 0);
    } while (flush != Z_FINISH);
    deflateEnd(&zs);
    if (err != Z_STREAM_END) {
        free(out);
        report(err, &zs, "while compressing data");
        return err;
    }
    result = out;
    result_n = used;
    return 0;
}

int zglue_inflate(int wbits, const unsigned char *src, size_t n, size_t bufsize) {
    z_stream zs;
    memset(&zs, 0, sizeof zs);
    clear();
    int err = inflateInit2(&zs, wbits);
    if (err == Z_MEM_ERROR) return nomem("decompressing");
    if (err != Z_OK) {
        inflateEnd(&zs);
        report(err, &zs, "while preparing to decompress data");
        return err;
    }
    unsigned char *out = NULL;
    size_t cap = 0, used = 0, left = n;
    if (bufsize > 0) {
        out = malloc(bufsize);
        if (!out) {
            inflateEnd(&zs);
            return nomem("decompressing");
        }
        cap = bufsize;
    }
    const unsigned char *p = src;
    size_t remains;
    do {
        size_t take = left > UINT_MAX ? UINT_MAX : left;
        zs.next_in = (Bytef *)p;
        zs.avail_in = (uInt)take;
        p += take;
        left -= take;
        remains = left;
        do {
            if (used == cap && !grow(&out, &cap)) {
                inflateEnd(&zs);
                free(out);
                return nomem("decompressing");
            }
            size_t room = cap - used;
            if (room > UINT_MAX) room = UINT_MAX;
            zs.next_out = out + used;
            zs.avail_out = (uInt)room;
            err = inflate(&zs, Z_FINISH);
            used += room - zs.avail_out;
            if (err != Z_OK && err != Z_BUF_ERROR && err != Z_STREAM_END) {
                inflateEnd(&zs);
                free(out);
                if (err == Z_MEM_ERROR) return nomem("decompressing");
                report(err, &zs, "while decompressing data");
                return err;
            }
        } while (zs.avail_out == 0);
    } while (err != Z_STREAM_END && remains != 0);
    if (err != Z_STREAM_END) {
        inflateEnd(&zs);
        free(out);
        report(err, &zs, "while decompressing data");
        return err ? err : -1;
    }
    inflateEnd(&zs);
    result = out;
    result_n = used;
    return 0;
}

size_t zglue_size(void) { return result_n; }

int zglue_take(unsigned char *dst, size_t n) {
    if (n != result_n) return -1;
    if (n) memcpy(dst, result, n);
    clear();
    return 0;
}

const char *zglue_errmsg(void) { return message; }
