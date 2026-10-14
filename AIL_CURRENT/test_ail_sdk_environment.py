"""Relocated SDK bootstraps in a fresh Python environment without packages."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
import venv
import test_ail_c_objects as support
import test_ail_sdk as sdk_support

class SdkEnvironmentTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    exported=sdk_support.SdkTests.exported
    environment=sdk_support.SdkTests.environment

    def test_fresh_no_package_python_doctor_and_user_project(self):
        sdk=self.exported()
        before={p.relative_to(sdk).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sdk.rglob('*') if p.is_file()}
        location=self.root/'fresh Python 😀'
        venv.EnvBuilder(with_pip=False,system_site_packages=False).create(location)
        python=location/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        environment,marker=self.environment()
        environment.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
        def cli(*args):
            return subprocess.run([str(python),'-X','utf8','-B',str(sdk/'ail_chatgpt.py'),*map(str,args)],
                                  cwd=self.root,env=environment,capture_output=True,timeout=180)
        inventory=subprocess.run([str(python),'-X','utf8','-B','-c',
                                  'import json,site,sys; from pathlib import Path; '
                                  'print(json.dumps({"isolated":sys.prefix!=sys.base_prefix,"user_site":site.ENABLE_USER_SITE,'
                                  '"entries":[p.name for d in site.getsitepackages() if Path(d).name=="site-packages" for p in Path(d).iterdir()]}))'],
                                  env=environment,capture_output=True,timeout=30)
        self.assertEqual(inventory.returncode,0,inventory.stderr)
        state=json.loads(inventory.stdout)
        self.assertTrue(state['isolated']);self.assertFalse(state['user_site']);self.assertEqual(state['entries'],[])
        checked=cli('doctor','--check')
        self.assertEqual(checked.returncode,0,checked.stderr.decode(errors='replace'))
        report=json.loads(checked.stdout)
        self.assertEqual(report['build_check']['status'],'passed')
        project=self.root/'new user project 😀'; project.mkdir()
        entry=project/'extract.ail'
        entry.write_text('use json_pointer;\nuse environment_config;\n'
                         'fn main()->int { let text=read_bytes(sys.argv[1]).decode("utf-8"); '
                         'let nodes=json_parse_document(text); '
                         'let selected=json_pointer_extract(nodes,"/value"); '
                         'write_stdout_bytes((json_render_document(selected)+"\\n").encode("utf-8")); '
                         'return env_int("AIL_TEST_BOOTSTRAP_RESULT",0); }',encoding='utf8')
        data=project/'input.json'; data.write_bytes('{"value":"日本語😀","other":-0.00e+02}'.encode())
        executable=project/('program.exe' if os.name=='nt' else 'program')
        compiled=cli('compile',entry,'-o',executable)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        run=subprocess.run([str(executable),str(data)],env=dict(environment,AIL_TEST_BOOTSTRAP_RESULT='0'),
                           capture_output=True,timeout=30)
        self.assertEqual((run.returncode,run.stdout,run.stderr),(0,'"日本語😀"\n'.encode(),b''))
        integrity=cli('integrity'); self.assertEqual(integrity.returncode,0,integrity.stderr)
        self.assertEqual(json.loads(integrity.stdout)['status'],'verified')
        self.assertGreater(len(marker.read_text(encoding='utf8').splitlines()),1)
        after={p.relative_to(sdk).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sdk.rglob('*') if p.is_file()}
        self.assertEqual(after,before,'bootstrap must preserve the SDK and use its relocated files')

if __name__=='__main__':unittest.main()