"""Pure generation, binding boundaries and public numeric builtin contracts."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
from ail_syntax import translate
import ail_builtin_api as api
import pyfunc as compiler
import cruntime


def generate(source):
    return compiler.to_c(translate(source, module=True), library=True, strict=True)


class ProfileCandidateTests(unittest.TestCase):
    def test_hex_positive_boundaries_and_runtime_code(self):
        for expression in ('0', '1', '-1', '9223372036854775807', '-9223372036854775808', 'n'):
            with self.subTest(expression=expression):
                code = generate('fn probe(n:int)->str {let r:str=hex(' + expression + ');return r;}')
                self.assertIn('ail_int_hex', code)
                self.assertIn('UINT64_C(0) - magnitude', code)
                self.assertIn('uint16_t reversed[16]', code)
        self.assertTrue(generate('fn hex(n:int)->int {return n;} fn probe(n:int)->int {return hex(n);}'))

    def test_callable_parameter_and_local_hex_shadow(self):
        sources = [
            'fn apply(hex:Callable[[int],int],n:int)->int {return hex(n);}',
            'fn target(n:int)->int {return n+1;} fn probe(n:int)->int {let hex:Callable[[int],int]=target;return hex(n);}',
        ]
        for source in sources:
            with self.subTest(source=source):
                code = generate(source)
                self.assertNotIn('ail_int_hex', code)

    def test_float_sort_positive_domains(self):
        for values in ('', '1.0', '2.0,1.0', '-0.0,0.0', 'float("inf"),float("-inf")',
                       'float("nan")', '1.0,float("nan")'):
            with self.subTest(values=values):
                code = generate('fn probe()->int {let xs:list[float]=[' + values + '];xs.sort();return len(xs);}')
                self.assertIn('ail_flist_sort', code)
                self.assertLess(code.index('if (isnan(L->p[i]))'), code.index('qsort(L->p, (size_t)L->n, sizeof *L->p, ail_flist_compare)'))
                self.assertIn('return (a > b) - (a < b);', code)

    def test_type_arity_borrowed_and_value_refusals(self):
        sources = [
            'fn probe()->str {return hex();}',
            'fn probe(n:int)->str {return hex(n,n);}',
            'fn probe(n:float)->str {return hex(n);}',
            'fn probe(n:str)->str {return hex(n);}',
            'fn probe(n:int)->str {return hex(value=n);}',
            'fn probe(xs:list[float])->int {xs.sort();return len(xs);}',
            'fn probe()->int {let xs:list[float]=[1.0];xs.sort(1);return len(xs);}',
            'fn probe()->int {let xs:list[float]=[1.0];return xs.sort();}',
        ]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(compiler.Unsupported):
                generate(source)

    def test_api_ownership_and_effect_boundaries(self):
        hexadecimal = api.query('hex')['entries'][0]
        self.assertTrue(hexadecimal['signature_known'])
        self.assertFalse(hexadecimal['binding_verified'])
        self.assertFalse(hexadecimal['runtime_verified'])
        self.assertEqual(len(hexadecimal['overloads']), 1)
        hx = hexadecimal['overloads'][0]
        self.assertEqual([(p['name'], p['type']) for p in hx['parameters']], [('value', 'int')])
        self.assertEqual(hx['result'], dict(type='str', ownership='owned_snapshot', access='readonly'))
        self.assertEqual(hx['context'], 'expression')
        self.assertTrue(any('INT64_MIN' in item for item in hx['constraints']))
        floating_sort = api.query('list[float].sort')['entries'][0]
        self.assertTrue(floating_sort['signature_known'])
        self.assertFalse(floating_sort['binding_verified'])
        self.assertFalse(floating_sort['runtime_verified'])
        self.assertEqual(len(floating_sort['overloads']), 1)
        sort = floating_sort['overloads'][0]
        self.assertEqual(sort['parameters'], [])
        self.assertEqual(sort['result'], dict(type='void', ownership='none', access='none'))
        self.assertEqual(sort['context'], 'statement')
        self.assertTrue(sort['receiver']['mutable'])
        self.assertEqual(sort['receiver']['type'], 'list[float]')
        self.assertTrue(any('NaN' in item for item in sort['constraints']))
        self.assertTrue(any('qsort' in item for item in sort['constraints']))
        self.assertIn('ValueError', floating_sort['known_errors'])


if __name__ == '__main__':
    unittest.main()
