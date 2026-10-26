"""One pipeline of coarse verbs becomes one C loop, and nothing else comes with it.

    from pipeline import pipe
    total = pipe('sum where odd squares over xs')(xs)

The verbs fuse: no intermediate array is built, and a verb you do not use never becomes code. A
program using two of the twenty-one verbs carries the other nineteen as nothing, so the artifact is
the size of one function rather than the size of a library.

One rule holds it together: **generated code allocates nothing**. Sources arrive as a pointer and a
length, results go into a buffer the caller already owns, sorting happens in that buffer. A design
that had to grow a buffer would need an allocator, an allocator needs a runtime, and a runtime is
the hundred megabytes this exists to avoid. The same rule is the boundary -- anything that genuinely
must allocate belongs to the host language, and that is most code.

The measured claims and the conditions they were measured under are in README.md. This module
depends on nothing but the standard library and a C compiler.
"""
import ctypes, hashlib, os, pathlib, shutil, subprocess, sys, tempfile

MAPS = {'squares': 'x*x', 'double': '2*x', 'inc': 'x+1', 'dec': 'x-1',
        'negate': '-x', 'abs': 'x<0?-x:x', 'half': 'x/2', 'cube': 'x*x*x'}
PREDS = {'odd': 'x%2!=0', 'even': 'x%2==0', 'positive': 'x>0', 'negative': 'x<0',
         'nonzero': 'x!=0', 'small': 'x<100'}
FOLDS = {'sum': ('T a=0;', 'a+=x;', 'a'),
         'count': ('T a=0;', 'a+=1;', 'a'),
         'max': ('T a=LOW;', 'if(x>a)a=x;', 'a'),
         'min': ('T a=HIGH;', 'if(x<a)a=x;', 'a'),
         'product': ('T a=1;', 'a*=x;', 'a'),
         'any': ('T a=0;', 'if(x)a=1;', 'a'),
         'all': ('T a=1;', 'if(!x)a=0;', 'a')}
REAL_ONLY_BAD = {'odd', 'even'}          # integer parity has no meaning on a double

CMP = ('static int cmp(const void *a, const void *b){ T x=*(const T*)a, y=*(const T*)b;'
       ' return (x>y)-(x<y); }\n')

FULL = ('#include <stdio.h>\n'
        'static void ail_full(void){ fputs("collected more than the buffer holds\\n", stderr);'
        ' _Exit(1); }\n')


class PipelineError(ValueError):
    """The text is not a pipeline. The message says which word and what was expected instead."""


def compiler():
    """A C compiler, from $PIPE_CC or the PATH. Any of cc, clang or gcc will do."""
    cc = os.environ.get('PIPE_CC')
    if cc:
        return cc
    for name in ('cc', 'clang', 'gcc'):
        found = shutil.which(name)
        if found:
            return found
    raise PipelineError('no C compiler found on PATH; set $PIPE_CC')


def opt_flags():
    """The optimisation flags of a build: -O2, or -g -O0 under AIL_DEBUG=1 (`ail build --debug`, so gdb steps
    through the source lines the `#line` directives point at)."""
    return ['-g', '-O0', '-DAIL_DEBUG_SITE=1'] if os.environ.get('AIL_DEBUG') == '1' else ['-O2']


def ffi_link_args():
    """Extra link arguments for C libraries named by @extern stubs (G4); empty unless AIL_FFI_LINK is set."""
    import shlex
    return shlex.split(os.environ.get('AIL_FFI_LINK', ''))


def sqlite_link_args():
    """The link arguments of a program that uses sqlite3 (G11): the system libsqlite3, then what a static libsqlite3.a needs
    after it (the shared library records its own dependencies)."""
    return ['-lsqlite3', '-lm'] + (['-ldl', '-pthread'] if sys.platform.startswith('linux') else [])


def link_flags():
    """Dynamic linking is the default on Linux and macOS: a typed program is then about 30 KB
    instead of about 800 KB with a static glibc (decided 2026-10-11). AIL_STATIC=1 (set by
    `ail_chatgpt.py compile --static`) links statically, for a binary that runs on any Linux
    without the same C library. Windows keeps static linking, so a MinGW build needs no runtime
    DLLs beside it."""
    flags = []
    windows = os.name == 'nt' or os.environ.get('AIL_TARGET_OS') == 'windows'   # --target windows
    if windows or os.environ.get('AIL_STATIC') == '1':
        flags.append('-static')
    if windows:
        # UTF-8 console (decision Q8): a separate unit, so the generated C is the same everywhere.
        flags += ['-D_Exit=ail_wincon_exit', str(pathlib.Path(__file__).resolve().with_name('ail_wincon.c'))]
    flags += _curl_flags(flags)          # G12: include paths of libcurl, only for a program that uses urllib.request
    return flags


def _curl_flags(flags):
    try:
        import urllower
    except ImportError:
        return []
    return urllower.cflags()


