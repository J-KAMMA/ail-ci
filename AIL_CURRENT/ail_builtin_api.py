"""Declared builtin API. No source execution, binding proof or closed effect inference."""
import ast
import copy
import hashlib
from pathlib import Path
import re
from ail_builtin_syntax_forms import forms_for, SYNTAX_FORMS

SCHEMA='ail.builtin_api/1'
VERSION=1
ROOT=Path(__file__).resolve().parent
if not (ROOT/'python/pkg-v12/pyfunc.py').is_file():
    ROOT=None
DECLARATIONS={}


def _ownership(kind,result=False):
    if kind in ('int','float'):return ('value','readonly')
    if kind=='void':return ('none','none')
    if kind in ('str','bytes'):return ('owned_snapshot' if result else 'borrowed_view','readonly')
    if kind in ('dict[str,int]','dict[str,float]','dict[str,str]','dict[str,bytes]'):
        return ('owned_snapshot' if result else 'borrowed_view','mutable' if result else 'readonly')
    if kind in ('bytearray','binaryfile','tcpsocket','exception'):
        return ('owned_reference' if result else 'borrowed_reference','readonly' if kind=='exception' else 'mutable')
    if kind in ('list[int]','list[float]','list[str]'):
        return ('owned_snapshot' if result else 'borrowed_view','mutable' if result else 'readonly')
    if kind in ('list[bytes]','list[exception]','list[bytearray]','list[binaryfile]','list[tcpsocket]'):
        return ('owned_reference' if result else 'borrowed_reference','mutable')
    return ('unknown','unknown')


def _value(kind,result=False):
    ownership,access=_ownership(kind,result)
    return dict(type=kind,ownership=ownership,access=access)


def _add(symbol,params,result,anchor,*,receiver=None,mutable=False,errors=(),constraints=(),context='expression'):
    entry=DECLARATIONS.setdefault(symbol,dict(symbol=symbol,classification='declaration',signature_known=True,overloads=[],source_anchor=anchor,known_errors=sorted(set(errors))))
    entry['known_errors']=sorted(set(entry['known_errors'])|set(errors))
    entry['overloads'].append(dict(parameters=[dict(name=name,**_value(kind)) for name,kind in params],result=_value(result,True),
                                  receiver=None if receiver is None else (_value(receiver)|dict(mutable=mutable,access='mutable' if mutable else 'readonly')),constraints=list(constraints),context=context))


# File/process/environment/directory/network are initial-profile intrinsic operations.
for name,params,result,anchor,errors in [
    ('open_binary',[('path','str'),('mode','str')],'binaryfile','_binaryfile_value',('ValueError','OSError')),
    ('read_bytes',[('path','str')],'bytes','_bytes_value',('ValueError','OSError')),
    ('read_stdin_bytes',[('size','int')],'bytes','_bytes_value',('ValueError','OSError')),
    ('write_bytes',[('path','str'),('data','bytes')],'void','_stmt_inner',('ValueError','OSError')),
    ('append_bytes',[('path','str'),('data','bytes')],'void','_stmt_inner',('ValueError','OSError')),
    ('write_text',[('path','str'),('text','str')],'void','_stmt_inner',('ValueError','OSError')),
    ('write_stdout_bytes',[('data','bytes')],'void','_stmt_inner',('OSError',)),
    ('flush_stdout',[],'void','_stmt_inner',('OSError',)),
    ('get_env',[('name','str'),('default','str')],'str','_osconfig_str_value',('ValueError','OSError','UnicodeDecodeError')),
    ('current_dir',[],'str','_osconfig_str_value',('OSError','UnicodeDecodeError')),
    ('list_dir',[('path','str')],'list[str]','_call',('ValueError','OSError','UnicodeDecodeError')),
    ('path_exists',[('path','str')],'int','_call',('ValueError','OSError')),
    ('is_dir',[('path','str')],'int','_call',('ValueError','OSError')),
    ('file_size',[('path','str')],'int','_call',('ValueError','OSError')),
    ('same_file',[('first','str'),('second','str')],'int','_call',('ValueError','OSError')),
    ('make_dir',[('path','str')],'void','_fsmutate_statement',('ValueError','OSError')),
    ('remove_file',[('path','str')],'void','_fsmutate_statement',('ValueError','OSError')),
    ('remove_dir',[('path','str')],'void','_fsmutate_statement',('ValueError','OSError')),
    ('replace_path',[('source','str'),('destination','str')],'void','_fsmutate_statement',('ValueError','OSError')),
    ('tcp_connect',[('host','str'),('port','int')],'tcpsocket','_tcpsocket_value',('ValueError','OSError')),
    ('tcp_listen',[('host','str'),('port','int'),('backlog','int')],'tcpsocket','_tcpsocket_value',('ValueError','OSError')),
    ('tcp_poll',[('peers','list[tcpsocket]'),('interests','list[int]'),('milliseconds','int')],'list[int]','_tcp_poll_value',('ValueError','OSError')),
    ('monotonic_ms',[],'int','_monotonic_arguments',('OSError',)),
]:
    _add(name,params,result,anchor,errors=errors,context='statement' if result=='void' else 'expression')
