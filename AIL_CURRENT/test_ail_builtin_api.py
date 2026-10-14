"""Staged declarations checked against actual initial-profile compiler, without native runs."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('staged_builtin_api',HERE/'ail_builtin_api.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)


SOURCE_ROOT=HERE

def query(symbol=None):return api.query(symbol,source_root=SOURCE_ROOT)

def item(name):return query(name)['entries'][0]


def probe(symbol,o):
    params=[('v'+str(i),p['type']) for i,p in enumerate(o['parameters'])]
    args=','.join(p[0] for p in params); prefix=''; receiver=o['receiver']
    if receiver:
        params.insert(0,('source',receiver['type']))
        prefix=('let receiver:'+receiver['type']+'=[];' if receiver['type'] in ('list[int]','list[float]','list[str]') else 'let receiver=source;')
        if receiver['type'].startswith('dict[str,'):
            prefix='let receiver:'+receiver['type']+'=source.copy();'
        expr='receiver.'+symbol.split('.',1)[1]
    elif symbol=='open(path).read':expr='open(v0).read';args=''
    else:expr=symbol
    if o['context']!='property':expr+='('+args+')'
    result=o['result']['type'];body=prefix+(expr+';return;' if result=='void' else 'let output:'+result+'='+expr+';return output;')
    return 'fn probe('+','.join(n+':'+t for n,t in params)+')->'+result+' {'+body+'}'
class BuiltinApiTests(unittest.TestCase):
    def test_inventory_is_explicit_and_unknown_does_not_mean_zero_arity(self):
        payload=query()
        self.assertEqual(payload['schema'],'ail.builtin_api/1')
        self.assertFalse(payload['coverage']['complete'])
        symbols={entry['symbol'] for entry in payload['entries']}
        for name in ('open_binary','binaryfile.read','binaryfile.close','get_env','current_dir','list_dir','tcp_connect','tcp_listen','tcp_poll','tcpsocket.send_some','tcpsocket.recv_into','tcpsocket.wait_readable','tcpsocket.set_blocking','integer_decode','ValueError'):
            self.assertIn(name,symbols)
        search=item('str.find')
        self.assertTrue(search['signature_known'])
        self.assertEqual([len(o['parameters']) for o in search['overloads']],[1,2,3])
        unknown=item('not_a_real_builtin')
        self.assertFalse(unknown['signature_known']);self.assertEqual(unknown['overloads'],[])
        self.assertFalse(unknown['fatal']['known'])
        self.assertIn('range',payload['coverage']['unknown_symbols'])
        with self.assertRaises(ValueError):query([])

    def test_context_forms_are_separate_from_callable_signatures(self):
        payload=query()
        entries={e['symbol']:e for e in payload['entries']}
        for name in ('range','enumerate','reversed','zip','map','open','print'):
            with self.subTest(symbol=name):
                entry=entries[name]
                self.assertFalse(entry['signature_known'])
                self.assertEqual(entry['overloads'],[])
                self.assertEqual(len(entry['syntax_forms']),1)
                form=entry['syntax_forms'][0]
                self.assertFalse(form['ordinary_call_signature_published'])
                self.assertFalse(form['compile_verified'])
                self.assertFalse(form['runtime_verified'])
                self.assertIsNone(form['generic_iterator_result_type'])
                self.assertIsNotNone(form['references'][0]['line'])
                self.assertEqual(form['references'][0]['sha256'],entries['str.find']['references'][0]['sha256'])
        self.assertEqual(item('missing')['syntax_forms'],[])
    def test_resource_signatures_and_ownership_match_real_type_checks(self):
        self.assertIsNotNone(SOURCE_ROOT)
        sys.path.insert(0,str(SOURCE_ROOT));sys.path.insert(0,str(SOURCE_ROOT/'python/pkg-v12'))
        try:
            from ail_syntax import translate
            from pyfunc import to_c, Unsupported
            cases={
                'open_binary':('binaryfile','fn probe(path:str)->binaryfile {return open_binary(path,"r");}'),
                'binaryfile.read':('bytes','fn probe(file:binaryfile)->bytes {return file.read(8);}'),
                'tcpsocket.send_some':('int','fn probe(socket:tcpsocket)->int {return socket.send_some(b"x");}'),
                'tcpsocket.recv_into':('int','fn probe(socket:tcpsocket,buffer:bytearray)->int {return socket.recv_into(buffer);}'),
                'get_env':('str','fn probe()->str {return get_env("AIL_TEST","fallback");}'),
                'current_dir':('str','fn probe()->str {return current_dir();}'),
                'list_dir':('list[str]','fn probe(path:str)->list[str] {return list_dir(path);}'),
                'tcp_poll':('list[int]','fn probe(peers:list[tcpsocket],masks:list[int])->list[int] {return tcp_poll(peers,masks,0);}'),
                'integer_decode':('list[int]','fn probe(data:bytes)->list[int] {return integer_decode(data,2,0);}'),
                'ValueError':('exception','fn probe()->exception {return ValueError("message");}'),
            }
            for name,(result,source) in cases.items():
                with self.subTest(symbol=name):
                    declared=item(name)
                    self.assertIn(result,{overload['result']['type'] for overload in declared['overloads']})
                    self.assertIsNotNone(declared['references'][0]['line'])
                    to_c(translate(source+' fn main()->int {return 0;}'),name='run',strict=True)
            wrong='fn probe(file:binaryfile)->bytes {return file.read("wrong");} fn main()->int {return 0;}'
            with self.assertRaises(Unsupported):to_c(translate(wrong),name='run',strict=True)
        finally:
            sys.path.pop(0);sys.path.pop(0)

    def test_every_published_overload_compiles_in_its_declared_profile(self):
        sys.path[:0]=[str(SOURCE_ROOT),str(SOURCE_ROOT/'python/pkg-v12')]
        try:
            from ail_syntax import translate
            from pyfunc import to_c, Unsupported
            for entry in query()['entries']:
                for overload in entry['overloads']:
                    with self.subTest(symbol=entry['symbol'],parameters=overload['parameters']):
                        to_c(translate(probe(entry['symbol'],overload),module=True),name='probe',strict=True,library=True)
        finally:del sys.path[:2]
    def test_receiver_alias_contracts_and_declarations_do_not_claim_effect_proof(self):
        file=item('binaryfile.read')
        self.assertTrue(file['overloads'][0]['receiver']['mutable'])
        self.assertEqual(file['overloads'][0]['result']['ownership'],'owned_snapshot')
        buffer=item('bytearray.copy')
        self.assertEqual(buffer['overloads'][0]['result']['ownership'],'owned_reference')
        for entry in query()['entries']:
            self.assertFalse(entry['effects']['known']);self.assertFalse(entry['fatal']['known']);self.assertFalse(entry['runtime_verified'])
        before=item('tcp_connect');before['overloads'].clear()
        self.assertTrue(item('tcp_connect')['overloads'])


if __name__=='__main__':unittest.main()