def extra_libs(flags=None):
    """Libraries that come after the objects on the link line: libcurl for a program that uses urllib.request
    (G12), nothing for every other program."""
    try:
        import urllower
    except ImportError:
        return []
    return urllower.libs(static='-static' in (flags if flags is not None else link_flags()))

def cache_dir():
    d = os.environ.get('PIPE_CACHE')
    return pathlib.Path(d) if d else pathlib.Path.home() / '.cache' / 'pipeline'


def tokenize(text):
    """Words, with {...} kept whole so a C expression may contain spaces, and ',' its own word."""
    out, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
        elif text[i] == '{':
            j = text.find('}', i)
            if j < 0:
                raise PipelineError('unclosed { in %r' % text)
            out.append(text[i:j + 1])
            i = j + 1
        elif text[i] == ',':
            out.append(',')
            i += 1
        else:
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '{,':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def _stages(words, real, reject):
    """The stages of one fold as C statements, innermost first.

    Stages apply nearest-the-source first, so the words are walked right to left. `reject` is what a
    failing filter runs: `continue` in a loop of its own, `break` when several folds share one loop
    and each lives inside its own `do { } while (0)`.
    """
    out, i = [], len(words) - 1
    while i >= 0:
        t = words[i]
        if t in MAPS:
            out.append('x = %s;' % MAPS[t])
        elif t.startswith('{'):
            if i > 0 and words[i - 1] == 'where':
                out.append('if (!(%s)) %s;' % (t[1:-1], reject))
                i -= 1
            else:
                out.append('x = %s;' % t[1:-1])
        elif t in PREDS:
            if i == 0 or words[i - 1] != 'where':
                raise PipelineError('`%s` is a predicate; write `where %s`' % (t, t))
            if real and t in REAL_ONLY_BAD:
                raise PipelineError('`%s` is an integer predicate and this pipeline is `real`' % t)
            out.append('if (!(%s)) %s;' % (PREDS[t], reject))
            i -= 1
        elif t == 'where':
            raise PipelineError('`where` must be followed by a predicate or {expression}')
        else:
            raise PipelineError('unknown verb %r' % t)
        i -= 1
    return out


def parse(text):
    """Everything the emitter needs, and every rejection the grammar implies."""
    w = tokenize(text)
    real = bool(w) and w[0] == 'real'
    if real:
        w = w[1:]
    collect = None
    if len(w) >= 2 and w[-2] == 'into':
        collect, w = w[-1], w[:-2]
    sort = bool(w) and w[0] == 'sort'
    if sort:
        if collect is None:
            raise PipelineError('`sort` produces elements, so it needs `into ys`')
        w = w[1:]
    if len(w) < 2:
        raise PipelineError('a pipeline is `[real] [sort] fold? stage... over xs [into ys]`')
    if w[-2] == 'upto' and w[-1] == 'n':
        source, rest = 'range', w[:-2]
    elif w[-2] == 'over':
        source, rest = 'array', w[:-2]
    else:
        raise PipelineError('a source is `upto n` or `over xs`, got %r' % ' '.join(w[-2:]))

    groups, cur = [], []
    for t in rest:
        if t == ',':
            groups.append(cur)
            cur = []
        else:
            cur.append(t)
    groups.append(cur)
    if len(groups) > 1 and collect is not None:
        raise PipelineError('`into` collects elements; several folds produce several numbers')
    if collect is None:
        for g in groups:
            if not g or g[0] not in FOLDS:
                raise PipelineError('each fold starts with one of %s, got %r'
                                    % (' '.join(sorted(FOLDS)), ' '.join(g[:1]) or '(nothing)'))
    elif groups[0] and groups[0][0] in FOLDS:
        raise PipelineError('`into` collects elements; it does not take the fold `%s`'
                            % groups[0][0])
    return dict(real=real, sort=sort, collect=collect, source=source, groups=groups)


