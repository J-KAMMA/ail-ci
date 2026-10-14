"""Static helper definitions must not be confused with calls or unrelated frames."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import row_cpu_profile as profile


SOURCE = '''static void *ail_obj_retain(void *v) {
 if (v) { /* } */ return v; } return 0;
}
static void ail_obj_release(void *v) { (void)v; }
static Node *ail_obj_store_Node(Node **s, Node *v, int adopt) {
 ail_obj_retain(v); ail_obj_release(*s); *s=v; return v;
}
void work(Node **s,Node *v) {
 if (ail_obj_store_Node(s,v,0)) { other(); }
 while (ail_obj_store_Node(s,v,0),keep()) { other(); }
 const char *text="static void ail_obj_store_fake(void) { }";
 /* static void ail_obj_store_comment(void) { } */
}
'''


class ProfileParserTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='ail-pc-parser-')
        self.addCleanup(temporary.cleanup)
        self.source=Path(temporary.name)/'input.c';self.source.write_text(SOURCE)

    def test_calls_strings_comments_and_nested_braces_do_not_create_helpers(self):
        ranges=profile.helper_ranges(self.source)
        self.assertEqual([(item['helper'],item['first'],item['last']) for item in ranges],
                         [('ail_obj_retain',1,3),('ail_obj_release',4,4),('ail_obj_store_Node',5,7)])

    def test_forward_declarations_are_excluded(self):
        self.source.write_text('static void *ail_obj_retain(void *);\n'+SOURCE)
        self.assertEqual(len(profile.helper_ranges(self.source)),3)

    def test_both_function_name_and_definition_line_are_required(self):
        stdout=(f'0x1\nail_bytearray_extend_int\n{self.source}:6\n'
                f'0x2\nail_obj_store_Node\n{self.source}:6\n'
                f'0x3\nail_obj_store_Node\n{self.source}:9\n').encode()
        with patch.object(profile,'command',return_value=SimpleNamespace(stdout=stdout)):
            classified=profile.symbolize(Path('binary'),self.source,{1,2,3},Path('addr2line'),{})
        self.assertEqual(classified[1]['helpers'],[])
        self.assertEqual(classified[2]['helpers'],['ail_obj_store_Node'])
        self.assertEqual(classified[3]['helpers'],[])


if __name__=='__main__':unittest.main()
