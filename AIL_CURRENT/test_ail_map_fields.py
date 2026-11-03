"""Deep owned dictionary fields and invalid mutations."""
import ast
import re
import subprocess
import unittest
from ail_syntax import translate
import test_ail_c_objects as support


def build(case,name,source,modules=()):
    paths=[]; seen=set()
    def include(module):
        if module in seen:return
        seen.add(module)
        text=(support.ROOT/'language_examples'/(module+'.ail')).read_text(encoding='utf8')
        for dependency in re.findall(r'^use (\w+);',text,re.M):include(dependency)
        paths.append(case.write(module+'.ail',text))
    for module in modules:include(module)
    ast.parse(source)
    path=case.write(name+'.ail',source);output=case.root/name
    result=case.command('compile',path,*(arg for p in paths for arg in ('--module',p)),'-o',output)
    case.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
    return output if output.exists() else output.with_suffix('.exe')


SOURCE='import sys\n\nclass Maps:\n\n    def __init__(self, counts: dict[str, int], texts: dict[str, str], blobs: dict[str, bytes]):\n        self.counts = counts\n        self.texts = texts\n        self.blobs = blobs\n\ndef relay(box: Maps) -> dict[str, int]:\n    return box.counts\n\ndef receiver(box: Maps) -> Maps:\n    print(\'receiver\')\n    return box\n\ndef rhs() -> dict[str, int]:\n    print(\'rhs\')\n    return {\'once\': 7}\n\ndef fail() -> dict[str, int]:\n    raise ValueError\n    empty: dict[str, int] = {}\n    return empty\n\ndef main() -> int:\n    counts: dict[str, int] = {}\n    texts: dict[str, str] = {}\n    blobs: dict[str, bytes] = {}\n    n = int(sys.argv[1])\n    for i in range(n):\n        key = str(i) + \'\\x00😀\'\n        counts[key] = i\n        texts[key] = key\n        blobs[key] = key.encode()\n    box = Maps(counts, texts, blobs)\n    counts.clear()\n    texts.clear()\n    blobs.clear()\n    c = box.counts\n    t = box.texts\n    b = box.blobs\n    box.counts = box.counts\n    box.texts = {}\n    box.blobs = {}\n    for i in range(257):\n        churn = Maps({}, {\'廃棄\': \'😀\' + str(i)}, {\'廃棄\': bytes(8193)})\n    output: list[str] = []\n    for key, value in c.items():\n        output.append(key.encode().hex() + \':\' + str(value) + \':\' + t[key].encode().hex() + \':\' + b[key].hex())\n    print(\'\\n\'.join(output))\n    c.clear()\n    if len(box.counts) != n:\n        return 8\n    try:\n        box.counts = {\'bad\': 10 // 0}\n    except ZeroDivisionError:\n        caught: int = 1\n    if len(box.counts) != n:\n        return 9\n    returned = relay(box)\n    if len(returned) != n:\n        return 10\n    keys = box.counts.keys()\n    values = box.counts.values()\n    copy = box.counts.copy()\n    if len(keys) != n or len(values) != n or len(copy) != n:\n        return 11\n    if False:\n        box.counts = fail()\n    alias = box\n    receiver(box).counts = rhs()\n    if alias.counts.get(\'once\', 0) != 7 or alias.counts[\'once\'] != 7:\n        return 12\n    box = Maps({}, {}, {})\n    if len(returned) != n:\n        return 13\n    box.counts = {\'first\': 1, \'second\': 2}\n    seen: list[str] = []\n    for key, value in box.counts.items():\n        seen.append(key + str(value))\n        box.counts = {\'changed\': 9}\n    if \'|\'.join(seen) != \'first1|second2\':\n        return 14\n    box.counts = {\'first\': 1, \'second\': 2}\n    seen = []\n    for key in box.counts:\n        seen.append(key)\n        box.counts = {\'changed\': 9}\n    if \'|\'.join(seen) != \'first|second\':\n        return 15\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


class MapFieldTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def test_owned_snapshot_selfreplacement_failed_rhs_and_retention(self):
        executable=build(self,'map_fields',SOURCE)
        for n in (0,1,16,8191,8192,8193):
            rows=[]
            for i in range(n):
                key=str(i)+'\0😀'; h=key.encode().hex();rows.append(f'{h}:{i}:{h}:{h}')
            expected=('\n'.join(rows)+'\nrhs\nreceiver\n').encode()
            result=subprocess.run([str(executable),str(n)],capture_output=True,timeout=120)
            self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,expected,b''))

    def test_invalid_mutations_and_wrong_field_types_refused_after_parse(self):
        for i,statement in enumerate(('box.counts[1]=1;','del box.counts[1];','box.counts.clear(1);',
                                     'box.counts.pop("x","bad");','box.counts.update({"x":"bad"});','box.counts.setdefault("x","bad");',
                                     'box.texts["x"]=1;','box.blobs["x"]="y";','box.counts={"x":"bad"};')):
            program='struct Maps { counts: dict[str,int]; texts: dict[str,str]; blobs: dict[str,bytes]; } fn main() -> int { let box=Maps({"x":1},{"x":"v"},{"x":b"v"}); '+statement+' return 0; }'
            ast.parse(program);path=self.write('bad'+str(i)+'.ail',program);output=self.root/('bad'+str(i))
            result=self.command('compile',path,'-o',output);self.assertNotEqual(result.returncode,0,statement)
            self.assertNotIn(b'Traceback',result.stderr);self.assertFalse(output.exists());self.assertFalse(output.with_suffix('.exe').exists())


if __name__=='__main__':unittest.main()
