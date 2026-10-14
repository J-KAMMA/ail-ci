"""R735 ordinary owned join returns: complete output and ownership boundaries."""
import os
import shutil
import sys
import unittest

import ail_syntax
import test_ail_callable_owned_results as owned
import test_ail_callable_values as callbacks
import test_ail_c_objects as support
import test_ail_exception_resources as resources
import test_ail_finally as finally_support
import test_ail_owned_join_take as take


PROVIDER = '''
def direct(n: int, text: str, sep: str) -> str:
    values: list[str] = [text for i in range(n)]
    return sep.join(values)
def held(n: int, text: str, sep: str) -> str:
    values: list[str] = [text for i in range(n)]
    result: str = sep.join(values)
    return result
def sliced(n: int, text: str, sep: str) -> str:
    values: list[str] = [text for i in range(n)]
    return sep.join(values)[1:-1]
def final(n: int, text: str, sep: str) -> str:
    values: list[str] = [text for i in range(n)]
    try:
        return sep.join(values)
    finally:
        scratch: str = direct(17, "overwrite", "!")
def separator() -> str:
    print("separator")
    return "|"
def items() -> list[str]:
    print("items")
    return ["a", "b"]
def ordered() -> str:
    return separator().join(items())
'''

ENTRY = '''
def main() -> int:
    write_bytes(sys.argv[1], b"")
    for text in ["abc", "éÿ", "日😀", "a\\x00b", ""]:
        for n in [0, 1, 65537]:
            first: str = direct(n, text, "|")
            alias: str = first
            scratch: str = direct(31, "next😀", "-")
            print(first)
            print(alias)
            print(held(n, text, "|"))
            print(sliced(n, text, "|"))
            print(final(n, text, "|"))
            append_bytes(sys.argv[1], first.encode("utf-8"))
            if len(first) > 0:
                print(first[0])
                print(first[-1])
    print(direct(3, "日", "😀\\x00"))
    print(ordered())
    return 0
'''

