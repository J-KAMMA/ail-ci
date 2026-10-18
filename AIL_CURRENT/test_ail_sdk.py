"""Relocated SDK public workloads with independent oracles and Python read guard."""
import csv
import re
import hashlib
import importlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest

import test_ail_c_objects as support


class SdkTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp

    def exported(self):
        output = self.root / 'initial-sdk'
        importlib.import_module('ail_sdk').export_sdk(support.ROOT, output)
        sdk = self.root / '移動 言語SDK 😀'
        output.rename(sdk)
        return sdk

    def environment(self):
        # Denies Python opens in CLI/child interpreters; this is not an OS sandbox.
        guard = self.root / 'python-guard'
        guard.mkdir(exist_ok=True)
        marker = self.root / 'guard-loaded.txt'
        (guard / 'sitecustomize.py').write_text(
            'import os, sys\n'
            f'original = os.path.normcase(os.path.realpath({str(support.ROOT)!r}))\n'
            'def deny_original(event, args):\n'
            ' if event != "open" or not args or isinstance(args[0], int): return\n'
            ' path = os.path.normcase(os.path.realpath(os.fsdecode(args[0])))\n'
            ' try: inside = os.path.commonpath([path, original]) == original\n'
            ' except ValueError: inside = False\n'
            ' if inside: raise PermissionError("original AIL source read denied: " + path)\n'
            'sys.addaudithook(deny_original)\n'
            f'with open({str(marker)!r}, "a", encoding="utf8") as stream: stream.write("active\\n")\n',
            encoding='utf8')
        return dict(os.environ, PYTHONPATH=str(guard), PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1'), marker

    def cli(self, sdk, environment, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', '-B', str(sdk / 'ail_chatgpt.py'),
                               *map(str, args)], cwd=self.root, env=environment,
                              capture_output=True, timeout=240)

    def build(self, sdk, environment, source, name, *options, command='compile'):
        output = self.root / name
        result = self.cli(sdk, environment, command, source, *options, '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return output if output.is_file() else Path(str(output) + '.exe')

    def run_binary(self, executable, *args):
        return subprocess.run([str(executable), *map(str, args)], cwd=self.root,
                              capture_output=True, timeout=180)

    def same_bytes(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(expected).digest())

    def successful(self, executable, expected, *args):
        result = self.run_binary(executable, *args)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stderr, b'')
        self.same_bytes(result.stdout, expected)

    def test_relocated_numeric_profiles_source_free_object(self):
        sdk=self.exported(); environment,marker=self.environment()
        for symbol in ('hex','list[float].sort','str.lstrip','str.rstrip'):
            queried=self.cli(sdk,environment,'api-builtin',symbol)
            self.assertEqual((queried.returncode,queried.stderr),(0,b''))
            self.assertTrue(json.loads(queried.stdout)['entries'][0]['signature_known'])
        provider=self.root/'numeric_profiles.ail'
        provider.write_text('fn report()->str {let rows:list[tuple[int,int]]=[(7,8)];'
                            'let values:list[float]=[3.0,-2.0,float("inf")];values.sort();'
                            'return ("x"+hex(rows[0][0]+int(values[0]))+"x").lstrip("x").rstrip("x");}',encoding='utf8')
        obj=self.build(sdk,environment,provider,'numeric-profiles.o',command='compile-module')
        provider.unlink()
        original=hashlib.sha256(obj.read_bytes()).hexdigest()
        source=self.root/'numeric_client.ail'
        source.write_text('fn main()->int {write_stdout_bytes(report().encode());return 0;}',encoding='utf8')
        self.successful(self.build(sdk,environment,source,'numeric-client','--object',obj),hex(7+int(sorted([3.0,-2.0,float('inf')])[0])).encode())
        self.assertEqual(hashlib.sha256(obj.read_bytes()).hexdigest(),original)
        self.assertTrue(marker.is_file())
    def test_relocated_integer_quantiles_expression_extend(self):
        sdk = self.exported(); environment, marker = self.environment()
        binary = self.build(sdk, environment, sdk / 'language_examples/integer_quantiles.ail', 'quantiles')
        paths = [self.root / 'first 日本.txt', self.root / 'second 😀.txt']
        cases = [([], []), ([3, -2, 3], [7, 0]),
                 ([-(1 << 63), (1 << 63) - 1], [0, -1]),
                 (list(range(2049, -1, -1)), list(range(-2049, 0)))]
        for left, right in cases:
            for path, values in zip(paths, (left, right)):
                path.write_bytes((' \n'.join(map(str, values))).encode())
            ordered = sorted(left + right)
            expected = {'count': len(ordered), 'min': ordered[0] if ordered else None,
                        'median': ordered[(len(ordered)-1)//2] if ordered else None,
                        'max': ordered[-1] if ordered else None}
            result = self.run_binary(binary, *paths)
            self.assertEqual((result.returncode, result.stderr), (0, b''))
            self.assertEqual(result.stdout, (json.dumps(expected, separators=(',', ':')) + '\n').encode())
        paths[0].write_bytes(b'9223372036854775808')
        failed = self.run_binary(binary, *paths)
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(failed.stdout, b'')
        self.assertEqual(failed.stderr.replace(b'\r\n', b'\n'), b'ValueError: \n')
        self.assertTrue(marker.is_file())

    def test_relocated_exception_config_application(self):
        from test_ail_exception_values_app import reference
        sdk = self.exported(); environment, marker = self.environment()
        binary = self.build(sdk, environment, sdk / 'language_examples/config_validate.ail', 'config-app')
        path = self.root / 'config 日本.txt'
        for payload in (b'x=2\ny=-3\n', 'x=日本😀'.encode(), b'\xff'):
            path.write_bytes(payload)
            expected = reference(payload)
            result = self.run_binary(binary, path)
            encode = lambda text: text.replace('\n', os.linesep).encode()
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (expected[0], encode(expected[1]), encode(expected[2])))
            self.assertEqual(path.read_bytes(), payload)
        batch = self.build(sdk, environment, sdk / 'language_examples/config_batch.ail', 'config-batch')
        good = self.root / 'valid.txt'; good.write_bytes(b'x=2\ny=-3')
        wanted = {'reports': [{'path': str(good), 'summary': {'count': 2, 'total': -1}}],
                  'errors': [{'path': str(path), 'kind': 'UnicodeDecodeError', 'message': 'input must be UTF-8'}]}
        result = self.run_binary(batch, good, path)
        self.assertEqual((result.returncode, result.stderr), (2, b''))
        self.assertEqual(result.stdout, (json.dumps(wanted, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
        merge_source=self.root/'merge.ail'
        prefix=(sdk/'language_examples/config_batch.ail').read_bytes().split(b'fn main()',1)[0]
        main=b'''fn main()->int {
            let left=validate_many(sys.argv[1:2]);let right=validate_many(sys.argv[2:]);
            let saved=batch_json(right);let merged=merge_config_batches(left,right);
            if batch_json(right)!=saved {return 9;}
            write_stdout_bytes((batch_json(merged)+"\\n").encode());return 2;
        }'''
        merge_source.write_bytes(prefix+main)
        merged=self.build(sdk,environment,merge_source,'config-merged','-I',sdk/'language_examples')
        result=self.run_binary(merged,good,path)
        self.assertEqual((result.returncode,result.stderr),(2,b''))
        self.assertEqual(result.stdout,(json.dumps(wanted,ensure_ascii=False,separators=(',',':'))+'\n').encode())
        broken = self.root / 'broken_config.ail'
        broken.write_bytes((sdk / 'language_examples/config_batch.ail').read_bytes().replace(b'errors.append(error);', b'errors.append(7);'))
        checked = self.cli(sdk, environment, 'check', broken, '-I', sdk / 'language_examples', '--repair-context')
        self.assertEqual(checked.returncode, 1)
        report = json.loads(checked.stdout)
        self.assertEqual(report['diagnostics'][0]['type_details'],
                         {'operation': 'element', 'action': 'append', 'container': 'list[exception]',
                          'expected': 'exception', 'actual': 'int'})
        self.assertEqual(report['repair_context']['target'], 'validate_many')
        self.assertFalse(report['runtime_verified'])
        self.assertTrue(marker.is_file())

    def test_relocated_function_body_edit_build_and_run(self):
        sdk=self.exported();environment,marker=self.environment()
        intrinsic=self.cli(sdk,environment,'api-builtin','binaryfile.read')
        self.assertEqual((intrinsic.returncode,intrinsic.stderr),(0,b''))
        declared=json.loads(intrinsic.stdout)
        self.assertEqual(declared['schema'],'ail.builtin_api/1')
        self.assertTrue(declared['entries'][0]['signature_known'])
        self.assertEqual(declared['entries'][0]['overloads'][0]['result']['type'],'bytes')
        self.assertFalse(declared['entries'][0]['runtime_verified'])
        search_api=self.cli(sdk,environment,'api-builtin','str.find')
        self.assertEqual((search_api.returncode,search_api.stderr),(0,b''))
        self.assertEqual([len(o['parameters']) for o in json.loads(search_api.stdout)['entries'][0]['overloads']],[1,2,3])
        pop_api=self.cli(sdk,environment,'api-builtin','list[str].pop')
        self.assertEqual((pop_api.returncode,pop_api.stderr),(0,b''))
        self.assertEqual([len(o['parameters']) for o in json.loads(pop_api.stdout)['entries'][0]['overloads']],[0,1])
        list_source=self.root/'list-operations.ail'
        list_source.write_text('fn main()->int {let words:list[str]=["first","last"];words.reverse();let saved=words.pop();words.clear();write_stdout_bytes(saved.encode());return 0;}',encoding='utf8')
        self.successful(self.build(sdk,environment,list_source,'list-operations-native'),b'first')
        map_api=self.cli(sdk,environment,'api-builtin','dict[str,str].pop')
        self.assertEqual((map_api.returncode,map_api.stderr),(0,b''))
        mapping=json.loads(map_api.stdout)['entries'][0]
        self.assertEqual([len(o['parameters']) for o in mapping['overloads']],[1,2])
        self.assertTrue(all(o['receiver']['mutable'] for o in mapping['overloads']))
        self.assertTrue(all(o['result']['ownership']=='owned_snapshot' for o in mapping['overloads']))
        loop_api=self.cli(sdk,environment,'api-builtin','range')
        self.assertEqual((loop_api.returncode,loop_api.stderr),(0,b''))
        loop=json.loads(loop_api.stdout)['entries'][0]
        self.assertFalse(loop['signature_known']);self.assertEqual(loop['overloads'],[])
        self.assertEqual(loop['syntax_forms'][0]['context'],'direct_for')
        loop_source=self.root/'query-loop.ail'
        loop_source.write_text(loop['syntax_forms'][0]['source'].replace('fn probe(','fn sum_to(')+' fn main()->int {write_stdout_bytes(str(sum_to(4)).encode());return 0;}',encoding='utf8')
        self.successful(self.build(sdk,environment,loop_source,'query-loop-native'),b'6')
        search_source=self.root/'search-alias.ail'
        search_source.write_text('fn find(source:str,needle:str)->int {let alias=source;return alias.find(needle);} fn main()->int {write_stdout_bytes(str(find("a😀b","😀")).encode());return 0;}',encoding='utf8')
        self.successful(self.build(sdk,environment,search_source,'search-alias-native'),b'1')
        source=self.root/'editable 日本.ail';body=self.root/'body.txt';output=self.root/'candidate.ail'
        source.write_bytes(b'use neighbor; fn helper(x:int)->int {return bump(x)+"broken";}\nfn main()->int {write_stdout_bytes(str(helper(2)).encode());return 0;}')
        (self.root/'neighbor.ail').write_bytes(b'fn bump(x:int)->int {return x+1;}')
        body.write_bytes(b'return bump(x)+2;')
        original=source.read_bytes();sha=hashlib.sha256(original).hexdigest()
        plain=self.cli(sdk,environment,'context',source,'--symbol','helper','--include-body','--resolve-imports')
        self.assertEqual((plain.returncode,plain.stderr),(0,b''))
        self.assertNotIn('contracts',json.loads(plain.stdout))
        obtained=self.cli(sdk,environment,'context',source,'--symbol','helper','--include-body','--resolve-imports','--contracts','--compact')
        self.assertEqual((obtained.returncode,obtained.stderr),(0,b''))
        from ail_source_context import expand_context
        packed=json.loads(obtained.stdout)
        self.assertEqual(packed['schema'],'ail.context.compact/1')
        context=expand_context(packed)
        self.assertEqual(context['contracts']['schema'],'ail.api_contracts/1')
        self.assertEqual({key:value for key,value in context.items() if key!='contracts'},json.loads(plain.stdout))
        self.assertEqual(context['source_sha256'],sha);self.assertEqual(context['imports'],['neighbor'])
        self.assertFalse(context['type_verified']);self.assertEqual(context['body'],'return bump(x)+"broken";')
        signatures={item['name']:item for item in context['interface']['functions']}
        self.assertEqual(signatures['bump']['returns'],'int')
        self.assertEqual(context['dependency_sha256'][str((self.root/'neighbor.ail').resolve())],
                         hashlib.sha256((self.root/'neighbor.ail').read_bytes()).hexdigest())
        sha=context['source_sha256']
        context_file=self.root/'context.json';context_file.write_bytes(obtained.stdout)
        result=self.cli(sdk,environment,'edit',source,'--symbol','helper','--base-sha256',sha,'--body',body,'--context',context_file,'-o',output)
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        report=json.loads(result.stdout)
        self.assertFalse(report['link_verified']);self.assertFalse(report['runtime_verified'])
        self.assertEqual(output.read_bytes(),original.replace(b'return bump(x)+"broken";',b'return bump(x)+2;'))
        executable=self.build(sdk,environment,output,'edited-native','--json','--debug-dir',self.root/'edited-debug')
        native_report=json.loads((self.root/'edited-debug/ail_build.json').read_bytes())
        self.assertEqual((native_report['status'],native_report['link_verified'],native_report['runtime_verified']),('passed',True,False))
        self.assertTrue(native_report['native_build']['generated'])
        self.successful(executable,b'5')
        self.assertEqual(source.read_bytes(),original);self.assertTrue(marker.is_file())
        (self.root/'neighbor.ail').write_bytes(b'fn bump(x:int)->int {return x+50;}')
        stale=self.root/'stale-candidate.ail'
        refused=self.cli(sdk,environment,'edit',source,'--symbol','helper','--base-sha256',sha,
                         '--body',body,'--context',context_file,'-o',stale)
        self.assertEqual(refused.returncode,2);self.assertFalse(stale.exists())
        self.assertIn('stale',json.loads(refused.stdout)['error'])
        self.assertEqual(source.read_bytes(),original)
    def test_relocated_json_query_options_batch(self):
        sdk=self.exported();environment,marker=self.environment();examples=sdk/'language_examples'
        obj=self.build(sdk,environment,examples/'file_identity.c','query-identity.o',
                       '--interface',examples/'file_identity.json',command='compile-c')
        checked=self.cli(sdk,environment,'api','json_query_file','--object',obj,
                         '--symbol','json_query_file','--types-used')
        self.assertEqual((checked.returncode,checked.stderr),(0,b''))
        report=json.loads(checked.stdout)
        self.assertFalse(report['link_verified']);self.assertFalse(report['runtime_verified'])
        self.assertEqual([item['name'] for item in report['interface']['functions']],['json_query_file'])
        self.assertEqual([item['name'] for item in report['interface']['structs']],['JsonQueryResult'])
        executable=self.build(sdk,environment,examples/'json_query_main.ail','query-batch','--object',obj,'--separate')
        source=self.root/'document.json';output=self.root/'selected.json'
        source.write_bytes(b'{"a/b":[9007199254740993,-0.00e+02,true]}');before=hashlib.sha256(source.read_bytes()).hexdigest()
        command=[str(executable),'batch','--input',str(source),'--output',str(output),'--','/a~1b/2','/a~1b/0','/a~1b/1']
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=60)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(output.read_bytes(),b'[true,9007199254740993,-0.00e+02]\n')
        old=output.read_bytes();command.append('/missing')
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=60)
        self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertTrue(result.stderr)
        self.assertEqual(output.read_bytes(),old);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
        self.assertTrue(marker.is_file())
    def test_relocated_pool_iterable_single_evaluation(self):
        sdk=self.exported();environment,marker=self.environment()
        source=self.root/'pool capture.ail'
        source.write_text('''fn choose()->int {write_stdout_bytes(b"once|");return 0;}
fn reduce(values:list[int])->int {return sum(values);}
fn main()->int {let g=[[1,2,3]];write_stdout_bytes(str(reduce(g[choose()])).encode());return 0;}''',encoding='utf8')
        original=source.read_bytes();executable=self.build(sdk,environment,source,'pool-capture')
        self.successful(executable,b'once|6')
        self.assertEqual(source.read_bytes(),original);self.assertTrue(marker.is_file())
    def test_relocated_grid_return_calls(self):
        from test_ail_grid_calls import LIBRARY,ENTRY
        sdk=self.exported(); environment,marker=self.environment()
        module=self.root/'grid_module.ail';module.write_text(LIBRARY,encoding='utf8')
        source=self.root/'grid_client.ail';source.write_text('use grid_module;\n'+ENTRY,encoding='utf8')
        executable=self.build(sdk,environment,source,'grid-client','--separate')
        rows,cols=4097,17
        values=[[i*100003+j-17 for j in range(cols)] for i in range(rows)]
        expected=f'{cols}\n{rows}\ncaught\n{rows}\n'+''.join(' '.join(map(str,row))+'\n' for row in values)+'123\n'
        self.successful(executable,expected.replace('\n',os.linesep).encode(),rows,cols)
        self.assertTrue(marker.is_file())
    def test_relocated_empty_bytes_list_constructor(self):
        sdk=self.exported(); environment,marker=self.environment()
        provider=self.root/'empty_provider.ail'
        provider.write_text('struct Holder {parts:list[bytes]; tag:int;} '
                            'fn make_empty(tag:int)->Holder {return Holder([],tag);}',encoding='utf8')
        obj=self.build(sdk,environment,provider,'empty-provider.o',command='compile-module')
        provider.unlink()
        source=self.root/'empty_client.ail'
        source.write_text(r'''fn main()->int {
 let data=read_bytes(sys.argv[1]);
 let first=make_empty(1); let second=make_empty(2);
 first.parts.append(data); let shared=first.parts;
 if len(second.parts)!=0 {return 1;}
 first=make_empty(3); second.parts.append(b"tail\0\xff");
 for i in range(257) {let discarded=make_empty(i); discarded.parts.append(bytes(129));}
 if len(first.parts)!=0 or len(shared)!=1 or len(second.parts)!=1 {return 2;}
 write_stdout_bytes(shared[0]+second.parts[0]);return 0;
}''',encoding='utf8')
        executable=self.build(sdk,environment,source,'empty-client','--object',obj)
        data=bytes(range(256))*4097+b'\0\xff'
        path=self.root/'binary-input';path.write_bytes(data)
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        self.successful(executable,data+b'tail\0\xff',path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        self.assertTrue(marker.is_file())
    def test_relocated_public_five_workloads_and_source_free_helper(self):
        sdk = self.exported()
        environment, marker = self.environment()
        manifest = json.loads((sdk / 'MANIFEST.json').read_text(encoding='utf8'))
        pins = {name: hashlib.sha256((sdk / name).read_bytes()).hexdigest()
                for name in manifest['sha256']}
        project = self.root / '新規 project 😀'
        project.mkdir()
        examples = sdk / 'language_examples'
        names = ('csv_table', 'json_query', 'binary_search', 'binary_cursor_records', 'numeric_scale_binary')
        sources = {}
        for name in names:
            source = project / (name + '_main.ail')
            shutil.copyfile(examples / (name + '_main.ail'), source)
            sources[name] = source
        identity = self.root / 'file_identity.o'
        result = self.cli(sdk, environment, 'compile-c', examples / 'file_identity.c',
                          '--interface', examples / 'file_identity.json', '-o', identity)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        output_names = dict(zip(names, ('csv_program', 'json_program', 'search_program', 'records_program', 'scale_program')))
        executables = {name: self.build(sdk, environment, sources[name], output_names[name],
                                       *(('--object', identity) if name == 'json_query' else ()))
                       for name in names}

        table = io.StringIO(newline='')
        rows = [(f'日本語,{i}\\"', 'a' * 64 + '\nline') for i in range(18000)]
        csv.writer(table, lineterminator='\r\n').writerows(rows)
        csv_input = project / 'input.csv'
        csv_input.write_bytes(table.getvalue().encode('utf8'))
        parsed = csv.reader(io.StringIO(table.getvalue(), newline=''))
        csv_expected = ''.join(json.dumps([row[1], row[0]], ensure_ascii=False,
                                          separators=(',', ':')) + '\n' for row in parsed).encode('utf8')
        self.assertGreater(len(csv_expected), 1 << 20)
        self.successful(executables['csv_table'], csv_expected, 'project', csv_input, '1,0', 4093)
        csv_separate = self.build(sdk, environment, sources['csv_table'], 'csv_separate', '--separate')
        self.successful(csv_separate, csv_expected, 'project', csv_input, '1,0', 8191)

        selected = ['x' * 64 + str(i) for i in range(18000)]
        document = {'items': [False, selected, None]}
        json_input, json_output = project / 'input.json', project / 'selected.json'
        json_input.write_text(json.dumps(document, separators=(',', ':')), encoding='utf8')
        selected_by_python = json.loads(json_input.read_text(encoding='utf8'))['items'][1]
        json_expected = (json.dumps(selected_by_python, ensure_ascii=False,
                                    separators=(',', ':')) + '\n').encode('utf8')
        self.assertGreater(len(json_expected), 1 << 20)
        self.successful(executables['json_query'], b'', 'extract', json_input, json_output, '/items/1')
        self.same_bytes(json_output.read_bytes(), json_expected)

        for invalid in (b'\xff', b'\xc0\x80', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xf0\x9f\x98'):
            json_input.write_bytes(invalid)
            json_output.write_bytes(b'prior output')
            result = self.run_binary(executables['json_query'], 'extract', json_input, json_output, '/items/1')
            self.assertEqual((result.returncode, result.stdout), (2, b''))
            self.assertIn(b'invalid UTF-8 JSON input', result.stderr)
            self.assertEqual(json_output.read_bytes(), b'prior output')
            self.assertEqual(json_input.read_bytes(), invalid)

        search_input = project / 'search.bin'
        haystack = bytes(range(256)) * 4097 + b'needle\x00\xff'
        needle = b'needle\x00\xff'
        search_input.write_bytes(haystack)
        self.successful(executables['binary_search'], f'{haystack.find(needle)}{os.linesep}'.encode(),
                        'find', search_input, needle.hex())

        count = 90000
        fields = [(i % 256, i % 65536, (i * 7) % 65536, i * 123, i * 7919) for i in range(count)]
        records = b''.join(struct.pack('<BH', a, b) + struct.pack('>H', c)
                           + struct.pack('<I', d) + struct.pack('>I', e) for a, b, c, d, e in fields)
        self.assertGreater(len(records), 1 << 20)
        records_input = project / 'records.bin'
        records_input.write_bytes(records)
        decoded = [(records[i], struct.unpack_from('<H', records, i + 1)[0],
                    struct.unpack_from('>H', records, i + 3)[0],
                    struct.unpack_from('<I', records, i + 5)[0],
                    struct.unpack_from('>I', records, i + 9)[0]) for i in range(0, len(records), 13)]
        report = ' '.join(map(str, [count, *(sum(column) for column in zip(*decoded)), len(records)])) + '\n'
        self.successful(executables['binary_cursor_records'], report.encode(), records_input)
        records_separate = self.build(sdk, environment, sources['binary_cursor_records'],
                                      'records_separate', '--separate')
        self.successful(records_separate, report.encode(), records_input)

        values = [math.ldexp(float((i % 8191) - 4095), (i % 17) - 8) for i in range(131073)]
        values[:4] = [-0.0, 0.0, math.ldexp(1.0, -1074), -math.ldexp(1.0, -1074)]
        numeric_input = project / 'float64.bin'
        numeric_input.write_bytes(struct.pack('<' + 'd' * len(values), *values))
        numeric_expected = struct.pack('<' + 'd' * len(values), *(value * -0.5 for value in values))
        self.successful(executables['numeric_scale_binary'], numeric_expected, numeric_input, 0, '-0.5')

        include = project / 'include'
        include.mkdir()
        helper = include / 'helper.ail'
        helper.write_text('use binary_numbers; fn sdk_helper()->bytes {return pack_u16_le(4660);}', encoding='utf8')
        wrapper = project / 'wrapper.ail'
        wrapper.write_text('use helper; fn sdk_export()->bytes {return sdk_helper();}', encoding='utf8')
        obj = self.build(sdk, environment, wrapper, 'helper.o', '-I', include, command='compile-module')
        helper.unlink(); wrapper.unlink()
        consumer = project / 'consumer.ail'
        consumer.write_text('fn main()->int {write_stdout_bytes(sdk_export());return 0;}', encoding='utf8')
        self.successful(self.build(sdk, environment, consumer, 'consumer', '--object', obj), b'\x34\x12')
        readme = (sdk / 'SDK_README_JA.md').read_text(encoding='utf8')
        hello = re.search(r'```text\n(fn main\(\).*?)\n```', readme, re.S).group(1)
        hello_source = project / 'hello.ail'
        hello_source.write_text(hello, encoding='utf8')
        hello_binary = self.build(sdk, environment, hello_source, 'hello_program')
        self.successful(hello_binary, b'hello' + os.linesep.encode())
        sample = re.search(r'```python\n(.*?)\n```', readme, re.S).group(1)
        sample_path = self.root / 'try_cli.py'
        sample_path.write_text(sample, encoding='utf8')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(sample_path)],
                                cwd=self.root, env=environment, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout.replace(b'\r\n', b'\n'), b'["a"]\n["b"]\n')

        integrity = self.cli(sdk, environment, 'integrity')
        self.assertEqual(integrity.returncode, 0, integrity.stderr.decode(errors='replace'))
        self.assertEqual(json.loads(integrity.stdout)['status'], 'verified')
        self.assertEqual({name: hashlib.sha256((sdk / name).read_bytes()).hexdigest() for name in pins}, pins)
        self.assertGreaterEqual(len(marker.read_text(encoding='utf8').splitlines()), 11)

    def test_relocated_json_lines_service(self):
        from test_ail_tcp_json_lines import TcpJsonLinesTests
        from test_ail_tcp_listener import RunningServer
        sdk = self.exported()
        environment, marker = self.environment()
        exe = self.build(sdk, environment, sdk / 'language_examples/tcp_json_lines_main.ail', 'json-server')
        frames = [b'{"same":1,"same":-0.0e+02}\n', '["日本語😀",null]\n'.encode()]
        probe = TcpJsonLinesTests()
        with RunningServer(exe, ('127.0.0.1', 0, 1, 3000, 1048576)) as server:
            self.assertEqual(probe.exchange(server, frames), b''.join(frames))
            self.assertEqual(server.finish(), (b'2\r\n' if os.name == 'nt' else b'2\n', b''))
        self.assertTrue(marker.is_file())
        # The provider object includes its imported dependency closure.
        provider = self.build(sdk, environment, sdk / 'language_examples/tcp_json_lines.ail',
                              'provider.o', command='compile-module')
        moved = self.root / 'sourcefree-service'
        moved.mkdir()
        obj = moved / provider.name
        shutil.move(provider, obj)
        shutil.move(str(provider) + '.json', str(obj) + '.json')
        entry = moved / 'entry.ail'
        entry.write_text((sdk / 'language_examples/tcp_json_lines_main.ail').read_text(encoding='utf8')
                         .replace('use tcp_json_lines;', ''), encoding='utf8')
        (sdk / 'language_examples').rename(self.root / 'unavailable-library-sources')
        linked = self.build(sdk, environment, entry, 'linked-service', '--object', obj)
        with RunningServer(linked, ('127.0.0.1', 0, 1, 3000, 1048576)) as server:
            self.assertEqual(probe.exchange(server, frames), b''.join(frames))
            self.assertEqual(server.finish(), (b'2\r\n' if os.name == 'nt' else b'2\n', b''))
    def test_relocated_handle_lists_and_source_free_fields(self):
        import socket
        from test_ail_handle_lists import FIELD_PROVIDER, FIELD_ENTRY
        from test_ail_tcp_listener import RunningServer
        sdk=self.exported()
        environment,marker=self.environment()
        example=self.build(sdk,environment,sdk/'language_examples/handle_list_main.ail','handles-example')
        self.successful(example,b'AIL!\n')
        source=self.root/'provider.ail'; source.write_text(FIELD_PROVIDER,encoding='utf8')
        obj=self.build(sdk,environment,source,'provider.o',command='compile-module')
        source.unlink()
        folder=self.root/'moved typed handles 😀'; folder.mkdir(); moved=folder/obj.name
        shutil.move(obj,moved); shutil.move(str(obj)+'.json',str(moved)+'.json')
        entry=folder/'entry.ail'; entry.write_text(FIELD_ENTRY,encoding='utf8')
        exe=self.build(sdk,environment,entry,'typed-service','--object',moved)
        data=bytes(range(256))*33+b'\0\xff'
        path=self.root/'data.bin'; path.write_bytes(data)
        with RunningServer(exe,(path,)) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:
                peer.settimeout(8); output=bytearray()
                while chunk:=peer.recv(4096): output.extend(chunk)
            self.assertEqual(bytes(output),b'prefix\0'+data)
            self.assertEqual(server.finish(),(f'{len(data)+7}{os.linesep}'.encode(),b''))
        self.assertTrue(marker.is_file())
        self.assertEqual(path.read_bytes(),data)

    def test_relocated_multiplex_json_and_source_free_provider(self):
        import socket
        from test_ail_tcp_listener import RunningServer
        sdk=self.exported()
        environment,marker=self.environment()
        examples=sdk/'language_examples'
        main=(examples/'tcp_json_lines_poll_main.ail').read_text(encoding='utf8')
        exe=self.build(sdk,environment,examples/'tcp_json_lines_poll_main.ail','poll-json')
        provider=self.build(sdk,environment,examples/'tcp_json_lines_poll.ail','poll-provider.o',command='compile-module')
        moved=self.root/'moved poll provider 😀'; moved.mkdir(); obj=moved/provider.name
        shutil.move(provider,obj); shutil.move(str(provider)+'.json',str(obj)+'.json')
        entry=moved/'entry.ail'; entry.write_text(main.replace('use tcp_json_lines_poll;',''),encoding='utf8')
        (sdk/'language_examples').rename(self.root/'unavailable-poll-library-sources')
        linked=self.build(sdk,environment,entry,'poll-linked','--object',obj)
        frames=b'{"same":1,"same":-0.00e+02}\n'+ '["日本語😀",null]\n'.encode()
        for binary in (exe,linked):
            with RunningServer(binary,('127.0.0.1',0,2,3000,128,2)) as server:
                with socket.create_connection(('127.0.0.1',server.port),timeout=8) as idle:
                    with socket.create_connection(('127.0.0.1',server.port),timeout=8) as healthy:
                        healthy.settimeout(8); healthy.sendall(frames); output=bytearray()
                        while output.count(b'\n')<2:
                            chunk=healthy.recv(8192); self.assertTrue(chunk); output.extend(chunk)
                        self.assertEqual(bytes(output),frames)
                        healthy.shutdown(socket.SHUT_WR); self.assertEqual(healthy.recv(1),b'')
                    idle.settimeout(8); idle.shutdown(socket.SHUT_WR); self.assertEqual(idle.recv(1),b'')
                self.assertEqual(server.finish(),(f'2{os.linesep}'.encode(),b''))
        self.assertTrue(marker.is_file())

    def test_relocated_filesystem_lifecycle_and_source_free_result(self):
        sdk=self.exported();environment,marker=self.environment()
        exe=self.build(sdk,environment,sdk/'language_examples/filesystem_main.ail','filesystem')
        folder=self.root/'new directory 日本語😀'
        self.successful(exe,b'new\0\xff',folder)
        self.assertFalse(folder.exists())
        folder.mkdir();kept=folder/'kept';kept.write_bytes(b'original')
        failure=self.run_binary(exe,folder)
        self.assertEqual((failure.returncode,failure.stdout,failure.stderr),(4,b'',b''))
        self.assertEqual(kept.read_bytes(),b'original');self.assertEqual(list(folder.iterdir()),[kept])
        provider=self.root/'provider.ail'
        provider.write_text('fn roundtrip(path:str,data:bytes)->bytes { make_dir(path); '
                            'let staged=path+"/stage";let final=path+"/final";'
                            'write_bytes(staged,data);write_bytes(final,b"old");replace_path(staged,final);'
                            'let result=read_bytes(final);remove_file(final);remove_dir(path);return result; }',encoding='utf8')
        obj=self.build(sdk,environment,provider,'filesystem.o',command='compile-module');provider.unlink()
        moved=self.root/'moved file operations 😀';moved.mkdir();target=moved/obj.name
        shutil.move(obj,target);shutil.move(str(obj)+'.json',str(target)+'.json')
        entry=moved/'entry.ail';entry.write_text('fn main()->int { write_stdout_bytes(roundtrip(sys.argv[1],b"new\\0\\xff"));return 0; }',encoding='utf8')
        linked=self.build(sdk,environment,entry,'linked-filesystem','--object',target)
        new=self.root/'new linked directory';self.successful(linked,b'new\0\xff',new)
        self.assertFalse(new.exists());self.assertTrue(marker.is_file())

    def test_relocated_mixed_output_and_source_free_mutable_buffer(self):
        sdk=self.exported();environment,marker=self.environment()
        exe=self.build(sdk,environment,sdk/'language_examples/mixed_output_main.ail','mixed')
        data=bytes(range(256))*4097+b'\r\n\0\xff'
        source=self.root/'payload 日本語😀';source.write_bytes(data)
        newline=os.linesep.encode()
        self.successful(exe,b'AIL bytes '+str(len(data)).encode()+newline+data+b'END'+newline,source)
        provider=self.root/'output.ail'
        provider.write_text('fn emit(data:bytearray)->int { print("header");write_stdout_bytes(data);return len(data); }',encoding='utf8')
        obj=self.build(sdk,environment,provider,'output.o',command='compile-module');provider.unlink()
        moved=self.root/'moved output 😀';moved.mkdir();target=moved/obj.name
        shutil.move(obj,target);shutil.move(str(obj)+'.json',str(target)+'.json')
        entry=moved/'entry.ail'
        entry.write_text('fn main()->int { let data=bytearray(b"A\\0\\xff");let n=emit(data);print(n);write_stdout_bytes(data);return 0; }',encoding='utf8')
        linked=self.build(sdk,environment,entry,'linked-output','--object',target)
        self.successful(linked,b'header'+newline+b'A\0\xff3'+newline+b'A\0\xff')
        self.assertTrue(marker.is_file());self.assertEqual(source.read_bytes(),data)

    def test_relocated_csv_rewrite_clock_and_timed_service(self):
        import socket
        import time
        from test_ail_tcp_listener import RunningServer
        sdk=self.exported();environment,marker=self.environment();examples=sdk/'language_examples'
        identity=self.root/'identity.o'
        result=self.cli(sdk,environment,'compile-c',examples/'file_identity.c','--interface',examples/'file_identity.json','-o',identity)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        exe=self.build(sdk,environment,examples/'csv_rewrite_main.ail','rewrite','--object',identity)
        rows=[['日本語😀',str(i),'x'*512+'\r\n"comma,'] for i in range(2049)]
        table=io.StringIO(newline='');csv.writer(table,lineterminator='\n').writerows(rows)
        source=self.root/'input 😀.csv';source.write_bytes(table.getvalue().encode('utf8'))
        self.assertGreater(source.stat().st_size,1<<20)
        expected=io.StringIO(newline='');csv.writer(expected,lineterminator='\r\n').writerows(rows)
        target=self.root/'rewritten.csv';self.successful(exe,b'',source,target)
        self.same_bytes(target.read_bytes(),expected.getvalue().encode('utf8'))
        self.assertEqual(list(csv.reader(io.StringIO(target.read_bytes().decode('utf8'),newline=''),strict=True)),rows)
        source.write_bytes(b'"unfinished');target.write_bytes(b'keep')
        failure=self.run_binary(exe,source,target)
        self.assertEqual((failure.returncode,failure.stdout),(4,b''));self.assertEqual(target.read_bytes(),b'keep')
        provider=self.root/'clock.ail';provider.write_text('fn clock_value()->int {return monotonic_ms();}',encoding='utf8')
        obj=self.build(sdk,environment,provider,'clock.o',command='compile-module');provider.unlink()
        entry=self.root/'entry.ail';entry.write_text('fn main()->int {print(clock_value());return 0;}',encoding='utf8')
        linked=self.build(sdk,environment,entry,'clock-entry','--object',obj)
        result=self.run_binary(linked);self.assertEqual((result.returncode,result.stderr),(0,b''));self.assertGreaterEqual(int(result.stdout),0)
        server_exe=self.build(sdk,environment,examples/'tcp_json_lines_poll_main.ail','timed')
        # Isolate peer expiry from batch/startup scheduling; retain a deliberate late connection.
        with RunningServer(server_exe,('127.0.0.1',0,1,15000,64,1,150,0)) as server:
            time.sleep(1.2)
            with socket.create_connection(('127.0.0.1',server.port),timeout=5) as peer:
                began=time.monotonic()
                peer.settimeout(5);self.assertEqual(peer.recv(1),b'')
            out,err=server.process.communicate(timeout=5)
            self.assertEqual((server.process.returncode,out),(3,b''));self.assertIn(b'deadline',err)
        self.assertLess(time.monotonic()-began,3);self.assertTrue(marker.is_file())

    def test_relocated_stream_csv_and_source_free_file_handles(self):
        sdk=self.exported();environment,marker=self.environment();examples=sdk/'language_examples'
        identity=self.root/'stream-identity.o'
        result=self.cli(sdk,environment,'compile-c',examples/'file_identity.c','--interface',examples/'file_identity.json','-o',identity)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        exe=self.build(sdk,environment,examples/'csv_rewrite_stream_main.ail','stream-rewrite','--object',identity)
        rows=[['日本語😀',str(i),'x'*512+'\r\n"comma,'] for i in range(2049)]
        table=io.StringIO(newline='');csv.writer(table,lineterminator='\n').writerows(rows)
        source=self.root/'stream-input.csv';source.write_bytes(table.getvalue().encode('utf8'))
        expected=io.StringIO(newline='');csv.writer(expected,lineterminator='\r\n').writerows(rows)
        target=self.root/'stream-output.csv';self.successful(exe,b'',source,target,4093,1024)
        self.same_bytes(target.read_bytes(),expected.getvalue().encode('utf8'))
        self.assertGreater(source.stat().st_size,1<<20)
        provider=self.root/'stream-provider.ail'
        provider.write_text('use csv_rewrite_stream; fn rewrite_files(input:str,output:str)->int {'
                            'let reader=open_binary(input,"rb");try {let writer=open_binary(output,"wb");'
                            'try {let n=csv_rewrite_stream(reader,writer,7,1024);writer.flush();return n;}'
                            'finally {writer.close();}} finally {reader.close();}}',encoding='utf8')
        obj=self.build(sdk,environment,provider,'stream-provider.o',command='compile-module');provider.unlink()
        entry=self.root/'stream-entry.ail';entry.write_text('fn main()->int {print(rewrite_files(sys.argv[1],sys.argv[2]));return 0;}',encoding='utf8')
        linked=self.build(sdk,environment,entry,'linked-stream','--object',obj)
        source.write_bytes('"日本語😀",x\r\n"",last'.encode('utf8'))
        self.successful(linked,('2'+os.linesep).encode(),source,target)
        self.assertEqual(target.read_bytes(),'日本語😀,x\r\n,last\r\n'.encode('utf8'))
        source.write_bytes(b'a\n"unfinished');target.write_bytes(b'old')
        failed=self.run_binary(exe,source,target,2,1024)
        self.assertEqual((failed.returncode,failed.stdout),(4,b''));self.assertEqual(target.read_bytes(),b'a\r\n')
        self.assertTrue(marker.is_file())

    def test_relocated_json_source_check_without_c_compiler(self):
        sdk=self.exported();environment,marker=self.environment()
        environment.update(PATH='')
        source=self.root/'LLM source 日本語😀.ail'
        source.write_text('fn plus(x:int)->int {return x+1;} fn main()->int {return plus(2);}',encoding='utf8')
        before=source.read_bytes();result=self.cli(sdk,environment,'check',source,'--interface','--symbol','plus')
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        report=json.loads(result.stdout);self.assertEqual((report['schema'],report['status']),("ail.check/1","passed"))
        self.assertFalse(report['link_verified']);self.assertFalse(report['runtime_verified'])
        self.assertEqual(report['source_sha256'],hashlib.sha256(before).hexdigest())
        self.assertEqual(report['interface']['functions'][0]['name'],'plus')
        self.assertEqual(len(report['interface']['functions']),1)
        self.assertEqual(report['interface']['functions'][0]['returns'],'int')
        api=self.cli(sdk,environment,'api','checked_integer','--symbol','parse_int64_decimal')
        self.assertEqual((api.returncode,api.stderr),(0,b''))
        api_report=json.loads(api.stdout)
        self.assertEqual(api_report['interface']['functions'][0]['name'],'parse_int64_decimal')
        self.assertEqual(len(api_report['interface']['functions']),1)
        self.assertEqual(api_report['source_sha256'],hashlib.sha256((sdk/'language_examples/checked_integer.ail').read_bytes()).hexdigest())
        compact=self.cli(sdk,environment,'api','csv_column_stats','--symbol','csv_column_stats','--types-used')
        self.assertEqual((compact.returncode,compact.stderr),(0,b''))
        compact_api=json.loads(compact.stdout)['interface']
        self.assertEqual(compact_api['struct_selection'],'reachable_declared_types')
        self.assertEqual([item['name'] for item in compact_api['structs']],['IntegerColumnStats'])
        refused=self.cli(sdk,environment,'api','../checked_integer')
        self.assertEqual((refused.returncode,refused.stderr),(2,b''))
        self.assertEqual(json.loads(refused.stdout)['diagnostics'][0]['code'],'configuration')
        source.write_text('# 日本語😀\nfn take(x:int)->int {return x;}\nfn main()->int {return take("wrong");}',encoding='utf8')
        result=self.cli(sdk,environment,'check',source,'--interface')
        self.assertEqual((result.returncode,result.stderr),(1,b''))
        report=json.loads(result.stdout);self.assertNotIn('interface',report)
        diagnostic=report['diagnostics'][0]
        self.assertEqual((diagnostic['path'],diagnostic['line'],diagnostic['column']),(str(source),3,17))
        self.assertEqual((diagnostic['function'],diagnostic['location_kind']),('main','source_statement'))
        self.assertEqual(diagnostic['type_details'],dict(operation='argument',callee='take',
                         parameter='x',parameter_index=0,expected='int',actual='str'))
        repaired=self.cli(sdk,environment,'check',source,'--repair-context')
        self.assertEqual((repaired.returncode,repaired.stderr),(1,b''))
        repair=json.loads(repaired.stdout)['repair_context']
        self.assertEqual((repair['schema'],repair['target'],repair['source_path']),('ail.context/1','main',str(source)))
        self.assertEqual(repair['body'],'return take("wrong");')
        self.assertEqual(repair['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertFalse(repair['type_verified'])
        report_file=self.root/'check-report.json';report_file.write_bytes(repaired.stdout)
        output=self.root/'repaired.ail';original=source.read_bytes()
        edited=self.cli(sdk,environment,'edit',source,'--symbol','main','--base-sha256',repair['source_sha256'],
                        '--body-text','return take(7);','--context',report_file,'-o',output)
        self.assertEqual((edited.returncode,edited.stderr),(0,b''))
        edit_report=json.loads(edited.stdout)
        self.assertEqual(edit_report['context_sha256'],hashlib.sha256(repaired.stdout).hexdigest())
        self.assertEqual(output.read_bytes(),original.replace(b'return take("wrong");',b'return take(7);'))
        self.assertEqual(source.read_bytes(),original)
        source.write_bytes(b'fn widen(value:float)->float {return value;} fn main()->int {print(widen(1));return 0;}')
        widened=self.cli(sdk,environment,'check',source)
        self.assertEqual((widened.returncode,widened.stderr),(0,b''))
        self.assertEqual(json.loads(widened.stdout)['diagnostics'],[])
        source.write_bytes(b'fn main()->int {return "wrong";}')
        result=self.cli(sdk,environment,'check',source,'--repair-context')
        self.assertEqual((result.returncode,result.stderr),(1,b''))
        typed=json.loads(result.stdout)
        self.assertEqual(typed['diagnostics'][0]['type_details'],
                         dict(operation='return',expected='int',actual='str'))
        self.assertEqual(typed['repair_context']['target'],'main')
        report_file.write_bytes(result.stdout)
        typed_output=self.root/'typed-repaired.ail';original=source.read_bytes()
        edited=self.cli(sdk,environment,'edit',source,'--symbol','main',
                        '--base-sha256',typed['source_sha256'],'--body-text',
                        'write_stdout_bytes(b"7");return 0;','--context',report_file,'-o',typed_output)
        self.assertEqual((edited.returncode,edited.stderr),(0,b''))
        self.assertEqual(json.loads(edited.stdout)['candidate_check']['status'],'passed')
        self.assertEqual(source.read_bytes(),original)
        text='# 日本語😀\nfn main()->int {\n if true && false {return 1;}\n return 0;\n}\n'
        source.write_text(text,encoding='utf8');result=self.cli(sdk,environment,'check',source)
        self.assertEqual((result.returncode,result.stderr),(1,b''))
        diagnostic=json.loads(result.stdout)['diagnostics'][0]
        self.assertEqual((diagnostic['line'],diagnostic['column']),(3,text.splitlines()[2].index('&')+1))
        self.assertEqual(source.read_text(encoding='utf8'),text);self.assertTrue(marker.is_file())

    def _check_csv_integer_column_stats(self,main_source):
        from test_csv_column_stats_cli import encoded, oracle
        sdk=self.exported();environment,marker=self.environment();examples=sdk/'language_examples'
        obj=self.build(sdk,environment,examples/'file_identity.c','identity-stats.o',
                       '--interface',examples/'file_identity.json',command='compile-c')
        executable=self.build(sdk,environment,examples/main_source,'csv-integer-stats','--object',obj)
        source,output=self.root/'input CSV 日本語😀.csv',self.root/'stats.tsv'
        data=encoded([['quoted,\r\n😀','9007199254740993'],['last','-9007199254740992']]).rstrip(b'\r\n')
        source.write_bytes(data);output.write_bytes(b'old\0\xff')
        result=self.run_binary(executable,source,output,1)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(output.read_bytes(),oracle(data,'1'));self.assertEqual(source.read_bytes(),data)
        source.write_bytes(b'1\n9223372036854775807\n');output.write_bytes(b'old\0\xff')
        result=self.run_binary(executable,source,output,0)
        self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertTrue(result.stderr)
        self.assertEqual(output.read_bytes(),b'old\0\xff');self.assertTrue(marker.is_file())
    def test_relocated_csv_integer_column_stats(self):
        self._check_csv_integer_column_stats('csv_column_stats_main.ail')

    def test_relocated_standard_source_api_inventory(self):
        sdk=self.exported();environment,marker=self.environment()
        catalog=json.loads((sdk/'language_examples/STANDARD_SOURCE_API.json').read_text(encoding='utf8'))
        self.assertEqual((len(catalog['modules']),catalog['source_check_all_passed']),(26,True))
        self.assertEqual(sum(len(row['declared_api']['functions']) for row in catalog["modules"]),74)
        for name,digest in catalog['dependency_pins'].items():
            self.assertEqual(hashlib.sha256((sdk/name).read_bytes()).hexdigest(),digest)
        result=self.cli(sdk,environment,'api','json_document','--symbol','json_parse_document','--types-used')
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        self.assertEqual([row['name'] for row in json.loads(result.stdout)['interface']['structs']],['JsonValue'])
        self.assertTrue(marker.is_file())
        result=self.cli(sdk,environment,'api','integer_row_stream','--symbol','integer_row_report_stream','--types-used')
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        interface=json.loads(result.stdout)['interface']
        self.assertEqual([row['name'] for row in interface['functions']],['integer_row_report_stream'])
        self.assertEqual([row['type'] for row in interface['functions'][0]['parameters']],['binaryfile','int','int'])
        self.assertEqual(interface['functions'][0]['returns'],'bytes')
        self.assertEqual(interface['structs'],[])

    def test_relocated_integer_row_stream_source_free_result(self):
        from test_integer_row_stream import ENTRY,oracle
        import struct
        sdk=self.exported();environment,marker=self.environment()
        provider=self.root/'provider.ail'
        provider.write_bytes((sdk/'language_examples/integer_row_stream.ail').read_bytes())
        obj=self.build(sdk,environment,provider,'stream.o',command='compile-module')
        provider.unlink()
        entry=self.root/'entry.ail';entry.write_text(ENTRY,encoding='utf8')
        binary=self.build(sdk,environment,entry,'stream-linked','--object',obj)
        values=[(-1 if i%2 else 1)*((1<<53)+37*i) for i in range(8193*3)]
        path=self.root/'input.bin';data=b''.join(struct.pack('<q',v) for v in values);path.write_bytes(data)
        result=self.run_binary(binary,path,'3','65537','0')
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,oracle(values,3),b''))
        self.assertEqual(path.read_bytes(),data);self.assertTrue(marker.is_file())

    def test_relocated_persistent_json_kv_application(self):
        from test_json_kv import reference
        sdk=self.exported();environment,marker=self.environment();examples=sdk/'language_examples'
        obj=self.build(sdk,environment,examples/'file_identity.c','kv-identity.o','--interface',examples/'file_identity.json',command='compile-c')
        executable=self.build(sdk,environment,examples/'json_kv_main.ail','kv','--object',obj)
        source=self.root/'requests 日本語.jsonl';state=self.root/'state 😀.json'
        data=b'{"op":"set","key":"a","value":"v"}\n{"op":"get","key":"a"}\n{"op":"count"}'
        source.write_bytes(data);expected=reference(None,data)
        result=self.run_binary(executable,source,state)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected[0],b''));self.assertEqual(state.read_bytes(),expected[1])
        second=b'{"op":"delete","key":"a"}\n{"op":"count"}'
        source.write_bytes(second);expected=reference(state.read_text(encoding='utf8'),second)
        result=self.run_binary(executable,source,state)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected[0],b''));self.assertEqual(state.read_bytes(),expected[1]);self.assertTrue(marker.is_file())
        source.write_bytes(b'{"op":"set","key":"x","value":"y"}\ninvalid')
        before=state.read_bytes();result=self.run_binary(executable,source,state)
        self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertEqual(state.read_bytes(),before)
    def test_relocated_persistent_json_kv_tcp_service(self):
        import socket
        from test_ail_tcp_listener import RunningServer
        from test_json_kv import reference
        sdk=self.exported();environment,marker=self.environment()
        executable=self.build(sdk,environment,sdk/'language_examples/json_kv_tcp_main.ail','kv-service')
        state=self.root/'network state 😀.json';current=None
        batches=[b'{"op":"set","key":"a","value":"v"}\n{"op":"count"}',b'{"op":"get","key":"a"}\n{"op":"delete","key":"a"}']
        with RunningServer(executable,(0,state,2,3000)) as server:
            for data in batches:
                expected,snapshot=reference(current,data)
                with socket.create_connection(('127.0.0.1',server.port),timeout=5) as peer:
                    peer.settimeout(10);peer.sendall(data);peer.shutdown(socket.SHUT_WR);actual=bytearray()
                    while chunk:=peer.recv(4096):actual.extend(chunk)
                self.assertEqual(bytes(actual),expected);self.assertEqual(state.read_bytes(),snapshot);current=snapshot.decode()
            self.assertEqual(server.finish(),(f'4{os.linesep}'.encode(),b''))
        self.assertTrue(marker.is_file())
    def test_source_free_csv_integer_value_object(self):
        sdk=self.exported();environment,marker=self.environment()
        module=sdk/'language_examples/csv_column_stats.ail'
        obj=self.build(sdk,environment,module,'csv-value.o',command='compile-module')
        project=self.root/'source-free caller';project.mkdir()
        entry=project/'main.ail'
        entry.write_text(r'fn main()->int {let stats:IntegerColumnStats=csv_column_stats("m,9007199254740993\nm,-9007199254740992",1);write_stdout_bytes(integer_column_stats_render(stats).encode());return 0;}',encoding='utf8')
        executable=self.build(sdk,environment,entry,'value-caller','--object',obj)
        result=self.run_binary(executable)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'2\t1\t-9007199254740992\t9007199254740993\n',b''))
        self.assertTrue(marker.is_file())
    def test_relocated_stream_csv_integer_column_stats(self):
        self._check_csv_integer_column_stats('csv_column_stats_stream_main.ail')
    def test_doctor_reports_configured_compiler_and_no_fallback(self):
        import ail_chatgpt
        from contextlib import redirect_stdout
        from unittest.mock import patch
        for requested, available in ((sys.executable, True), ('ail-missing-compiler-653', False)):
            output = io.StringIO()
            with patch.dict(os.environ, {'PIPE_CC': requested}), redirect_stdout(output):
                status = ail_chatgpt.main(['doctor'])
            report = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(report['c_compiler_configured'], requested)
            self.assertEqual(report['c_compiler_available'], available)
            self.assertEqual(report['c_compiler'], shutil.which(requested))
        with patch.dict(os.environ, {'PIPE_CC': ''}), patch.object(ail_chatgpt.shutil, 'which',
                side_effect=lambda name: '/compiler/clang' if name in ('clang', '/compiler/clang') else None):
            output = io.StringIO()
            with redirect_stdout(output):ail_chatgpt.main(['doctor'])
        self.assertEqual(json.loads(output.getvalue())['c_compiler'], '/compiler/clang')

    def test_sdk_files_cover_every_compiler_module_import(self):
        # The exported compiler must carry every python/pkg-v12 module that a shipped .py file imports
        # (jsonrt.py once imported unconditionally by cruntime.py was missing from a copied subset).
        import ast
        manifest = json.loads((support.ROOT / 'MANIFEST.json').read_text(encoding='utf8'))
        shipped = set(manifest['sdk_files'])
        package = support.ROOT / 'python/pkg-v12'
        modules = {path.stem for path in package.glob('*.py')}
        missing = set()
        for name in sorted(shipped):
            if not name.endswith('.py'):
                continue
            tree = ast.parse((support.ROOT / name).read_text(encoding='utf8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    imported = [node.module.split('.')[0]]
                else:
                    continue
                for module in imported:
                    if module in modules and 'python/pkg-v12/' + module + '.py' not in shipped:
                        missing.add((name, module))
        self.assertEqual(sorted(missing), [])

    def test_declared_distribution_excludes_unadopted_files_and_checks_closure(self):
        exporter = importlib.import_module('ail_sdk').export_sdk
        sdk = self.exported()
        manifest_path = sdk / 'MANIFEST.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf8'))
        self.assertEqual(set(manifest['sdk_files']), set(manifest['sha256']) - {'SDK_README_JA.md'})
        (sdk / 'language_examples/unadopted.ail').write_text('invalid research source', encoding='utf8')
        copied = exporter(sdk, self.root / 'with-unadopted')
        self.assertEqual(copied['sha256'], manifest['sha256'])
        self.assertNotIn('language_examples/unadopted.ail', copied['sdk_files'])
        # The legacy discovery path remains supported for older SDKs.
        legacy = dict(manifest)
        legacy.pop('sdk_files')
        (sdk / 'language_examples/unadopted.ail').unlink()
        manifest_path.write_text(json.dumps(legacy), encoding='utf8')
        self.assertEqual(exporter(sdk, self.root / 'legacy-copy')['sha256'], manifest['sha256'])
        names = manifest['sdk_files']
        malformed = (None, [], 'not a list', names + [names[0]], names + ['../outside'],
                     names + ['/absolute'], names + ['C:/drive'], names + ['a\\b'],
                     names + ['a//b'], names + [7], names + ['MANIFEST.json'],
                     [name for name in names if name != 'ailc.py'])
        for index, selection in enumerate(malformed):
            with self.subTest(selection=index):
                value = dict(manifest, sdk_files=selection)
                manifest_path.write_text(json.dumps(value), encoding='utf8')
                destination = self.root / f'refused{index}'
                with self.assertRaises((ValueError, OSError)):
                    exporter(sdk, destination)
                self.assertFalse(destination.exists())
        # Existing C interface dependencies cannot disappear from a fixed selection.
        interface = json.loads((sdk / 'language_examples/asm_checksum.json').read_text(encoding='utf8'))
        dependencies = [name for field in ('headers', 'sources', 'asm_sources', 'archives')
                        for name in interface.get(field, [])]
        self.assertTrue(dependencies)
        missing = 'language_examples/' + dependencies[0]
        manifest_path.write_text(json.dumps(dict(manifest, sdk_files=[n for n in names if n != missing])), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'missing C interface inputs'):
            exporter(sdk, self.root / 'missing-dependency')
        self.assertFalse((self.root / 'missing-dependency').exists())

    def test_stale_standard_api_inventory_refused_before_output(self):
        exporter=importlib.import_module('ail_sdk').export_sdk
        sdk=self.exported();manifest_path=sdk/'MANIFEST.json';original=json.loads(manifest_path.read_text(encoding='utf8'))
        catalog_path=sdk/'language_examples/STANDARD_SOURCE_API.json';catalog=json.loads(catalog_path.read_text(encoding='utf8'))
        changed=sdk/'language_examples/json_text.ail';changed.write_bytes(changed.read_bytes()+b'\n# changed dependency\n')
        manifest=dict(original);manifest['sha256']=dict(original['sha256']);manifest['sha256']['language_examples/json_text.ail']=hashlib.sha256(changed.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest),encoding='utf8')
        destination=self.root/'stale-copy'
        with self.assertRaisesRegex(ValueError,'standard API dependency'):exporter(sdk,destination)
        self.assertFalse(destination.exists())
        variants=[{**catalog,'dependency_pins':{}},{**catalog,'dependency_pins':{'../outside':'bad'}},{**catalog,'modules':[{'source':'missing','sha256':'bad'}]},{**catalog,'modules':[{'source':[],'sha256':'bad'}]}]
        for index,value in enumerate(variants):
            # Restore dependency bytes so the module-row/schema gates are exercised.
            changed.write_bytes((support.ROOT/'language_examples/json_text.ail').read_bytes())
            catalog_path.write_text(json.dumps(value),encoding='utf8');manifest=json.loads(json.dumps(original));manifest['sha256']['language_examples/STANDARD_SOURCE_API.json']=hashlib.sha256(catalog_path.read_bytes()).hexdigest();manifest_path.write_text(json.dumps(manifest),encoding='utf8')
            destination=self.root/f'bad-catalog{index}'
            with self.assertRaises(ValueError):exporter(sdk,destination)
            self.assertFalse(destination.exists())
    def test_metadata_destination_integrity_and_legacy_command_refusals(self):
        exporter = importlib.import_module('ail_sdk').export_sdk
        sdk = self.exported()
        manifest = json.loads((sdk / 'MANIFEST.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['kind'], 'ail_language_sdk')
        self.assertTrue((sdk / 'SDK_README_JA.md').is_file())
        self.assertIn('ail_chatgpt.py', manifest['sha256'])
        self.assertTrue(any(name.endswith('.ail') for name in manifest['sha256']))
        self.assertFalse(any(part in ('workflow', 'weights', 'timinghistory')
                             for name in manifest['sha256'] for part in Path(name).parts))
        copied = exporter(sdk, self.root / 'sdk-copy')
        self.assertEqual(copied['sha256'], manifest['sha256'])
        existing = self.root / 'existing'
        existing.mkdir()
        sentinel = existing / 'keep'
        sentinel.write_bytes(b'unchanged')
        for destination in (existing, sdk / 'nested', sdk.parent):
            with self.subTest(destination=destination), self.assertRaises((ValueError, OSError)):
                exporter(sdk, destination)
        self.assertEqual(sentinel.read_bytes(), b'unchanged')
        self.assertFalse((sdk / 'nested').exists())
        environment, marker = self.environment()
        legacy = self.cli(sdk, environment, 'selftest', '--out', self.root / 'legacy-output')
        self.assertNotEqual(legacy.returncode, 0)
        self.assertIn(b'SDK', legacy.stderr)
        compiler = sdk / 'ail_chatgpt.py'
        compiler.write_bytes(compiler.read_bytes() + b'\n# deliberate integrity mismatch\n')
        rejected_output = self.root / 'must-not-exist'
        with self.assertRaises((ValueError, OSError)):
            exporter(sdk, rejected_output)
        self.assertFalse(rejected_output.exists())
        self.assertTrue(marker.is_file())


if __name__ == '__main__':
    unittest.main()
