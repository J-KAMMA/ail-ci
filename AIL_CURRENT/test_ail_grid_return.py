"""Rectangular integer return contracts through both syntax and native marshalling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import ail_chatgpt
import ail_sdk
import test_ail_source_check as source_support

GRID = '''fn grid(rows:int,cols:int)->list[list[int]] {
 let result=[];
 for i in range(rows) {
  let row=[];
  for j in range(cols) {row.append(i*100003+j-17);}
  result.append(row);
 }
 return result;
}'''
WORKER = '''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(Path(sys.argv[1])/"python/pkg-v12"))
from ail_syntax import translate
from pyfunc import compile_fn
source=sys.argv[2]
if sys.argv[3]=="ail":source=translate(source,module=True)
function=compile_fn(source,strict=True)
print(json.dumps([function(*args) for args in json.loads(sys.argv[4])]))
'''

class GridReturnTests(unittest.TestCase):
    setUp = source_support.SourceCheckTests.setUp
    source = source_support.SourceCheckTests.source
    check = source_support.SourceCheckTests.check

    def test_checked_grid_declaration_and_wrong_shapes(self):
        status,report=self.check(self.source(GRID),'--library','--interface')
        self.assertEqual(status,0,report)
        self.assertEqual(report['interface']['functions'][0]['returns'],'list[list[int]]')
        for source in ('fn grid()->list[list[int]] {return 1;}',
                       'fn grid()->list[list[int]] {let result=[[(1,2)]];return result;}',
                       'fn grid()->list[list[float]] {let result=[[1.0]];return result;}',
                       'fn grid()->list[list[int]] {let result=[];}'):
            with self.subTest(source=source):self.assertEqual(self.check(self.source(source),'--library')[0],1)

    def worker(self,source,syntax,inputs,root=None):
        with tempfile.TemporaryDirectory(prefix='ail-grid-cache-') as cache:
            return subprocess.run([sys.executable,'-X','utf8','-B','-c',WORKER,
                                   str(root or ail_chatgpt.ROOT),source,syntax,json.dumps(inputs)],
                                  env=dict(os.environ,PIPE_CACHE=cache,PYTHONDONTWRITEBYTECODE='1'),
                                  capture_output=True,timeout=120)

    def test_native_grid_matches_independent_rows_and_spill(self):
        inputs=[(-1,3),(3,-1),(-(1<<63),3),(1,-(1<<63)),(0,(1<<63)-1),(0,0),(0,7),(1,0),(2,0),(65,0),(1,1),(8,8),(5,13),(257,17),(2,1),(0,0)]
        expected=[[[i*100003+j-17 for j in range(cols)] for i in range(rows)] for rows,cols in inputs]
        python='''def grid(rows:int,cols:int)->list[list[int]]:
 result=[]
 for i in range(rows):
  row=[]
  for j in range(cols):row.append(i*100003+j-17)
  result.append(row)
 return result
'''
        sdk = self.root / 'moved-sdk'
        ail_sdk.export_sdk(ail_chatgpt.ROOT, sdk)
        for source,syntax in ((GRID,'ail'),(python,'python')):
            with self.subTest(syntax=syntax):
                result=self.worker(source,syntax,inputs,root=sdk)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
                self.assertEqual(json.loads(result.stdout),expected)
                self.assertEqual(result.stderr,b'')

    def test_spilled_result_does_not_execute_twice(self):
        source=GRID.replace(' let result=[];', ' print("once"); let result=[];')
        result=self.worker(source,'ail',[(5,13)])
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        lines=result.stdout.splitlines()
        self.assertEqual(lines.count(b'once'),1)
        payloads=[line for line in lines if line!=b'once']
        self.assertEqual(len(payloads),1)
        self.assertEqual(json.loads(payloads[0]),[[[i*100003+j-17 for j in range(13)] for i in range(5)]])
    def test_ragged_grid_traps_instead_of_losing_shape(self):
        source='fn grid(n:int)->list[list[int]] {let result=[[1],[2,3]];return result;}'
        result=self.worker(source,'ail',[(0,)])
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,b'')
        self.assertIn(b'rows are not all the same length',result.stderr)

if __name__=='__main__':unittest.main()