for name in ('write_bytes','append_bytes'):_add(name,[('path','str'),('data','bytearray')],'void','_stmt_inner',context='statement')
_add('write_stdout_bytes',[('data','bytearray')],'void','_stmt_inner',context='statement')
_add('input',[],'str','_str_value',errors=('EOFError',))
_add('open(path).read',[('path','str')],'str','_str_value',errors=('ValueError','OSError'),constraints=('inline expression only; bare open is not a public file handle type',))

for name,params,result in [
    ('read',[('size','int')],'bytes'),('readinto',[('buffer','bytearray')],'int'),
    ('write',[('data','bytes')],'int'),('write',[('data','bytearray')],'int'),
    ('seek',[('offset','int')],'int'),('seek',[('offset','int'),('whence','int')],'int'),
    ('tell',[],'int'),('flush',[],'void'),('close',[],'void')]:
    _add('binaryfile.'+name,params,result,'_binaryfile_method',receiver='binaryfile',mutable=True,errors=('ValueError','OSError'),context='statement' if result=='void' else 'expression')
for name,params,result in [
    ('recv',[('size','int')],'bytes'),('recv_into',[('buffer','bytearray')],'int'),
    ('send',[('data','bytes')],'int'),('send',[('data','bytearray')],'int'),
    ('send_some',[('data','bytes')],'int'),('send_some',[('data','bytearray')],'int'),
    ('accept',[],'tcpsocket'),('local_port',[],'int'),('wait_readable',[('milliseconds','int')],'int'),
    ('wait_writable',[('milliseconds','int')],'int'),('set_blocking',[('enabled','int')],'void'),
    ('shutdown_write',[],'void'),('close',[],'void')]:
    _add('tcpsocket.'+name,params,result,'_tcpsocket_method',receiver='tcpsocket',mutable=True,errors=('ValueError','OSError'),context='statement' if result=='void' else 'expression')
for kind in ('binaryfile','tcpsocket'):_add(kind+'.closed',[],'int','_closed_ref_kind',receiver=kind,context='property')

# Concrete scalar/text/buffer overloads. Additional overloads are not silently invented.
for name,inputs,output in [('int',('int','float','str'),'int'),('float',('int','float','str'),'float'),('str',('int','float'),'str'),('abs',('int','float'),None),('ord',('str',),'int'),('chr',('int',),'str'),('hex',('int',),'str')]:
    for kind in inputs:_add(name,[('value',kind)],output or kind,'_call',errors=('ValueError',) if kind=='str' and name in ('int','float') or kind=='float' and name=='int' else ())
for kind in ('float',):
    _add('round',[('value',kind)],'int','_call')
    _add('round',[('value',kind),('digits','int')],kind,'_call')