FAILURE = '''
def checked(n: int) -> list[str]:
    scratch: list[str] = ["日😀" * 8193 for i in range(3)]
    if n % 2 == 0:
        raise ValueError()
    return scratch
def produce(n: int) -> str:
    return "|".join(checked(n))
def run(n: int) -> int:
    saved: str = "saved😀"
    total: int = 0
    for i in range(n):
        try:
            saved = produce(i)
        except ValueError:
            total += len(saved)
    return total + len(saved)
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class OrdinaryJoinReturnTests(unittest.TestCase):
    def setUp(self):
        support.CObjectTests.setUp(self)
        self.addTypeEqualityFunc(bytes, lambda a,b,msg=None: self.assertTrue(
            a==b, msg or f'whole output differs: {len(a)} vs {len(b)} bytes'))
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    snapshot = support.CObjectTests.snapshot
    compare_program = owned.CallableOwnedResultTests.compare_program
    generated = take.OwnedJoinTakeTests.generated
    host = take.OwnedJoinTakeTests.host
    maxDiff = 1200

    def test_complete_cpython_output_retention_fallbacks_and_evaluation_order(self):
        self.compare_program(PROVIDER + ENTRY, 'ordinary_join_full')

    def test_relocated_source_free_library_print_encode_and_index(self):
        provider = self.write('ordinary_provider.ail', finally_support.brace_source(PROVIDER))
        obj = self.root / 'ordinary_provider.o'
        built = self.command('compile-module', provider, '-o', obj)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        provider.unlink()
        directory = self.root / '移動 ordinary'
        directory.mkdir()
        moved = directory / obj.name
        shutil.move(str(obj), moved)
        shutil.move(str(obj) + '.json', str(moved) + '.json')
        before = self.snapshot(moved)
        self.compare_program(ENTRY, 'ordinary_join_relocated', '--object', moved,
                             reference_source=PROVIDER + ENTRY)
        self.assertEqual(self.snapshot(moved), before)

    def test_full_units_bytesflag_and_removed_return_allocation(self):
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
  uint64_t a=resource_alloc_calls[6], b=resource_alloc_bytes[6];
  ail_str result=run(sizes[i]);
  printf("%llu %llu %lld %d ",(unsigned long long)(resource_alloc_calls[6]-a),
         (unsigned long long)(resource_alloc_bytes[6]-b),
         (long long)result.n,(int)result.bytes);
  for(int64_t j=0;j<result.n;j++)printf("%04x",(unsigned)ail_chr(result,j));
  puts(""); resource_free((void*)result.p); DRAIN
  if(live || live_bytes)return 5; GUARDS
 }
 return 0;
}
'''
        namespace = {}
        exec(callbacks.oracle_source(PROVIDER), namespace)
        for text, flag in [('abc', 1), ('éÿ', 0), ('日😀', 0), ('a\x00b', 1)]:
            measurements = {}
            for function in ('direct', 'held'):
                body = ('    return "|".join(values)\n' if function == 'direct' else
                        '    result: str = "|".join(values)\n    return result\n')
                source = (f'\ndef run(n: int) -> str:\n'
                          f'    values: list[str] = [{text!r} for i in range(n)]\n' + body)
                lines = self.host(self.generated(source), host,
                                  f'ordinary_counts_{function}_{flag}_{ord(text[0])}')
                measurements[function] = []
                self.assertEqual(len(lines), 3)
                for n, line in zip((0, 1, 65537), lines, strict=True):
                    allocations, allocated, length, actual_flag, units = line.split(' ', 4)
                    value = namespace[function](n, text, '|').encode('utf-8')
                    expected = ''.join(f'{b:04x}' for b in value)
                    self.assertEqual(int(length), len(value))
                    self.assertTrue(units == expected,
                                    f'{function}/{n}: full UTF-8 mismatch ({len(units)} hex chars)')
                    if function == 'direct' and n:
                        self.assertEqual(int(actual_flag), flag)
                    measurements[function].append((int(allocations), int(allocated)))
            # The fallback allocates one return copy of the UTF-8 bytes.
            direct, held = measurements['direct'][-1], measurements['held'][-1]
            units = len(namespace['direct'](65537, text, '|').encode('utf-8'))
            self.assertEqual(held[0] - direct[0], 1, (text, direct, held))
            self.assertEqual(held[1] - direct[1], units, (text, direct, held))

    def test_separator_field_snapshot_survives_iterable_mutation(self):
        source='''struct Holder {separator:str;}
impl Holder {
 fn items(self)->list[str] {self.separator="new separator";return ["a","b"];}
 fn joined(self)->str {return self.separator.join(self.items());}
}
fn main()->int {let holder=Holder("|");print(holder.joined());print(holder.separator);return 0;}
'''
        executable=support.CObjectTests.ail_build(self,'ordinary_field_snapshot',source)
        support.CObjectTests.check_run(self,executable,'a|b\nnew separator\n')
    def test_checked_slist_marker_preserves_literal_return_validation(self):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c,Unsupported
            for body in ('return []','return ["a", "日"]'):
                to_c('def items() -> __ail_checked_slist__:\n    '+body+'\n',
                     name='items',strict=True,library=True)
            for body in ('return [1,2]','return ["a",1]'):
                with self.subTest(body=body),self.assertRaises(Unsupported):
                    to_c('def items() -> __ail_checked_slist__:\n    '+body+'\n',
                         name='items',strict=True,library=True)
        finally:
            sys.path.pop(0)
    def test_repeated_exception_keeps_saved_output_and_releases_frames(self):
        resources.ExceptionResourceTests.check_resources(
            self, callbacks.oracle_source(FAILURE), sizes=(0, 1, 2, 17, 101),
            native_source=ail_syntax.translate(finally_support.brace_source(FAILURE), module=True))


if __name__ == '__main__':
    unittest.main()