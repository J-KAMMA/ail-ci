"""Count native allocations independently while generated AIL catches exceptions."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
SOURCE = '''
def allocate(n: int) -> int:
    values = [i for i in range(8193)]
    if n % 2 == 0:
        raise ValueError()
    return values[-1]

def middle(n: int) -> int:
    values = [n, n+1]
    try:
        return allocate(n) + values[0]
    except IndexError:
        return -1

def run(n: int) -> int:
    retained = [17, 23]
    total = 0
    for i in range(n):
        try:
            total += middle(i)
        except ValueError:
            total += retained[0]
        retained[1] = 23
    return total + retained[1]
'''

ALLOCATOR = r'''
#define AIL_NO_OBJ_POOL 1   /* struct objects from malloc, so the counters below see every one */
#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef union { max_align_t alignment; size_t size; } allocation_header;
static size_t live, live_bytes, peak_bytes;
static void *count_malloc(size_t size) {
    allocation_header *p = malloc(sizeof *p + size);
    if (!p) return NULL;
    p->size = size; live++; live_bytes += size;
    if (live_bytes > peak_bytes) peak_bytes = live_bytes;
    return p + 1;
}
static void count_free(void *ptr) {
    if (!ptr) return;
    allocation_header *p = (allocation_header *)ptr - 1;
    live--; live_bytes -= p->size; free(p);
}
static void *count_calloc(size_t n, size_t size) {
    if (size && n > (size_t)-1 / size) return NULL;
    void *p = count_malloc(n * size);
    if (p) memset(p, 0, n * size);
    return p;
}
static void *count_realloc(void *ptr, size_t size) {
    if (!ptr) return count_malloc(size);
    if (!size) { count_free(ptr); return NULL; }
    allocation_header *old = (allocation_header *)ptr - 1;
    size_t old_size = old->size;
    allocation_header *p = realloc(old, sizeof *p + size);
    if (!p) return NULL;
    p->size = size; live_bytes = live_bytes - old_size + size;
    if (live_bytes > peak_bytes) peak_bytes = live_bytes;
    return p + 1;
}
#define malloc count_malloc
#define calloc count_calloc
#define realloc count_realloc
#define free count_free
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class ExceptionResourceTests(unittest.TestCase):
    def check_resources(self, source, sizes=(1, 2, 101, 1001), library=False, separate=False,
                        native_source=None):
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            info = {'_want_units': True} if separate else None
            generated = to_c(source if native_source is None else native_source,
                             name='run', strict=True, library=library, info=info)
        finally:
            sys.path.pop(0)
        reference = {}
        exec(source, reference)
        expected = []
        for n in sizes:
            with contextlib.redirect_stdout(io.StringIO()):
                expected.append(reference['run'](n))
        calls = ','.join(str(n) for n in sizes)
        # The bounded process-wide string cache deliberately survives a function. Release
        # only its recorded blocks; abandoned allocations remain visible to this counter.
        drain_cache = ('''for (int64_t j=0; j<ail__blk_cache_n; j++)
            count_free(ail__blk_cache[j].p);
        ail__blk_cache_n=0; ail__blk_cache_bytes=0;'''
                       if 'ail__blk_cache_n' in generated else '')
        drain_cache += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain_cache += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        host = r'''
#undef malloc
#undef calloc
#undef realloc
#undef free
int main(void) {
    int sizes[] = {SIZES};
    for (size_t i=0; i<sizeof sizes/sizeof *sizes; i++) {
        long long value = (long long)run(sizes[i]);
        FRAME_GUARD
        DRAIN_CACHE
        printf("%lld %zu %zu\n",value,live,live_bytes);
        if (live || live_bytes) return 5;
    }
    fprintf(stderr,"peak_bytes=%zu\n",peak_bytes);
    return 0;
}
'''.replace('SIZES', calls).replace('DRAIN_CACHE', drain_cache).replace(
            'FRAME_GUARD', ('if (ail_cleanup_top) return 6;'
                            if 'ail_cleanup_top' in generated else '')
            + ('if (ail_depth) return 7;'
               if 'AIL_LINK_STATE(int64_t, ail_depth,' in generated else ''))
        with tempfile.TemporaryDirectory(prefix='ail-exception-resource-') as directory:
            root = Path(directory)
            c = root / 'test.c'
            compiler = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
            objects = []
            allocator = ALLOCATOR
            if separate:
                declarations, units = info['c_units']
                allocator = allocator.replace('static void', 'void')
                imports = '''#define AIL_NO_OBJ_POOL 1
#include <stdlib.h>
void *count_malloc(size_t);
void *count_calloc(size_t,size_t);
void *count_realloc(void *,size_t);
void count_free(void *);
#define malloc count_malloc
#define calloc count_calloc
#define realloc count_realloc
#define free count_free
#define AIL_LINK_STATE(type,name,init) extern type name
#define AIL_LINK_EXPORT __attribute__((weak))
'''
                for i, (_, body) in enumerate(units[:-1]):
                    part = root / f'part{i}.c'
                    part.write_text(imports + declarations + body, encoding='utf8')
                    obj = root / f'part{i}.o'
                    result = subprocess.run([compiler, '-std=c11', '-O2', '-c', str(part), '-o', str(obj)],
                                            capture_output=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                    objects.append(str(obj))
                generated = '#define AIL_LINK_STATE(type,name,init) type name init\n' + declarations + units[-1][1]
            c.write_text(allocator + generated + host, encoding='utf8')
            exe = root / ('test.exe' if os.name == 'nt' else 'test')
            result = subprocess.run([compiler, '-std=c11', '-O2', str(c), *objects, '-lm', '-o', str(exe)],
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            result = subprocess.run([str(exe)], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            self.assertEqual(result.stdout.decode().splitlines(), [f'{value} 0 0' for value in expected])
            self.assertIn(b'peak_bytes=', result.stderr)

    def test_callee_unwind_preserves_catcher_and_releases_allocations(self):
        self.check_resources(SOURCE)

    def test_exception_cleanup_across_compiled_objects(self):
        self.check_resources(SOURCE, separate=True)

    def test_cleanup_symbols_do_not_collide_with_user_functions(self):
        helpers = '''
def allocate__unwind(n: int) -> int:
    return n
def ail_unwind_allocate(n: int) -> int:
    return n
def ail_unwind_allocate_(n: int) -> int:
    return n
'''
        self.check_resources(helpers + SOURCE, sizes=(2, 101), library=True)

    def test_recursive_unwind_restores_depth_and_multiple_arenas(self):
        self.check_resources('''
def descend(depth: int) -> int:
    if depth == 0:
        raise ValueError()
    return descend(depth - 1)

def work(n: int) -> int:
    text = "value:" + str(n)
    blob = b"abcd" + b"efgh"
    table = {1: n, 2: n+1}
    values = [n, n+1]
    try:
        descend(4)
    except ValueError:
        values[0] = len(text) + len(blob) + table[2]
    raise IndexError()

def run(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            work(i)
        except IndexError:
            total += 1
    return total
''')

    def test_string_list_transfer_and_abandoned_return(self):
        self.check_resources('''
def words(n: int):
    result: list[str] = []
    result.append("one")
    result.append("two")
    result.append("three")
    if n % 2 == 0:
        raise ValueError()
    return result

def consume(n: int) -> int:
    result = words(n)
    if n % 3 == 0:
        raise IndexError()
    return len(result) + len(result[0]) + len(result[-1])

def run(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            total += consume(i)
        except ValueError:
            total += 7
        except IndexError:
            total += 11
    return total
''')

    def test_nonescaping_object_with_and_without_local_handler(self):
        self.check_resources('''
class Point:
    def __init__(self, x):
        self.x = x

def leaf(n: int) -> int:
    p = Point(n)
    if n % 2 == 0:
        raise ValueError()
    return p.x

def middle(n: int) -> int:
    p = Point(n)
    try:
        return leaf(n) + p.x
    except ValueError:
        p.x = p.x + 1
    raise IndexError()

def run(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            total += middle(i)
        except IndexError:
            total += 3
    return total
''')


if __name__ == '__main__':
    unittest.main()
