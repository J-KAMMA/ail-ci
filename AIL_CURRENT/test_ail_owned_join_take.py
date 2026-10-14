"""R577 fresh callback join returns: independent output and ownership accounting."""
import os
import shutil
import subprocess
import sys
import unittest

import ail_syntax
import test_ail_callable_owned_results as owned
import test_ail_callable_values as callbacks
import test_ail_c_objects as support
import test_ail_exception_resources as resources
import test_ail_finally as finally_support


PROVIDER = '''
def identity(value: str) -> str:
    return value
def empty(value: str) -> str:
    return ""
def effect(value: str) -> str:
    print(value)
    if value == "!":
        raise ValueError()
    return value + "😀"
def produce(n: int, cb: Callable[[str], str]) -> str:
    source: str = "a\\x00😀日" * (n // 4) + "a" * (n % 4)
    return "|".join([cb(x) for x in source])
def copied(n: int, cb: Callable[[str], str]) -> str:
    source: str = "a\\x00😀日" * (n // 4) + "a" * (n % 4)
    held: str = "|".join([cb(x) for x in source])
    return held
def final(n: int, cb: Callable[[str], str]) -> str:
    scratch: str = "original"
    try:
        return produce(n, cb)
    finally:
        scratch = produce(31, cb)
def slice_result(n: int, cb: Callable[[str], str]) -> str:
    return produce(n, cb)[1:-1]
def nested(n: int, cb: Callable[[str], str]) -> str:
    return "/".join([cb(produce(n, cb)) for x in "ab"])
'''

ENTRY = '''
def main() -> int:
    write_bytes(sys.argv[1], b"a\\x00\\xff")
    cb: Callable[[str], str] = identity
    first: str = produce(65537, cb)
    alias: str = first
    collected: list[str] = [first, produce(1, cb), produce(0, cb)]
    for n in [0, 1, 65537]:
        print(produce(n, cb))
        print(copied(n, cb))
        print(final(n, cb))
        print(slice_result(n, cb))
    print(nested(7, cb))
    cb = empty
    print(produce(4, cb))
    print(produce(0, cb))
    print(first)
    print(alias)
    print("+".join(collected))
    cb = effect
    try:
        print("|".join([cb(x) for x in "ab!c"]))
    except ValueError:
        print("caught")
    print(first)
    return 0
'''

FAILURE = '''
def effect(value: str) -> str:
    scratch: str = "日😀" * 65537
    if value == "!":
        raise ValueError()
    return scratch
def produce(cb: Callable[[str], str]) -> str:
    return "|".join([cb(x) for x in "ab!c"])
def run(n: int) -> int:
    cb: Callable[[str], str] = effect
    result: str = "saved😀"
    total: int = 0
    for i in range(n):
        try:
            result = produce(cb)
        except ValueError:
            total += len(result)
    return total
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class OwnedJoinTakeTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    snapshot = support.CObjectTests.snapshot
    compare_program = owned.CallableOwnedResultTests.compare_program
    maxDiff = 1200

    def generated(self, source, name='run'):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            return to_c(ail_syntax.translate(finally_support.brace_source(source), module=True),
                        name=name, strict=True, library=True)
        finally:
            sys.path.pop(0)

    def host(self, generated, host, stem):
        allocator = (support.ROOT / 'language_examples/numeric_pipeline_allocator.c').read_text()
        drain = ('for(int64_t j=0;j<ail__blk_cache_n;j++)resource_free(ail__blk_cache[j].p);'
                 'ail__blk_cache_n=0;ail__blk_cache_bytes=0;'
                 if 'ail__blk_cache_n' in generated else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){resource_free(ail__ba_cache[j]->p);resource_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)resource_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in generated else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        guards = ('if(ail_cleanup_top)return 8;' if 'ail_cleanup_top' in generated else '')
        if 'AIL_LINK_STATE(int64_t, ail_depth,' in generated:
            guards += 'if(ail_depth)return 9;'
        host = host.replace('DRAIN', drain).replace('GUARDS', guards)
        path = self.write(stem + '.c', allocator + generated + host)
        executable = self.root / (stem + ('.exe' if os.name == 'nt' else ''))
        compiler = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        built = subprocess.run([compiler, '-std=c11', '-O2', str(path), '-lm', '-o', str(executable)],
                               capture_output=True, timeout=120)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        result = subprocess.run([str(executable)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stderr), (0, b''), result.stdout[:300])
        return result.stdout.decode().splitlines()

    def test_full_cpython_unicode_retention_nested_finally_and_failure(self):
        self.compare_program(PROVIDER + ENTRY, 'take_full')

    def test_genuine_separate_and_relocated_source_free_provider(self):
        provider = self.write('take_provider.ail', finally_support.brace_source(PROVIDER))
        self.compare_program(ENTRY, 'take_separate', '--separate', '--module', provider,
                             reference_source=PROVIDER + ENTRY)
        obj = self.root / 'take_provider.o'
        built = self.command('compile-module', provider, '-o', obj)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        provider.unlink()
        directory = self.root / '移動 take'
        directory.mkdir()
        moved = directory / obj.name
        shutil.move(str(obj), moved)
        shutil.move(str(obj) + '.json', str(moved) + '.json')
        before = self.snapshot(moved)
        self.compare_program(ENTRY, 'take_relocated', '--object', moved,
                             reference_source=PROVIDER + ENTRY)
        self.assertEqual(self.snapshot(moved), before)

    def test_partial_builder_failure_releases_frame(self):
        resources.ExceptionResourceTests.check_resources(
            self, callbacks.oracle_source(FAILURE), sizes=(0, 1, 17),
            native_source=ail_syntax.translate(finally_support.brace_source(FAILURE), module=True))

    def test_owned_full_utf16_and_removed_return_copy_requests(self):
        host = r'''
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef memcpy
#undef memmove
#undef memset
int main(void) {
 int sizes[]={0,1,65537};
 for(int i=0;i<3;i++) {
  uint64_t a=resource_alloc_calls[6], c=resource_copy_bytes[6];
  ail_str result=run(sizes[i]);
  printf("%llu %llu %lld ",(unsigned long long)(resource_alloc_calls[6]-a),
         (unsigned long long)(resource_copy_bytes[6]-c),(long long)result.n);
  for(int64_t j=0;j<result.n;j++)printf("%04x",(unsigned)result.p[j]);
  puts(""); resource_free((void*)result.p); DRAIN
  if(live || live_bytes)return 5; GUARDS
 }
 return 0;
}
'''
        measurements = {}
        namespace = {}
        exec(callbacks.oracle_source(PROVIDER), namespace)
        for function in ('produce', 'copied'):
            source = PROVIDER + f'\ndef run(n: int) -> str:\n    return {function}(n, identity)\n'
            lines = self.host(self.generated(source), host, 'take_counts_' + function)
            measurements[function] = []
            for n, line in zip((0, 1, 65537), lines, strict=True):
                allocations, copies, length, text = line.split(' ', 3)
                value = namespace[function](n, namespace['identity']).encode('utf-8')
                expected = ''.join(f'{b:04x}' for b in value)
                self.assertEqual(int(length), len(value))
                self.assertTrue(text == expected, f'{function}/{n}: complete UTF-8 mismatch')
                measurements[function].append((int(allocations), int(copies)))
        for n, taken, copied in zip((0, 1, 65537), measurements['produce'],
                                   measurements['copied'], strict=True):
            if n:
                units = len(namespace['produce'](n, namespace['identity']).encode('utf-8'))
                self.assertEqual(copied[0] - taken[0], 1, (n, taken, copied))
                self.assertEqual(copied[1] - taken[1], units, (n, taken, copied))

    def test_arena_middle_take_top_invalidation_and_slice_capacity_fallback(self):
        source = PROVIDER + '\ndef run(n: int) -> str:\n    return produce(n, identity)\n'
        host = r'''
