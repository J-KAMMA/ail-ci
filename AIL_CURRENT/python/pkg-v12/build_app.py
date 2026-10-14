"""Turn a pipeline into a standalone program that needs nothing on the host.

    python3 build_app.py 'sum where odd squares, count where negative, max abs over xs' myapp
    ./myapp data.bin

The program maps its input instead of reading it into a buffer, because that was measured: of the
29.5 ms the read-and-copy version spent, the 40 MB copy was 26.4 and mapping the same bytes and
touching every page is 4.1. Removing the copy and fusing the traversals made the program 3.50x
faster and 56 bytes smaller -- `mmap` is two syscalls and three loops becoming one deletes code.

`MAP_POPULATE` was tried against exactly this and measured 1.04x, indistinguishable from noise, and
is not used. What is left is 47.2% page faults and 48.6% traversal at 9.8 GB/s, so no phase
dominates and further work here is worth under 2x.

POSIX only: it uses mmap.
"""
import pathlib, subprocess, sys

from pipeline import PipelineError, compiler, link_flags, emit, parse

MAIN = r'''
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>

int main(int argc, char **argv) {
    if (argc < 2) { fputs("usage: app FILE\n", stderr); return 2; }
    int fd = open(argv[1], O_RDONLY);
    struct stat st;
    if (fd < 0 || fstat(fd, &st)) { perror(argv[1]); return 1; }
    if (st.st_size == 0) { fputs("empty input\n", stderr); return 1; }
    const T *src = mmap(0, (size_t)st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (src == MAP_FAILED) { perror("mmap"); return 1; }
    close(fd);
    int64_t n = (int64_t)((size_t)st.st_size / sizeof *src);
    T out[NOUT];
    RUN;
    for (int i = 0; i < NOUT; i++) printf(FMT "%c", out[i], i + 1 < NOUT ? ' ' : '\n');
    return 0;
}
'''


def source(text):
    """The pipeline's own function, plus a main that owns the mapping and prints the results."""
    spec = parse(text)
    if spec['source'] != 'array':
        raise PipelineError('a standalone program reads a file, so its source is `over xs`')
    if spec['collect'] is not None:
        raise PipelineError('a standalone program prints numbers; drop the `into`')
    nout = len(spec['groups'])
    call = 'run(src, n, out)' if nout > 1 else 'out[0] = run(src, n)'
    return (emit(text)
            + '#define NOUT %d\n#define RUN %s\n#define FMT "%s"\n' % (nout, call,
                                                                      '%g' if spec['real'] else '%lld')
            + (MAIN if spec['real'] else MAIN.replace('out[i]', '(long long)out[i]')))


def build(text, out):
    out = pathlib.Path(out)
    c = out.with_suffix('.c')
    c.write_text(source(text))
    r = subprocess.run([compiler(), '-O2', *link_flags(), '-o', str(out), str(c)],
                       capture_output=True, text=True)
    if r.returncode:
        raise PipelineError('the C compiler rejected this:\n%s' % r.stderr[-800:])
    return out


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    p = build(argv[1], argv[2])
    print('%s  %d bytes  (C source kept at %s)' % (p, p.stat().st_size, p.with_suffix('.c')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
