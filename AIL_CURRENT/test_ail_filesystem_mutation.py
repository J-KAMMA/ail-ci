"""Filesystem writes stay inside owned fixtures and match independent os operations."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

PROBE=r'''fn main()->int {
 try {
  if sys.argv[1]=="mkdir" { make_dir(sys.argv[2]); }
  elif sys.argv[1]=="unlink" { remove_file(sys.argv[2]); }
  elif sys.argv[1]=="rmdir" { remove_dir(sys.argv[2]); }
  else { replace_path(sys.argv[2],sys.argv[3]); }
  print("ok");return 0;
 } except ValueError { print("ValueError");return 4; }
 except OSError { print("OSError");return 3; }
}'''
ROUNDTRIP=r'''fn main()->int {
 let folder=sys.argv[1];make_dir(folder);
 let first=folder+"/stage.bin";let final=folder+"/result.bin";
 write_bytes(first,read_bytes(sys.argv[2]));write_bytes(final,b"old");
 replace_path(first,final);
 if path_exists(first)!=0 or path_exists(final)!=1 { return 9; }
 write_stdout_bytes(read_bytes(final));remove_file(final);remove_dir(folder);return 0;
}'''
SNAPSHOT=r'''struct PathBox { path:str; calls:int; }
fn destination(box:PathBox,target:str)->str { box.path="missing source";box.calls+=1;return target; }
fn main()->int {
 let box=PathBox(sys.argv[1],0);replace_path(box.path,destination(box,sys.argv[2]));
 write_stdout_bytes((str(box.calls)+"\n").encode("utf-8"));write_stdout_bytes(read_bytes(sys.argv[2]));return 0;
}'''

class FilesystemMutationTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def tree(self,root):
        return sorted((p.relative_to(root).as_posix(),'link:'+os.readlink(p) if p.is_symlink()
                       else 'directory' if p.is_dir() else p.read_bytes().hex()) for p in root.rglob('*'))

    def test_independent_filesystem_oracles_and_failures(self):
        exe=build(self,'probe',PROBE)
        cases=(('mkdir','new',''),('mkdir','existing',''),('mkdir','file',''),('mkdir','absent/child',''),
               ('unlink','file',''),('unlink','existing',''),('unlink','absent',''),
               ('rmdir','empty',''),('rmdir','existing',''),('rmdir','file',''),('rmdir','absent',''),
               ('replace','file','target'),('replace','file','new'),('replace','file','existing'),
               ('replace','existing','target'),('replace','empty','empty2'),('replace','absent','target'),
               ('replace','file','absent/child'),('replace','file','file'))
        for i,(operation,src,dst) in enumerate(cases):
            with self.subTest(operation=operation,source=src,destination=dst):
                actual=self.root/f'actual{i}';reference=self.root/f'reference{i}'
                for root in (actual,reference):
                    root.mkdir();(root/'existing').mkdir();(root/'existing/kept').write_bytes(b'untouched')
                    (root/'empty').mkdir();(root/'empty2').mkdir()
                    (root/'file').write_bytes(b'new\0\xff');(root/'target').write_bytes(b'old')
                try:
                    if operation=='mkdir':os.mkdir(reference/src)
                    elif operation=='unlink':os.unlink(reference/src)
                    elif operation=='rmdir':os.rmdir(reference/src)
                    else:os.replace(reference/src,reference/dst)
                    expected=(0,b'ok\n')
                except OSError:expected=(3,b'OSError\n')
                result=subprocess.run([str(exe),operation,str(actual/src),str(actual/dst)],capture_output=True,timeout=10)
                self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n')),expected,result.stderr)
                self.assertEqual(result.stderr,b'');self.assertEqual(self.tree(actual),self.tree(reference))
                markers=list(actual.rglob('kept'));self.assertEqual(len(markers),1)
                self.assertEqual(markers[0].read_bytes(),b'untouched')

    def test_unicode_roundtrip_snapshot_and_source_free_void(self):
        exe=build(self,'roundtrip',ROUNDTRIP)
        data=bytes(range(256))*257+b'\0\xff'
        path=self.root/'input.bin';path.write_bytes(data)
        folder=self.root/'日本語 😀 output'
        result=subprocess.run([str(exe),str(folder),str(path)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,data,b''))
        self.assertFalse(folder.exists());self.assertEqual(path.read_bytes(),data)
        snapshot=build(self,'snapshot',SNAPSHOT)
        first=self.root/'first 日本語😀';final=self.root/'last 日本語😀'
        first.write_bytes(b'payload');final.write_bytes(b'old')
        result=subprocess.run([str(snapshot),str(first),str(final)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'1\npayload',b''))
        self.assertFalse(first.exists());self.assertEqual(final.read_bytes(),b'payload')
        provider='fn create(path:str)->void { make_dir(path); }\nfn discard(path:str)->void { remove_dir(path); }'
        obj=self.ail_build('provider',provider,library=True)
        moved=self.root/'moved FS 😀';moved.mkdir();target=moved/obj.name
        shutil.move(obj,target);shutil.move(str(obj)+'.json',str(target)+'.json');before=self.snapshot(target)
        entry='fn main()->int { create(sys.argv[1]); print(is_dir(sys.argv[1])); discard(sys.argv[1]); return 0; }'
        linked=self.ail_build('entry',entry,target)
        result=subprocess.run([str(linked),str(folder)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'1\n',b''))
        self.assertFalse(folder.exists());self.assertEqual(self.snapshot(target),before)

    def test_nul_empty_and_nonreturning_contracts(self):
        source=r'''fn main()->int { let caught:int=0;
 try { make_dir("a\0b"); } except ValueError { caught+=1; }
 try { remove_file("a\0b"); } except ValueError { caught+=1; }
 try { remove_dir("a\0b"); } except ValueError { caught+=1; }
 try { replace_path(sys.argv[1],"a\0b"); } except ValueError { caught+=1; }
 try { replace_path("a\0b",sys.argv[1]); } except ValueError { caught+=1; }
 try { make_dir(""); } except OSError { caught+=1; }
 try { remove_file(""); } except OSError { caught+=1; }
 try { remove_dir(""); } except OSError { caught+=1; }
 print(caught);return 0;}'''
        exe=build(self,'bounds',source);path=self.root/'kept';path.write_bytes(b'kept')
        result=subprocess.run([str(exe),str(path)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'8\n',b''))
        self.assertEqual(path.read_bytes(),b'kept')
        statements=('make_dir();','make_dir(1);','make_dir("x",1);','remove_file(path="x");',
                    'remove_dir(1.5);','replace_path("x");','replace_path("x",1);',
                    'let result=make_dir("x");','print(remove_file("x"));','return replace_path("x","y");')
        for i,statement in enumerate(statements):
            path=self.write(f'bad{i}.ail','fn main()->int { '+statement+'return 0; }');out=self.root/f'bad{i}'
            result=self.command('compile',path,'-o',out)
            self.assertNotEqual(result.returncode,0);self.assertNotIn(b'Traceback',result.stderr)
            self.assertFalse(out.exists());self.assertFalse(out.with_suffix('.exe').exists())

    def test_symlink_entries_preserve_targets_when_available(self):
        exe=build(self,'links',PROBE)
        destination=self.root/'target';destination.mkdir();(destination/'kept').write_bytes(b'kept')
        link=self.root/'directory link'
        try:os.symlink(destination,link,target_is_directory=True)
        except OSError as error:self.skipTest('directory symlink unavailable: '+str(error))
        result=subprocess.run([str(exe),'unlink',str(link)],capture_output=True,timeout=10)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'ok\n',b''))
        self.assertFalse(link.is_symlink());self.assertEqual((destination/'kept').read_bytes(),b'kept')

    @unittest.skipUnless(os.name=='nt','Windows directory junction contract')
    def test_windows_junction_is_removed_without_target_contents(self):
        import ctypes
        create=getattr(__import__('_winapi'),'CreateJunction',None)
        if create is None:self.skipTest('native Python junction fixture unavailable')
        target=self.root/'junction target';target.mkdir();(target/'kept').write_bytes(b'kept')
        link=self.root/'junction entry'
        self.assertTrue(target.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue(link.absolute().is_relative_to(self.root.resolve()))
        create(str(target),str(link))
        exe=build(self,'junction',PROBE)
        result=subprocess.run([str(exe),'unlink',str(link)],capture_output=True,timeout=10)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'ok\n',b''))
        self.assertFalse(link.exists());self.assertEqual((target/'kept').read_bytes(),b'kept')

    def test_function_and_callable_shadows_keep_user_behavior(self):
        for i,source in enumerate(('fn make_dir(n:int)->int { return n+7; } fn main()->int { print(make_dir(3)); return 0; }',
                                   'fn other(n:int)->int { return n+7; } fn main()->int { let remove_file:Callable[[int],int]=other; print(remove_file(3)); return 0; }')):
            exe=build(self,f'shadow{i}',source)
            result=subprocess.run([str(exe)],capture_output=True,timeout=10)
            self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'10\n',b''))

if __name__=='__main__':unittest.main()