for kind in ('str','bytes','bytearray','list[int]','list[float]','list[str]','list[bytes]','list[exception]','list[bytearray]','list[binaryfile]','list[tcpsocket]'):_add('len',[('value',kind)],'int','_call')
for kind in ('list[int]','list[float]'):
    scalar='int' if kind=='list[int]' else 'float'
    for name in ('sum','min','max'):_add(name,[('values',kind)],scalar,'_call',errors=('ValueError',) if name!='sum' else ())
    for name in ('min','max'):_add(name,[('first',scalar),('second',scalar)],scalar,'_call')
for name in ('any','all'):
    for kind in ('list[int]','list[float]'):_add(name,[('values',kind)],'int','_call')
for name,params,result in [
    ('integer_decode',[('data','bytes'),('width','int'),('byteorder','int')],'list[int]'),
    ('integer_encode',[('values','list[int]'),('width','int'),('byteorder','int')],'bytes'),
    ('float64_decode',[('data','bytes'),('byteorder','int')],'list[float]'),
    ('float64_encode',[('values','list[float]'),('byteorder','int')],'bytes'),
    ('pcm16_scale_le',[('data','bytes'),('numerator','int'),('denominator','int')],'bytes')]:
    constraints = ()
    if name.startswith('integer'):
        constraints = ('exactly three positional arguments; no keywords',
                       'width is 1, 2, 4 or 8; widths 1/2/4 are unsigned and width 8 is signed int64',
                       'byteorder 0 is little endian and 1 is big endian; bool follows integer 0/1',
                       'invalid width/order raises ValueError even for empty input; validation order is width, order, span, then value range or record length',
                       'encode values for width 1/2/4 must be in [0, 2**(8*width)-1]' if name.endswith('encode') else 'decode byte length must be divisible by width',
                       'flat integer lists only; record and nested containers remain unsupported' if name.endswith('encode') else 'decode reads an immutable bytes input')
    elif name.startswith('float64'):
        constraints = ('exactly two positional arguments; no keywords',
                       'byteorder 0 is little endian and 1 is big endian; bool follows integer 0/1',
                       'invalid byteorder raises ValueError even for empty input; empty valid input returns an empty result',
                       'flat float lists only; integer/mixed literals and tuples are refused' if name.endswith('encode') else 'decode byte length must be divisible by 8')
    _add(name,params,result,'_integer_codec_value' if name.startswith('integer') else '_float64_codec_value' if name.startswith('float64') else '_pcm16_scale_value',errors=('ValueError',),constraints=constraints)
for kind in ('bytes','bytearray','list[int]'):_add('bytes',[('value',kind)],'bytes','_bytes_value',errors=('ValueError',))
for kind in ('bytes','bytearray'):_add('bytearray',[('value',kind)],'bytearray','_bytearray_value',errors=('ValueError',))
_add('bytearray',[],'bytearray','_bytearray_value')
for name,params,result in [('encode',[],'bytes'),('lower',[],'str'),('upper',[],'str'),('strip',[],'str'),('strip',[('chars','str')],'str'),('lstrip',[],'str'),('lstrip',[('chars','str')],'str'),('rstrip',[],'str'),('rstrip',[('chars','str')],'str'),('isdigit',[],'int'),('isalpha',[],'int'),('isalnum',[],'int'),('isdecimal',[],'int'),('isnumeric',[],'int'),('isspace',[],'int'),('isupper',[],'int'),('islower',[],'int'),('istitle',[],'int'),('split',[],'list[str]'),('split',[('separator','str')],'list[str]'),('split',[('separator','str'),('maxsplit','int')],'list[str]'),('rsplit',[],'list[str]'),('rsplit',[('separator','str')],'list[str]'),('rsplit',[('separator','str'),('maxsplit','int')],'list[str]'),('splitlines',[],'list[str]'),('join',[('values','list[str]')],'str'),('replace',[('old','str'),('new','str')],'str'),('replace',[('old','str'),('new','str'),('count','int')],'str')]:
    _add('str.'+name,params,result,'_str_value',receiver='str',constraints=('immutable receiver; existing encoding/case domain restrictions apply',))