#undef malloc
#undef calloc
#undef realloc
#undef free
int main(void) {
 ail_sarena A={0};
 uint8_t *a=resource_malloc(8),*b=resource_malloc(8),*c=resource_malloc(8);
 a[0]=65;a[1]=0;b[0]=0xF0;b[1]=0x9F;b[2]=0x98;b[3]=0x80;b[4]=0;c[0]=67;c[1]=0;
 ail_sarena_pushn(&A,a,8);ail_sarena_pushn(&A,b,8);ail_sarena_pushn(&A,c,8);
 for(int j=0;j<AIL_SARENA_TOPS;j++){A.top[j]=b;A.tlen[j]=4;A.tcap[j]=8;A.trun[j]=1;}
 ail_str out=ail_str_join_take_owned(&A,(ail_str){.p=b,.n=4});
 if(out.p!=b||out.n!=4||A.n!=2)return 20;
 for(int j=0;j<AIL_SARENA_TOPS;j++)if(A.top[j]||A.tlen[j]||A.tcap[j]||A.trun[j])return 21;
 ail_sarena_free(&A);
 if(out.p[0]!=0xF0||out.p[1]!=0x9F||out.p[2]!=0x98||out.p[3]!=0x80)return 22;
 resource_free((void*)out.p);DRAIN
 if(live||live_bytes)return 23;
 ail_sarena B={0};uint8_t *p=resource_malloc(8);p[0]=65;p[1]=66;p[2]=67;p[3]=0;
 ail_sarena_pushn(&B,p,4);
 ail_str slice=ail_str_join_take_owned(&B,(ail_str){.p=p+1,.n=2});
 if(slice.p==p+1||B.n!=1||slice.n!=2)return 24;
 ail_str exactcap=ail_str_join_take_owned(&B,(ail_str){.p=p,.n=4});
 if(exactcap.p==p||B.n!=1||exactcap.n!=4)return 25;
 ail_sarena_free(&B);
 if(slice.p[0]!=66||slice.p[1]!=67||exactcap.p[0]!=65||exactcap.p[3]!=0)return 26;
 resource_free((void*)slice.p);resource_free((void*)exactcap.p);DRAIN
 if(live||live_bytes)return 27;GUARDS
 return 0;
}
'''
        self.assertEqual(self.host(self.generated(source), host, 'take_arena'), [])


if __name__ == '__main__':
    unittest.main()
