"""Public doctor configuration and compile/run probe outcomes, independent of helper internals."""
from contextlib import redirect_stderr,redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import ail_chatgpt
import test_ail_c_objects as support

class DoctorTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command

    def invoke(self,check=True):
        output=io.StringIO();errors=io.StringIO()
        # Host inventory can invoke uname on some Python versions; isolate the probe contract.
        with patch.object(ail_chatgpt.platform,'platform',return_value='test platform'), \
                redirect_stdout(output),redirect_stderr(errors):
            status=ail_chatgpt.main(['doctor',*(['--check'] if check else [])])
        report=json.loads(output.getvalue())
        self.assertEqual(errors.getvalue(),'')
        return status,report

    def failed(self,status,report,phase):
        self.assertNotEqual(status,0)
        self.assertEqual(report['build_check']['status'],'failed')
        self.assertEqual(report['build_check']['phase'],phase)
        self.assertIsInstance(report['build_check']['message'],str)
        self.assertTrue(report['build_check']['message'])

    def test_real_gcc_public_cli_check_compiles_runs_and_reports_passed(self):
        compiler=shutil.which('gcc')
        self.assertTrue(compiler,'real GCC required')
        with patch.dict(os.environ,{'PIPE_CC':compiler}):
            result=self.command('doctor','--check')
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        report=json.loads(result.stdout)
        self.assertTrue(report['c_compiler_available'])
        self.assertEqual(report['c_compiler_configured'],compiler)
        self.assertEqual(report['build_check']['status'],'passed')
        self.assertEqual(report['build_check']['phase'],'run')
        self.assertIsInstance(report['build_check']['message'],str)

    def test_missing_explicit_compiler_configuration_has_no_fallback_or_child(self):
        missing=str(self.root/'missing compiler.exe')
        with patch.dict(os.environ,{'PIPE_CC':missing}),patch.object(ail_chatgpt.subprocess,'run') as child:
            status,report=self.invoke()
        self.assertEqual(status,2)
        self.failed(status,report,'configuration')
        self.assertEqual(report['c_compiler_configured'],missing)
        self.assertFalse(report['c_compiler_available'])
        self.assertIsNone(report['c_compiler'])
        child.assert_not_called()

    def test_existing_noncompiler_executable_is_available_but_compile_fails(self):
        with patch.dict(os.environ,{'PIPE_CC':sys.executable}):
            result=self.command('doctor','--check')
        self.assertNotEqual(result.returncode,0)
        report=json.loads(result.stdout)
        self.assertTrue(report['c_compiler_available'])
        self.assertEqual(report['c_compiler_configured'],sys.executable)
        self.failed(result.returncode,report,'compile')

    def test_plain_doctor_starts_no_subprocess(self):
        for requested in (sys.executable,str(self.root/'missing')):
            with patch.dict(os.environ,{'PIPE_CC':requested}),patch.object(ail_chatgpt.subprocess,'run') as child:
                status,report=self.invoke(check=False)
            self.assertEqual(status,0)
            self.assertEqual(report['c_compiler_configured'],requested)
            child.assert_not_called()

    def test_unset_or_empty_compiler_uses_path_and_missing_path_is_configuration_failure(self):
        for empty in (False,True):
            with self.subTest(empty=empty),patch.dict(os.environ,{},clear=True):
                if empty:os.environ['PIPE_CC']=''
                with patch.object(ail_chatgpt.shutil,'which',return_value=None),patch.object(ail_chatgpt.subprocess,'run') as child:
                    status,report=self.invoke()
                self.assertEqual(status,2)
                self.failed(status,report,'configuration')
                self.assertFalse(report['c_compiler_available'])
                self.assertIsNone(report['c_compiler'])
                child.assert_not_called()
        with patch.dict(os.environ,{'PIPE_CC':''}),patch.object(ail_chatgpt.shutil,'which',
                side_effect=lambda name:sys.executable if name in ('clang',sys.executable) else None), \
                patch.object(ail_chatgpt.subprocess,'run') as child:
            status,report=self.invoke(check=False)
        self.assertEqual(status,0)
        self.assertEqual(report['c_compiler'],sys.executable)
        child.assert_not_called()

    def test_compile_oserror_timeout_and_missing_artifact_report_compile_phase(self):
        for outcome in ('oserror','timeout','missing_artifact'):
            calls=[]
            def child(argv,**kwargs):
                calls.append(list(map(str,argv)))
                self.assertIn('compile',calls[-1],'the probe must use the public compile CLI')
                if outcome=='oserror':raise OSError('compile unavailable')
                if outcome=='timeout':raise subprocess.TimeoutExpired(argv,1)
                return subprocess.CompletedProcess(argv,0,b'',b'')
            with self.subTest(outcome=outcome),patch.dict(os.environ,{'PIPE_CC':sys.executable}), \
                    patch.object(ail_chatgpt.subprocess,'run',side_effect=child):
                status,report=self.invoke()
                self.failed(status,report,'compile')
                self.assertEqual(len(calls),1)

    def test_wrong_stdout_nonzero_oserror_and_timeout_report_run_phase(self):
        for outcome in ('wrong_stdout','nonzero','oserror','timeout','unexpected_stderr'):
            calls=[]
            def child(argv,**kwargs):
                args=list(map(str,argv));calls.append(args)
                if 'compile' in args:
                    self.assertEqual(len(calls),1)
                    output=Path(args[args.index('-o')+1]);output.write_bytes(b'mock executable')
                    return subprocess.CompletedProcess(argv,0,b'',b'')
                self.assertEqual(len(calls),2)
                if outcome=='oserror':raise OSError('execution unavailable')
                if outcome=='timeout':raise subprocess.TimeoutExpired(argv,1)
                return subprocess.CompletedProcess(argv,7 if outcome=='nonzero' else 0,
                         b'AIL environment\r\n' if outcome=='wrong_stdout' else b'AIL environment\n',
                         b'runtime diagnostic' if outcome=='unexpected_stderr' else b'')
            with self.subTest(outcome=outcome),patch.dict(os.environ,{'PIPE_CC':sys.executable}), \
                    patch.object(ail_chatgpt.subprocess,'run',side_effect=child):
                status,report=self.invoke()
                self.failed(status,report,'run')
                self.assertEqual(len(calls),2)

    def test_unsupported_python_stops_before_any_probe_child(self):
        with patch.object(ail_chatgpt.sys,'version_info',(3,9,0)), \
                patch.dict(os.environ,{'PIPE_CC':sys.executable}), \
                patch.object(ail_chatgpt.subprocess,'run') as child:
            status,report=self.invoke()
        self.assertEqual(status,2)
        self.assertFalse(report['python_supported'])
        self.failed(status,report,'configuration')
        child.assert_not_called()
if __name__=='__main__':unittest.main()