for name in ('find','rfind','index','rindex','count','startswith','endswith'):
    for params in ([('text','str')],[('text','str'),('start','int')],[('text','str'),('start','int'),('end','int')]):
        _add('str.'+name,params,'int','_method',receiver='str',errors=('ValueError',) if name in ('index','rindex') else ())
for name,params,result in [('decode',[],'str'),('hex',[],'str'),('replace',[('old','bytes'),('new','bytes')],'bytes'),('replace',[('old','bytes'),('new','bytes'),('count','int')],'bytes'),('split',[],'list[bytes]'),('split',[('separator','bytes')],'list[bytes]'),('join',[('values','list[bytes]')],'bytes')]:
    _add('bytes.'+name,params,result,'_bytes_value',receiver='bytes',errors=('UnicodeDecodeError',) if name=='decode' else ())
_add('bytes.fromhex',[('text','str')],'bytes','_bytes_value',errors=('ValueError',))
for name in ('find','rfind','count','startswith','endswith'):
    for params in ([('data','bytes')],[('data','bytes'),('start','int')],[('data','bytes'),('start','int'),('end','int')]):_add('bytes.'+name,params,'int','_method',receiver='bytes')
for name,params,result in [('append',[('value','int')],'void'),('extend',[('data','bytes')],'void'),('extend',[('data','bytearray')],'void'),('clear',[],'void'),('pop',[],'int'),('pop',[('index','int')],'int'),('reverse',[],'void'),('copy',[],'bytearray')]:
    _add('bytearray.'+name,params,result,'_bytearray_method',receiver='bytearray',mutable=name!='copy',errors=('ValueError','IndexError'),context='statement' if result=='void' else 'expression')

for kind in ('list[int]','list[float]','list[str]','list[bytes]','list[exception]','list[bytearray]','list[binaryfile]','list[tcpsocket]'):
    element=kind[5:-1]
    for name,params,result in [('append',[('value',element)],'void'),('extend',[('source',kind)],'void'),('clear',[],'void'),('reverse',[],'void'),('copy',[],kind),('pop',[],element),('pop',[('index','int')],element)]:
        _add(kind+'.'+name,params,result,'_method',receiver=kind,mutable=name!='copy',errors=('IndexError',) if name=='pop' else (),context='statement' if result=='void' else 'expression',constraints=('scalar list parameters are readonly; numeric/string fields use current slot and snapshot reads; reference containers share identities',))
    _add('list',[('source',kind)],kind,'_call')
    if element in ('int','float','str'):_add('sorted',[('source',kind)],kind,'_call')
for kind in ('list[int]','list[float]','list[str]'):
    element=kind[5:-1]
    for name in ('bisect_left','bisect_right','bisect'):
        for extra in ([],[('lo','int')],[('lo','int'),('hi','int')]):
            _add(name,[('values',kind),('value',element)]+extra,'int','_lower_list_operations',errors=('ValueError',),
                 constraints=('values must already be sorted ascending; lo < 0 raises ValueError','key= (one component, as in Python 3.10) also accepted; lo=/hi= keywords accepted'))
for kind in ('list[int]','list[float]','list[str]'):_add(kind+'.sort',[],'void','_method',receiver=kind,mutable=True,context='statement')
# Typed maps have separate concrete contracts; generic dict stays unclassified.
for value in ('int','float','str','bytes'):
    mapping='dict[str,'+value+']'
    for name,params,result in [
        ('get',[('key','str'),('default',value)],value),
        ('pop',[('key','str')],value),('pop',[('key','str'),('default',value)],value),
        ('setdefault',[('key','str'),('default',value)],value),
        ('keys',[],'list[str]'),('values',[],'list['+value+']'),('copy',[],mapping),
        ('clear',[],'void'),('update',[('other',mapping)],'void')]:
        _add(mapping+'.'+name,params,result,'_map_method',receiver=mapping,
             mutable=name in ('pop','setdefault','clear','update'),
             errors=('KeyError',) if name=='pop' and len(params)==1 else (),
             context='statement' if result=='void' else 'expression',
             constraints=('positional arguments only; str keys; matching value kind; float defaults may widen int',
                          'borrowed map parameters are readonly; mutate an owning local copy or a direct managed field',
                          'copy/keys/values return independent snapshots; binding and effects remain unproved'))