def emit(text, name='run'):
    """One C function: one loop over the source, one accumulator per fold, no allocation."""
    p = parse(text)
    T = 'double' if p['real'] else 'int64_t'
    low, high = ('-1.0/0.0', '1.0/0.0') if p['real'] else ('INT64_MIN', 'INT64_MAX')
    head = ('for (int64_t k = 0; k < n; k++) { T x = (T)k;' if p['source'] == 'range'
            else 'for (int64_t k = 0; k < n; k++) { T x = src[k];')
    args = 'int64_t n' if p['source'] == 'range' else 'const T *src, int64_t n'
    pre = '#include <stdint.h>\n#include <stdlib.h>\n#define T %s\n' % T

    if p['collect'] is not None:
        body = '\n        '.join(_stages(p['groups'][0], p['real'], 'continue'))
        # The caller owns `out`, and until an audit found it this wrote into it without ever being
        # told how large it is -- a buffer one element short was silent memory corruption. The
        # capacity is now a parameter and overrunning it stops the program, which is what every
        # other out-of-range access here already does.
        return (pre + FULL + (CMP if p['sort'] else '')
                + 'int64_t %s(%s, T *out, int64_t cap) {\n    int64_t m = 0;\n    %s\n        %s\n'
                  '        if (m == cap) ail_full();\n        out[m++] = x;\n    }\n'
                  '%s    return m;\n}\n'
                % (name, args, head, body,
                   '    if (m > 1) qsort(out, (size_t)m, sizeof *out, cmp);\n' if p['sort'] else ''))

    if len(p['groups']) == 1:
        init, step, res = FOLDS[p['groups'][0][0]]
        body = '\n        '.join(_stages(p['groups'][0][1:], p['real'], 'continue'))
        return (pre + 'T %s(%s) {\n    %s\n    %s\n        %s\n        %s\n    }\n'
                      '    return %s;\n}\n'
                % (name, args, init.replace('LOW', low).replace('HIGH', high),
                   head, body, step, res))

    decls, blocks, stores = [], [], []
    # `sum, count upto n` reads no array, and this branch used to say `src[k]` whatever the source
    # was -- so a multi-fold over a range named a parameter the function does not have. It failed to
    # compile rather than answering wrongly, and no test put the two together, so nothing caught it.
    element = 'src[k]' if p['source'] == 'array' else '(T)k'
    for j, g in enumerate(p['groups']):
        init, step, res = FOLDS[g[0]]
        acc = 'a%d' % j
        decls.append(init.replace('LOW', low).replace('HIGH', high).replace('a', acc, 1))
        stages = '\n            '.join(_stages(g[1:], p['real'], 'break'))
        blocks.append('do { T x = %s;\n            %s\n            %s\n        } while (0);'
                      % (element, stages, step.replace('a', acc)))
        stores.append('out[%d] = %s;' % (j, res.replace('a', acc)))
    return (pre + 'void %s(%s, T *out) {\n    %s\n    for (int64_t k = 0; k < n; k++) {\n'
                  '        %s\n    }\n    %s\n}\n'
            % (name, args, '\n    '.join(decls), '\n        '.join(blocks), '\n    '.join(stores)))


def shared_object(src, prefix='p', extra=()):
    """Compile once and keep it. The source is the cache key, so identical pipelines compile once.

    `extra` carries link flags a program reached -- `-lm` when it raises something to a power -- and
    is part of the key, so two programs that differ only in what they link do not share a file.
    """
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((src + '\n'.join(extra)).encode()).hexdigest()[:16]
    so = d / ('%s%s.so' % (prefix, key))
    if not so.exists():
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp) / 'a.c'
            c.write_text(src, encoding='utf-8')
            r = subprocess.run([compiler(), '-O2', '-ffp-contract=off', '-shared', '-fPIC', '-o', str(so), str(c)]
                               + list(extra), capture_output=True, text=True)
            if r.returncode:
                raise PipelineError('the C compiler rejected this:\n%s\n%s' % (r.stderr[-600:], src))
    return so


def _address(buf):
    """The first byte of a buffer, without requiring numpy."""
    if hasattr(buf, 'ctypes'):                       # numpy array
        return buf.ctypes.data
    if hasattr(buf, 'buffer_info'):                  # array.array
        return buf.buffer_info()[0]
    return ctypes.addressof(ctypes.c_char.from_buffer(memoryview(buf)))


class Pipeline:
    """A compiled pipeline. `artifact` is the file on disk; `c` is what it was compiled from."""

    def __init__(self, text):
        self.text = text
        self.spec = parse(text)
        self.c = emit(text)
        self.artifact = shared_object(self.c)
        self.elem = ctypes.c_double if self.spec['real'] else ctypes.c_int64
        self.outputs = len(self.spec['groups'])
        fn = ctypes.CDLL(str(self.artifact)).run
        fn.restype = (ctypes.c_int64 if self.spec['collect'] is not None
                      else None if self.outputs > 1 else self.elem)
        self.raw = fn

    def __call__(self, src, n=None, out=None):
        p = ctypes.POINTER(self.elem)
        if self.spec['source'] == 'range':
            args = [ctypes.c_int64(src)]
        else:
            args = [ctypes.cast(_address(src), p),
                    ctypes.c_int64(len(src) if n is None else n)]
        if self.spec['collect'] is not None:
            if out is None:
                raise PipelineError('`into %s` writes into a buffer you own; pass out=...'
                                    % self.spec['collect'])
            # the capacity travels with the pointer, so a buffer too small stops rather than
            # overruns
            return self.raw(*args, ctypes.cast(_address(out), p), ctypes.c_int64(len(out)))
        if self.outputs == 1:
            return self.raw(*args)
        buf = (self.elem * self.outputs)()
        self.raw(*args, buf)
        return tuple(buf)


_COMPILED = {}


def pipe(text):
    """A compiled pipeline, one per distinct text."""
    if text not in _COMPILED:
        _COMPILED[text] = Pipeline(text)
    return _COMPILED[text]
