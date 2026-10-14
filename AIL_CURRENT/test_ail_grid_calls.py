"""Owned value grids across compiled calls; full output, unwind and type boundaries."""
import importlib.util
import os
import shutil
import subprocess
import unittest

import test_ail_c_objects as support
from test_ail_grid_return import GRID

LIBRARY=GRID+'''
fn relay(rows:int,cols:int)->list[list[int]] {let result=grid(rows,cols);return result;}
fn fail_grid()->list[list[int]] {raise ValueError;return [];}
fn mark(value:int)->int {print(value);return value;}
'''
ENTRY='''fn main()->int {
 let rows=int(sys.argv[1]); let cols=int(sys.argv[2]);
 let g=relay(cols=mark(cols),rows=mark(rows));
 try {g=fail_grid();} except ValueError {print("caught");}
 print(len(g));
 for row in g {
  let parts:list[str]=[];
  for value in row {parts.append(str(value));}
  print(" ".join(parts));
 }
 if len(g)>0 and cols>0 {
  let row=g[0]; row.append(123);
  g=grid(65,0); print(row[-1]);
 }
 return 0;
}'''

class GridCallTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_ordinary_and_separate_full_values_empty_rows_and_unwind(self):
        ordinary=self.ail_build('grid_calls',LIBRARY+ENTRY)
        library=self.write('grid_provider.ail',LIBRARY)
        source=self.write('grid_client.ail','use grid_provider;\n'+ENTRY)
        separate=self.root/'grid_separate'
        result=self.command('compile',source,'--separate','-o',separate)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        if not separate.is_file():separate=separate.with_suffix('.exe')
        for executable in (ordinary,separate):
            for rows,cols in ((0,0),(0,17),(1,0),(65,0),(8,8),(5,13),(4097,17),(-1,3),(3,-1)):
                with self.subTest(executable=executable.name,rows=rows,cols=cols):
                    values=[[i*100003+j-17 for j in range(cols)] for i in range(rows)]
                    expected=f'{cols}\n{rows}\ncaught\n{len(values)}\n'+''.join(' '.join(map(str,row))+'\n' for row in values)
                    if rows>0 and cols>0:expected+='123\n'
                    self.check_run(executable,expected,rows,cols)

    def test_value_copy_rows_are_independent_across_function_boundary(self):
        program='''fn duplicate()->list[list[int]] {
 let row=[];row.append(1);let result=[];result.append(row);result.append(row);return result;
}fn main()->int {
 let g=duplicate();let first=g[0];first.append(7);
 print(len(g[0]));print(len(g[1]));print(g[1][0]);return 0;
}'''
        self.check_run(self.ail_build('grid_value_copy',program),'2\n1\n1\n')
    def test_row_replacement_uses_handles_and_value_before_index(self):
        program=GRID+'''fn mark(value:int)->int {print(value);return value;}
fn main()->int {
 let g=grid(2,2);
 g[mark(1)]=g[mark(0)];
 let row=g[0];row.append(77);print(g[1][-1]);
 g[-1]=[];print(len(g[1]));print(len(row));return 0;
}'''
        self.check_run(self.ail_build('grid_row_replace',program),'0\n1\n77\n0\n3\n')
    def test_internal_grid_sizes_refused_before_allocation_or_access(self):
        path=support.ROOT/'python/pkg-v12/cruntime.py'
        spec=importlib.util.spec_from_file_location('grid_test_runtime',path)
        runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
        driver=r'''int main(int argc,char **argv) {
 ail_pool pool={0};int64_t slots=0,cols=0,rows=0;
 switch(atoi(argv[1])) {
 case 0: rows=-1;break;
 case 1: cols=-1;break;
 case 2: slots=-1;break;
 case 3: rows=INT64_MAX;cols=2;break;
 case 4: rows=1;cols=1;break;
 case 5: pool.n=INT64_MAX-1;pool.cap=pool.n;rows=2;break;
 case 6: pool.cap=-1;break;
 case 7: pool.n=pool.cap=INT64_MAX/2+1;ail_pool_alloc(&pool);return 0;
 }
 ail_list result=ail_grid_adopt_return(&pool,slots,cols,rows);
 ail_list_free(&result);ail_pool_free(&pool);return 0;
}'''
        headers=''.join('#include <'+name+'>\n' for name in ('stdint.h','stdio.h','stdlib.h','string.h','limits.h','setjmp.h','math.h'))
        source=self.write('invalid_grid_sizes.c',headers+runtime.emit({'GRIDRET'})+driver)
        executable=self.root/('invalid_grid_sizes.exe' if os.name=='nt' else 'invalid_grid_sizes')
        result=subprocess.run([os.environ.get('PIPE_CC') or shutil.which('gcc'),str(source),'-O2','-o',str(executable)],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        for case in range(8):
            with self.subTest(case=case):
                result=subprocess.run([str(executable),str(case)],capture_output=True,timeout=10)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(result.stdout,b'')
                self.assertIn(b'grid size' if case<7 else b'pool too large',result.stderr)
    def test_reserved_loop_bound_once_and_exception_preserves_prefix(self):
        program='''fn limit()->int {print("limit");return 17;}
fn item(value:int)->int {print(value);if value==2 {raise ValueError;}return value;}
fn main()->int {
 let row=[];let grid=[];
 for index in range(limit()) {row.append(index);}
 grid.append(row);print(len(grid[0]));print(grid[0][-1]);
 let partial=[];let results=[];
 try {for index in range(4) {partial.append(item(index));}}
 except ValueError {print("caught");}
 results.append(partial);print(len(results[0]));print(results[0][-1]);return 0;
}'''
        self.check_run(self.ail_build('reserve_effects',program),'limit\n17\n16\n0\n1\n2\ncaught\n2\n1\n')
    def test_optional_reservation_failure_errno_and_capacity_limits(self):
        spec=importlib.util.spec_from_file_location('reserve_runtime',support.ROOT/'python/pkg-v12/cruntime.py')
        runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
        headers=''.join('#include <'+name+'>\n' for name in ('stdint.h','stdio.h','stdlib.h','string.h','limits.h','setjmp.h','math.h','errno.h'))
        wrapper='''static int fail_next;
static void *reserve_malloc(size_t n) {if(fail_next){fail_next=0;errno=ENOMEM;return NULL;}return malloc(n);}
#define malloc reserve_malloc
'''
        driver=r'''
#undef malloc
int main(void) {
 ail_pool pool={0};int64_t first=ail_pool_alloc(&pool);
 errno=EDOM;fail_next=1;ail_pool_try_reserve(&pool,first,17);
 if(errno!=EDOM||ail_pool_at(&pool,first)->cap)return 1;
 ail_list_push(ail_pool_at(&pool,first),7);
 int64_t second=ail_pool_alloc(&pool);errno=ERANGE;
 ail_pool_try_reserve(&pool,second,-1);ail_pool_try_reserve(&pool,second,0);
 ail_pool_try_reserve(&pool,second,257);ail_pool_try_reserve(&pool,second,INT64_MAX);
 ail_pool_try_reserve(&pool,-1,17);
 if(errno!=ERANGE||ail_pool_at(&pool,second)->cap)return 2;
 ail_pool_try_reserve(&pool,second,256);
 if(errno!=ERANGE||ail_pool_at(&pool,second)->cap!=256)return 3;
 for(int64_t i=0;i<257;i++)ail_list_push(ail_pool_at(&pool,second),i);
 ail_pool_try_reserve(&pool,second,128);
 if(ail_pool_at(&pool,second)->n!=257||ail_pool_at(&pool,second)->cap<257)return 4;
 if(ail_pool_at(&pool,first)->p[0]!=7||ail_pool_at(&pool,second)->p[256]!=256)return 5;
 ail_pool_free(&pool);puts("reserved");return 0;
}'''
        source=self.write('reserve_limits.c',headers+wrapper+runtime.emit({'GRIDRET'})+driver)
        executable=self.root/('reserve_limits.exe' if os.name=='nt' else 'reserve_limits')
        result=subprocess.run([os.environ.get('PIPE_CC') or shutil.which('gcc'),str(source),'-O2','-o',str(executable)],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        self.check_run(executable,'reserved\n')
    def test_returned_grid_rebind_and_third_level_refused(self):
        for i,statement in enumerate(('g=[1];','g=1;','g=[[(1,2)]];',
                                      'let outer=[];outer.append(g);','let other=g;',
                                      'g.append(1);','g.extend([1]);','g[0]=1;','g += [1];')):
            source=self.write(f'bad_grid_{i}.ail',GRID+'fn main()->int {let g=grid(2,2);'+statement+'return 0;}')
            output=self.root/f'bad_grid_{i}'
            result=self.command('compile',source,'-o',output)
            self.assertNotEqual(result.returncode,0,statement)
            self.assertNotIn(b'Traceback',result.stderr)
            self.assertFalse(output.exists());self.assertFalse(output.with_suffix('.exe').exists())

class GridExtendTypeTests(unittest.TestCase):
    def test_grid_extend_rejects_flat_source_before_artifacts_without_type_reclassification(self):
        import sys
        from ail_syntax import translate
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from pyfront import Unsupported
            for statement in ('g.extend([1]);','let flat=[1,2];g.extend(flat);'):
                with self.subTest(statement=statement),self.assertRaises(Unsupported) as caught:
                    to_c(translate(GRID+'fn main()->int {let g=grid(2,2);'+statement+'return 0;}'),name='run',strict=True)
                self.assertFalse(hasattr(caught.exception,'type_details'))
                self.assertIn("has no method 'extend'",str(caught.exception))
            for statement in ('g.extend([[1,2]]);','g.extend([[1],[2,3]]);','g.extend([[(1,2)]]);','g.extend([]);','let rows=grid(1,2);g.extend(rows);','let rows=grid(1,3);g.extend(rows);','g.extend(g);'):
                with self.subTest(statement=statement),self.assertRaises(Unsupported):
                    to_c(translate(GRID+'fn main()->int {let g=grid(2,2);'+statement+'return 0;}'),name='run',strict=True)
        finally:
            sys.path.pop(0)

    def test_grid_row_append_and_scalar_expression_paths_stay_separate(self):
        import sys
        from ail_syntax import translate
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            for statement in ('g.append(g[0]);','g.append([]);','let row=g[0];g[1]=row;','g=grid(0,2);'):
                with self.subTest(statement=statement):
                    to_c(translate(GRID+'fn main()->int {let g=grid(2,2);'+statement+'return 0;}'),name='run',strict=True)
            from pyfront import Unsupported
            with self.assertRaises(Unsupported):
                to_c(translate('fn main()->int {let records=[(1,2)];records.extend([1]);return 0;}'),name='run',strict=True)
            for kind,literal in [('int','[1]'),('float','[1.5]'),('str','["text"]'),('bytes','[b"data"]')]:
                with self.subTest(kind=kind):
                    text='fn values()->list['+kind+'] {return '+literal+';} fn main()->int {let items='+literal+';items.extend(values());return 0;}'
                    to_c(translate(text),name='run',strict=True)
        finally:
            sys.path.pop(0)


if __name__=='__main__':unittest.main()