for kind in ('dict[str,int]','dict[str,float]','dict[str,str]','dict[str,bytes]'):
    _add('len',[('value',kind)],'int','_call')
for name,parameters,result,anchor,constraints in [
    ('jscharat',[('text','str'),('index','int')],'str','_str_value',
     ('explicit JavaScript UTF16 code-unit charAt profile; out-of-range returns empty str',
      'surrogate halves are possible; strict UTF8 encoding rejects an unpaired surrogate')),
    ('jsdiv',[('left','float'),('right','float')],'float','_call',
     ('explicit JavaScript Number division profile; zero division produces NaN or signed infinity',
      'NaN payload bits are not a declared contract')),
    ('wrapping_add',[('a','int'),('b','int')],'int','_call',('int64 addition modulo 2**64; never overflows',)),
    ('wrapping_sub',[('a','int'),('b','int')],'int','_call',('int64 subtraction modulo 2**64; never overflows',)),
    ('wrapping_mul',[('a','int'),('b','int')],'int','_call',('int64 multiplication modulo 2**64; never overflows',)),
    ('jsnegzero',[('value','float')],'int','_call',
     ('returns nonzero only for negative binary64 zero; explicit JavaScript numeric profile',))]:
    _add(name,parameters,result,anchor,constraints=constraints+('positional arguments only; no keyword arguments',))
for name in ('ValueError','ZeroDivisionError','IndexError','KeyError','EOFError','OSError','RuntimeError','UnicodeDecodeError','AssertionError','OverflowError'):
    _add(name,[],'exception','_exception_value')
    _add(name,[('message','str')],'exception','_exception_value')
for name in ('kind','message'):_add('exception.'+name,[],'str','_exception_value',receiver='exception',context='property')


# Pure library probes reject these candidate shapes; retain their symbols as unknown.
# Valid overloads of the same symbol remain available; omitted forms are never zero-arity.
_unverified={'ord':{0},'list':{0,1},'sorted':{1}}
for symbol in ('dict.get','dict.pop','set.add','set.remove','set.discard'):
    DECLARATIONS[symbol]=dict(symbol=symbol,classification='unknown',signature_known=False,overloads=[],source_anchor='_method',known_errors=[])
for symbol,indexes in _unverified.items():
    entry=DECLARATIONS[symbol]
    entry['overloads']=[value for index,value in enumerate(entry['overloads']) if index not in indexes]
    if not entry['overloads']:entry.update(classification='unknown',signature_known=False)
# Signed integer text and owning scalar float sorting profiles.
for symbol in ('hex', 'list[float].sort'):
    DECLARATIONS.pop(symbol, None)
_add('hex', [('value', 'int')], 'str', '_str_value',
         constraints=('one positional signed int64; lowercase Python 0x/-0x spelling; INT64_MIN supported',))
_add('list[float].sort', [], 'void', '_method', receiver='list[float]', mutable=True,
         errors=('ValueError',), context='statement', constraints=(
             'owning local scalar float list only; borrowed parameters remain readonly',
             'ascending finite and infinite values; NaN raises ValueError before permutation',
             'signed zeros compare equal; equal-value ordering is unspecified (standard qsort)',
             'binary64 payload values preserved'))

