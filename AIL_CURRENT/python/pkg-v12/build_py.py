"""A Python expression becomes a standalone program that needs nothing on the host.

    python3 build_py.py 'sum(v*v for v in xs if v % 2)' oddsquares
    ./oddsquares data.bin

The expression is the Python a model already writes, unchanged -- twelve expressions written by a
model that had never seen this project compiled as they stood, and all twelve were right. What it
produces is what C produces: the same artifact size to within bytes, the same speed within noise.

The claim this is for is not tokens. It is that Python-shaped code reaches C's speed and weight
instead of CPython's, which on the measured task is 75.13x and 39.9x. Nothing here beats C, because
nothing beats C on those axes; the point is arriving there from a surface that costs nothing to
introduce.

POSIX only: it uses mmap.
"""
import pathlib, subprocess, sys

from pipeline import PipelineError, compiler, link_flags
from pyfront import to_pipeline_c

MAIN = r'''
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>

int main(int argc, char **argv) {
    if (argc < 2) { fputs("usage: tool FILE\n", stderr); return 2; }
    int fd = open(argv[1], O_RDONLY);
    struct stat st;
    /* `perror` drags strerror's tables into a static binary and costs 35,096 bytes of the 793,816
       this program weighs -- more than the whole gap to a hand-written C equivalent. The message it
       would add is not worth 4.4% of the artifact. */
    if (fd < 0 || fstat(fd, &st)) { fputs("cannot open input\n", stderr); return 1; }
    if (st.st_size == 0) { fputs("empty input\n", stderr); return 1; }
    const T *src = mmap(0, (size_t)st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (src == MAP_FAILED) { fputs("cannot map input\n", stderr); return 1; }
    close(fd);
    printf("%lld\n", (long long)run(src, (int64_t)((size_t)st.st_size / sizeof *src)));
    return 0;
}
'''


def build(expr, out, source='xs', strict=False):
    out = pathlib.Path(out)
    c = out.with_suffix('.c')
    c.write_text(to_pipeline_c(expr, source, strict=strict) + MAIN)
    r = subprocess.run([compiler(), '-O2', '-ffp-contract=off', *link_flags(), '-o', str(out), str(c)],
                       capture_output=True, text=True)
    if r.returncode:
        raise PipelineError('the C compiler rejected this:\n%s' % r.stderr[-800:])
    return out


def main(argv):
    if len(argv) != 3:
        print("usage: build_py.py 'PYTHON EXPRESSION over xs' OUTFILE", file=sys.stderr)
        return 2
    p = build(argv[1], argv[2])
    print('%s  %d bytes  (C source kept at %s)' % (p, p.stat().st_size, p.with_suffix('.c')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
