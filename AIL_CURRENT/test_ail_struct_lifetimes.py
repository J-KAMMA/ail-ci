"""Numeric struct ownership checked against Python and independent allocation counts."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_ail_exception_resources import ALLOCATOR, ROOT

POINT = '''
class Point:
    def __init__(self, x):
        self.x = x

def maker(x: int):
    return Point(x)

def identity(p: Point):
    return p

def second(a: Point, b: Point):
    return b
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class StructLifetimeTests(unittest.TestCase):
    def check_lifetimes(self, body, separate=False, sizes=(1, 16, 10000)):
        source = POINT + body
        reference = {}
        exec(source, reference)
        expected = [reference['run'](n) for n in sizes]
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            info = {'_want_units': True} if separate else None
            generated = to_c(source, name='run', strict=True, library=True, info=info)
        finally:
            sys.path.pop(0)
        frames = '(ail_cleanup_top != NULL)' if 'ail_cleanup_top' in generated else '0'
        # Drain only the runtime's recorded, bounded cache; untracked allocations stay visible.
        drain_cache = ('''for (int64_t j=0; j<ail__blk_cache_n; j++) count_free(ail__blk_cache[j].p);
ail__blk_cache_n=0; ail__blk_cache_bytes=0;''' if 'ail__blk_cache_n' in generated else '')
        drain_cache += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain_cache += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        cache_calls, cache_declarations = [], []
        host = r'''
#undef malloc
#undef calloc
#undef realloc
#undef free
int main(void) {
    int sizes[] = {SIZES};
    for (size_t i=0; i<sizeof sizes/sizeof *sizes; i++) {
        peak_bytes = 0;
        long long value = (long long)run(sizes[i]);
        DRAIN_CACHE
        int frames = FRAMES;
        printf("%lld %zu %zu %d %zu\n",value,live,live_bytes,frames,peak_bytes);
        if (live || live_bytes || frames) return 5;
    }
    return 0;
}
'''.replace('FRAMES', frames).replace('SIZES', ','.join(map(str, sizes)))
        compiler = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        with tempfile.TemporaryDirectory(prefix='ail-struct-lifetime-') as directory:
            root = Path(directory)
            allocator = ALLOCATOR
            objects = []
            if separate:
                declarations, units = info['c_units']
                self.assertGreater(len(units), 1, 'separate translation must emit multiple units')
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
'''
                for i, (_, body) in enumerate(units[:-1]):
                    part = root / f'part{i}.c'
                    cache_name = 'drain_cache_part_' + str(i)
                    cache_calls.append(cache_name + '();')
                    cache_declarations.append('void ' + cache_name + '(void);')
                    part.write_text(imports + declarations + body + '\nvoid ' + cache_name + '(void) {' + drain_cache + '}\n', encoding='utf8')
                    obj = root / f'part{i}.o'
                    result = subprocess.run([compiler, '-std=c11', *FLAGS, '-c', str(part), '-o', str(obj)],
                                            capture_output=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                    objects.append(str(obj))
                generated = '#define AIL_LINK_STATE(type,name,init) type name init\n' + declarations + units[-1][1]
            c = root / 'test.c'
            host = '\n'.join(cache_declarations) + '\n' + host.replace('DRAIN_CACHE', ''.join(cache_calls) + drain_cache)
            c.write_text(allocator + generated + host, encoding='utf8')
            exe = root / ('test.exe' if os.name == 'nt' else 'test')
            result = subprocess.run([compiler, '-std=c11', *FLAGS, str(c), *objects, '-lm', '-o', str(exe)],
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            result = subprocess.run([str(exe)], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            rows = [list(map(int, line.split())) for line in result.stdout.decode().splitlines()]
            self.assertEqual(len(rows), len(sizes))
            for row, value in zip(rows, expected):
                self.assertEqual(row[:4], [value, 0, 0, 0])
            self.assertGreater(rows[0][4], 0)
            # A slot can retain the previous iteration while its replacement is evaluated.
            # Compare the long run with the warmed-up peak, independently of iteration count.
            self.assertLessEqual(rows[2][4], rows[1][4], 'fixed local slots must bound peak allocation')

    def test_legacy_numeric_methods_and_bytes_field(self):
        self.check_lifetimes('''
class Counter:
    def __init__(self, value):
        self.value = value

    def advance(self, delta: int):
        self.value += delta
        return self.value

class Tag:
    def __init__(self, code: bytes):
        self.code = code

def run(n: int) -> int:
    total = 0
    for i in range(n):
        counter = Counter(i)
        alias = counter
        alias.advance(3)
        tag = Tag(b'ok')
        total += counter.value + len(tag.code)
    return total
''')

    def test_return_alias_rebind_self_assignment_and_discard(self):
        self.check_lifetimes('''
def replace(p: Point, q: Point):
    p = Point(19)
    return q

def run(n: int) -> int:
    total = 0
    p = Point(0)
    for i in range(n):
        p = maker(i)
        p = p
        alias = identity(p)
        p = Point(23)
        kept = replace(alias, alias)
        nested = identity(identity(kept))
        keyword = second(b=nested, a=p)
        total += keyword.x + p.x
        maker(i)
        identity(keyword)
    return total
''')

    def test_returns_across_separate_objects(self):
        self.check_lifetimes('''
def run(n: int) -> int:
    total = 0
    for i in range(n):
        p = identity(maker(i))
        total += p.x
    return total
''', separate=True)

    def test_tuple_swap_preserves_aliases_in_loop(self):
        self.check_lifetimes('''
def swapped(x: int) -> int:
    p = Point(x)
    q = Point(x + 3)
    alias = identity(p)
    for j in range(4):
        p, q = q, p
        p.x = p.x + 1
    total = p.x + q.x + alias.x
    p = q
    p, q = q, p
    p.x = p.x + 7
    return total + q.x + alias.x

def run(n: int) -> int:
    total = 0
    for i in range(n):
        total += swapped(i)
    return total
''')

    def test_constructor_failure_releases_partially_initialized_struct(self):
        self.check_lifetimes('''
class Early:
    def __init__(self, seed, divisor):
        self.x = 100 // divisor
        self.y = seed

class Late:
    def __init__(self, seed, divisor):
        self.x = seed
        self.y = 100 // divisor

def construct(seed: int) -> int:
    retained = Point(seed)
    total = 0
    try:
        a = Early(seed, 0)
        total += a.x
    except ZeroDivisionError:
        total += retained.x + 1
    try:
        b = Late(seed, 0)
        total += b.y
    except ZeroDivisionError:
        total += retained.x + 2
    a = Early(seed, 2)
    b = Late(seed, 4)
    return total + a.x + a.y + b.x + b.y

def run(n: int) -> int:
    total = 0
    for i in range(n):
        total += construct(i)
    return total
''')

    def test_exception_during_argument_and_callee_unwind(self):
        self.check_lifetimes('''
def fail(x: int):
    p = Point(x)
    if x >= 0:
        raise ValueError()
    return p

def explode(p: Point) -> int:
    q = identity(p)
    if p.x >= 0:
        raise IndexError()
    return 0

def run(n: int) -> int:
    total = 0
    for i in range(n):
        p = Point(i)
        if False and explode(maker(i)):
            total += 100
        try:
            second(maker(i), fail(i))
        except ValueError:
            total += p.x
        try:
            explode(identity(p))
        except IndexError:
            total += p.x + 1
    return total
''')

    def test_try_return_break_continue_and_recursive_return(self):
        self.check_lifetimes('''
def recurse(p: Point, depth: int):
    q = identity(p)
    if depth == 0:
        return q
    return recurse(q, depth - 1)

def early(x: int):
    p = Point(x)
    try:
        return recurse(p, 3)
    except ValueError:
        return Point(0)

def run(n: int) -> int:
    total = 0
    for i in range(n):
        for j in range(3):
            try:
                p = early(i)
                if j == 0:
                    continue
                total += p.x
                break
            except ValueError:
                total += 100
    return total
''')


if __name__ == '__main__':
    unittest.main()