def _sources(source_root=None):
    root=Path(source_root).resolve() if source_root is not None else ROOT
    if root is None:
        raise ValueError('source_root must name the compiler/SDK directory')
    snapshots={name:(root/name).read_bytes() for name in ('python/pkg-v12/pyfunc.py','python/pkg-v12/cruntime.py','python/pkg-v12/SEMANTICS.md')}
    files={name:data.decode('utf8') for name,data in snapshots.items()}
    files['_snapshots']=snapshots
    nodes=ast.parse(files['python/pkg-v12/pyfunc.py'])
    inventory=set()
    for node in ast.walk(nodes):
        if isinstance(node,ast.Compare) and (isinstance(node.left,ast.Name) and node.left.id=='f' or isinstance(node.left,ast.Attribute) and isinstance(node.left.value,ast.Attribute) and node.left.value.attr=='func' and node.left.attr=='id'):
            for comparator in node.comparators:
                for value in ast.walk(comparator):
                    if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value.isidentifier() and not value.value.startswith('__'):inventory.add(value.value)
        if isinstance(node,ast.FunctionDef) and node.name in ('_binaryfile_method','_tcpsocket_method','_bytearray_method'):
            kind={'_binaryfile_method':'binaryfile','_tcpsocket_method':'tcpsocket','_bytearray_method':'bytearray'}[node.name]
            for part in ast.walk(node):
                if isinstance(part,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='arity' for target in part.targets) and isinstance(part.value,ast.Dict):
                    inventory.update(kind+'.'+key.value for key in part.value.keys if isinstance(key,ast.Constant))
    inventory.difference_update(('classes','funcs','internal_exact_bytes_fns','owned_bytes_fns','owned_str_fns'))
    inventory.update(('get_env','current_dir','list_dir','path_exists','is_dir','integer_decode','integer_encode','float64_decode','float64_encode','pcm16_scale_le'))
    return files,sorted(inventory),root


def _reference(files,anchor,root):
    text=files.get('python/pkg-v12/pyfunc.py','')
    match=re.search(r'^def '+re.escape(anchor)+r'\(',text,re.MULTILINE)
    return dict(path='python/pkg-v12/pyfunc.py',line=None if match is None else text.count('\n',0,match.start())+1,sha256=None if not text else hashlib.sha256(files['_snapshots']['python/pkg-v12/pyfunc.py']).hexdigest())


def query(symbol=None,*,source_root=None):
    if symbol is not None and (not isinstance(symbol,str) or not symbol):raise ValueError('builtin symbol must be a nonempty string')
    files,inventory,root=_sources(source_root)
    selected=[symbol] if symbol is not None else sorted(set(inventory)|set(DECLARATIONS)|set(SYNTAX_FORMS))
    entries=[]
    for name in selected:
        value=copy.deepcopy(DECLARATIONS.get(name,dict(symbol=name,classification='unknown',signature_known=False,overloads=[],source_anchor=None,known_errors=[])))
        anchor=value.pop('source_anchor')
        value['syntax_forms']=forms_for(name)
        for form in value['syntax_forms']:
            form['references']=[_reference(files,form.pop('source_anchor'),root)]
        if value['syntax_forms'] and not value['signature_known']:
            value['classification']='syntax_only'
        value.update(signature_evidence='pure library to_c probe; scalar-list mutation receiver is an owning local; typed result local' if value['signature_known'] else 'context source examples checked; no ordinary callable signature published' if value['syntax_forms'] else 'unclassified or compiler-refused candidate; no callable signature published',overloads_complete=False,errors_complete=False,effects=dict(known=False,values=[],unknown_reasons=['intrinsic declaration; caller binding/effects not proved']),fatal=dict(known=False,values=[],unknown_reasons=['allocation/limits/OS failures not closed']),
                     references=[_reference(files,anchor,root)] if anchor else [],binding_verified=False,runtime_verified=False)
        entries.append(value)
    if any((root/name).read_bytes()!=data for name,data in files['_snapshots'].items()):
        raise ValueError('compiler source changed while collecting builtin API')
    return dict(schema=SCHEMA,registry_version=VERSION,scope='builtin declarations; source APIs/C/object symbols remain separate; signatures do not prove call binding',entries=entries,
                coverage=dict(complete=False,inventory=inventory,unknown_symbols=[item['symbol'] for item in entries if not item['signature_known']],
                              syntax_only_symbols=[item['symbol'] for item in entries if item['classification']=='syntax_only'],
                              gaps=['complex iterators/range/zip/map/generator profiles','dict/set and mixed-record/context-dependent method overloads','additional text/codec overloads and unsupported domains','arbitrary user struct list types','properties and noncall operators not comprehensively inventoried']))