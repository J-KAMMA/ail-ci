"""Opt-in ownership/call facts stay conservative, source-bound and compact compatible."""
import ast
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch

import ail_chatgpt
from ail_api_contracts import build_contracts, validate_contracts
from ail_source_context import context, compact_context, expand_context
import test_ail_source_check as support


def entry(payload,name,kind='source'):
    return next(item for item in payload['entries'] if item['name']==name and item['kind']==kind)


class ApiContractsTests(unittest.TestCase):
    setUp=support.SourceCheckTests.setUp
    source=support.SourceCheckTests.source

    def cli(self,*args):
        output=io.StringIO()
        with patch.dict(os.environ,{'PATH':''}),patch.object(ail_chatgpt.subprocess,'run',side_effect=AssertionError('no subprocess')),patch.object(ail_chatgpt.subprocess,'Popen',side_effect=AssertionError('no subprocess')),redirect_stdout(output):
            status=ail_chatgpt.main(list(map(str,args)))
        return status,json.loads(output.getvalue())

    def test_opt_in_interface_default_and_compact_are_compatible(self):
        source=self.source('fn target(value:int)->int {print(value);return value;} fn main()->int {return target(1);}')
        status,plain=self.cli('check',source,'--interface')
        self.assertEqual(status,0,plain);self.assertNotIn('contracts',plain)
        status,rich=self.cli('check',source,'--interface','--contracts')
        self.assertEqual(status,0,rich);contracts=rich.pop('contracts');self.assertEqual(plain,rich)
        self.assertEqual(contracts['schema'],'ail.api_contracts/1')
        default=context(source.read_bytes(),'target')
        rich=context(source.read_bytes(),'target',contracts=True)
        self.assertNotIn('contracts',default)
        expanded=expand_context(compact_context(rich))
        self.assertEqual(expanded,rich);expanded.pop('contracts');self.assertEqual(expanded,default)
        self.assertIn('output',entry(contracts,'target')['effects']['values'])
        self.assertEqual(entry(contracts,'print','builtin')['kind'],'builtin')
        status,report=self.cli('check',source,'--contracts')
        self.assertEqual(status,2,report)

    def test_declared_ownership_covers_all_types_without_type_proof(self):
        source=b'''struct Box {value:int;}
fn target(number:int,text:str,data:bytes,ints:list[int],floats:list[float],texts:list[str],blobs:list[bytes],handles:list[exception],box:Box,buffer:bytearray,error:exception,unknown:Mystery)->list[str] {return ["x"];}
'''
        report=context(source,'target',contracts=True)
        item=entry(report['contracts'],'target');by_name={value['name']:value for value in item['parameters']}
        for name in ('text','data','ints','floats','texts'):
            self.assertEqual((by_name[name]['ownership'],by_name[name]['access']),('borrowed_view','readonly'))
        for name in ('blobs','handles','box','buffer'):
            self.assertEqual((by_name[name]['ownership'],by_name[name]['access']),('borrowed_reference','mutable'))
        self.assertEqual(by_name['error']['access'],'readonly')
        self.assertEqual(by_name['unknown']['ownership'],'unknown')
        self.assertEqual(item['result']['ownership'],'owned_snapshot')
        for key in ('type_verified','binding_verified','runtime_verified'):self.assertFalse(item['provenance'][key])

    def test_shadow_alias_callback_recursive_and_operator_errors_are_unknown(self):
        source=b'''fn print(value:int)->int {return value;}
fn target(cb:Callable[[int],int],value:int)->int {let alias=print;return cb(alias(value));}
fn recursive(value:int)->int {return recursive(value);}
fn divide(value:int)->int {return 7//value;}
fn indexed(values:list[int],index:int)->int {return values[index];}
'''
        for name in ('target','recursive','divide','indexed'):
            item=entry(context(source,name,contracts=True)['contracts'],name)
            self.assertFalse(item['raises']['known'],name)
            self.assertFalse(item['fatal']['known'],name)
        report=context(source,'target',contracts=True)['contracts']
        self.assertFalse(entry(report,'cb','unresolved')['effects']['known'])
        self.assertFalse(any(item['kind']=='builtin' and item['name']=='print' for item in report['entries']))
        root=context(b'const len=7; fn target()->int {return len("x");}','target',contracts=True)['contracts']
        self.assertFalse(entry(root,'len','unresolved')['effects']['known'])
        methods=context(b'struct Box {value:int;} impl Box {fn known(self)->int {return self.value;} fn target(self)->int {return self.known();}}','Box.target',contracts=True)['contracts']
        self.assertFalse(entry(methods,'Box.target')['effects']['known'])

    def test_owned_returns_literals_and_local_cleanup_do_not_claim_no_fatal(self):
        source=b'fn borrowed(text:str)->str {return text;} fn literal()->str {return "text";} fn cleanup(text:str)->int {let local=text;return 0;} fn wrapper(text:str)->int {borrowed(text);return 0;}'
        for name in ('borrowed','literal','cleanup','wrapper'):
            with self.subTest(name=name):
                item=entry(context(source,name,contracts=True)['contracts'],name)
                self.assertFalse(item['fatal']['known'])
                self.assertFalse(item['effects']['known'])

    def test_catch_finally_reraise_and_unclassified_calls_are_not_closed_sets(self):
        source=b'''fn target()->int {try {raise ValueError("x");} except ValueError {missing();raise;} finally {print(1);}return 0;}'''
        item=entry(context(source,'target',contracts=True)['contracts'],'target')
        self.assertFalse(item['raises']['known']);self.assertIn('ValueError',item['raises']['values'])
        self.assertFalse(item['effects']['known']);self.assertFalse(item['fatal']['known'])
        self.assertFalse(entry(context(source,'target',contracts=True)['contracts'],'missing','unresolved')['signature_known'])

    def test_imported_real_bodies_sha_and_invalid_target_context_survive_edit(self):
        dependency=self.source('fn input(path:str)->bytes {return read_bytes(path);}','library.ail')
        source=self.source('use library; fn target()->int {return input("path");}')
        rich=context(source.read_bytes(),'target',source_path=source,resolve_imports=True,contracts=True)
        item=entry(rich['contracts'],'input')
        self.assertIn('filesystem_io',item['effects']['values'])
        self.assertTrue(item['provenance']['body_available'])
        self.assertEqual(item['provenance']['source_sha256'],hashlib.sha256(dependency.read_bytes()).hexdigest())
        self.assertFalse(rich['type_verified']);self.assertFalse(item['provenance']['runtime_verified'])
        transport=self.source(json.dumps(compact_context(rich),ensure_ascii=False),'context.json')
        candidate=self.root/'candidate.ail'
        status,report=self.cli('edit',source,'--symbol','target','--base-sha256',rich['source_sha256'],'--body-text','return 1;','--context',transport,'--library','-o',candidate)
        self.assertEqual(status,0,report);self.assertTrue(candidate.is_file())
        dependency.write_text('fn input(path:str)->bytes {return b"changed";}',encoding='utf8')
        status,report=self.cli('edit',source,'--symbol','target','--base-sha256',rich['source_sha256'],'--body-text','return 2;','--context',transport,'--library','-o',self.root/'stale.ail')
        self.assertNotEqual(status,0,report);self.assertFalse((self.root/'stale.ail').exists())

    def test_api_all_declarations_and_malformed_contracts(self):
        status,report=self.cli('api','checked_integer','--contracts')
        self.assertEqual(status,0,report)
        named={item['name'] for item in report['contracts']['entries'] if item['kind']=='source'}
        self.assertTrue({item['name'] for item in report['interface']['functions']}<=named)
        malformed=copy.deepcopy(report['contracts']);malformed['entries'][0]['provenance']['runtime_verified']=True
        with self.assertRaises(ValueError):validate_contracts(malformed)
        malformed=copy.deepcopy(report['contracts']);malformed['entries'][0]['effects']['known']=True;malformed['entries'][0]['effects']['unknown_reasons']=['unknown']
        with self.assertRaises(ValueError):validate_contracts(malformed)
        malformed=copy.deepcopy(report['contracts']);malformed['entries'][0]['result']['ownership']='owned_magic'
        with self.assertRaises(ValueError):validate_contracts(malformed)
        for group,key,value in [('entry','kind',[]),('result','ownership',[]),('result','access',[]),('payload','registry_version',True),('proof','body_available',[]),('proof','registry_version',True),('entry','calls',[{'name':'callee','kind':[]}])]:
            malformed=copy.deepcopy(report['contracts'])
            target=malformed if group=='payload' else malformed['entries'][0]['result'] if group=='result' else malformed['entries'][0]['provenance'] if group=='proof' else malformed['entries'][0]
            target[key]=value
            with self.subTest(group=group,key=key),self.assertRaises(ValueError):validate_contracts(malformed)
        rich=context(b'fn target()->int {return 1;}','target',contracts=True)
        rich['contracts']['registry_version']=99
        with self.assertRaises(ValueError):compact_context(rich)


if __name__=='__main__':unittest.main()