"""Opt-in declared ownership and conservative source-call contracts; never runtime proof."""
import ast
import copy
import hashlib
import re

SCHEMA = 'ail.api_contracts/1'
REGISTRY_VERSION = 1
PROFILE = 'AIL native ABI11; declared ownership; conservative syntactic may-effects'
EXCEPTIONS = {'ValueError', 'ZeroDivisionError', 'IndexError', 'KeyError', 'EOFError', 'OSError', 'RuntimeError', 'UnicodeDecodeError', 'AssertionError', 'OverflowError'}
OWNERSHIP = {'unknown', 'value', 'none', 'borrowed_view', 'borrowed_reference', 'owned_snapshot', 'owned_reference'}
ACCESS = {'unknown', 'readonly', 'mutable', 'none'}
# Runtime/SEM evidence records intrinsic behavior, not caller argument binding or closed error sets.
BUILTINS = {
    'print': (['output'], [], ['allocation_failure'], 'SEM31/stdio'),
    'write_stdout_bytes': (['output'], ['OSError'], [], 'SEM stdout bytes'),
    'read_bytes': (['filesystem_io', 'allocation'], ['OSError', 'ValueError'], ['allocation_failure'], 'SEM31 whole-file binary'),
    'write_bytes': (['filesystem_io'], ['OSError', 'ValueError'], [], 'SEM31 whole-file binary'),
    'write_text': (['filesystem_io', 'allocation'], ['OSError', 'ValueError'], ['allocation_failure'], 'SEM31 write_text'),
    'append_bytes': (['filesystem_io'], ['OSError', 'ValueError'], [], 'SEM31 append_bytes'),
    'open_binary': (['filesystem_io', 'allocation'], ['OSError', 'ValueError'], ['allocation_failure'], 'SEM binaryfile'),
    'tcp_connect': (['network_io', 'allocation'], ['OSError', 'ValueError'], ['allocation_failure'], 'SEM tcpsocket'),
    'tcp_listen': (['network_io', 'allocation'], ['OSError', 'ValueError'], ['allocation_failure'], 'SEM tcpsocket'),
    'int': ([], ['ValueError'], ['integer_overflow'], 'SEM int64 conversion'),
    'float': ([], ['ValueError'], [], 'SEM float conversion'),
    'len': ([], [], [], 'SEM typed length'),
    'str': (['allocation'], [], ['allocation_failure'], 'SEM Unicode str'),
    'bytes': (['allocation'], ['ValueError'], ['allocation_failure'], 'SEM bytes constructors'),
    'bytearray': (['allocation'], ['ValueError'], ['allocation_failure'], 'SEM bytearray'),
}


def _summary(values=(), unknown=()):
    return dict(known=not bool(unknown), values=sorted(set(values)), unknown_reasons=sorted(set(unknown)))


def ownership(kind, structs=(), *, result=False):
    value = dict(type=kind, ownership='unknown', access='unknown')
    if kind in ('int', 'float') or isinstance(kind, str) and kind.startswith('Callable['):
        value.update(ownership='value', access='readonly')
    elif kind in ('void', 'noret'):
        value.update(ownership='none', access='none')
    elif kind in ('str', 'bytes'):
        value.update(ownership='owned_snapshot' if result else 'borrowed_view', access='readonly')
    elif kind in ('bytearray', 'binaryfile', 'tcpsocket', 'exception') or kind in structs:
        value.update(ownership='owned_reference' if result else 'borrowed_reference', access='readonly' if kind == 'exception' else 'mutable')
    elif isinstance(kind, str):
        compact=re.sub(r'\s+','',kind)
        match=re.fullmatch(r'list\[(\w+)\]',compact)
        if match and match[1] in ('int','float','str'):
            value.update(ownership='owned_snapshot' if result else 'borrowed_view', access='mutable' if result else 'readonly')
        elif match and (match[1] in ('bytes','bytearray','binaryfile','tcpsocket','exception') or match[1] in structs):
            value.update(ownership='owned_reference' if result else 'borrowed_reference', access='mutable')
        elif compact == 'list[list[int]]' and result:
            value.update(ownership='owned_snapshot', access='mutable')
        elif re.fullmatch(r'dict\[str,(int|float|str|bytes)\]',compact):
            value.update(ownership='owned_snapshot' if result else 'borrowed_view', access='mutable' if result else 'readonly')
        elif re.fullmatch(r'list\[tuple\[(int,)*(int|bytes|float)\]\]',compact) and not result:
            value.update(ownership='borrowed_view',access='readonly')
    return value


def _records(tree):
    result={}
    for node in tree.body:
        if isinstance(node,ast.FunctionDef):result[node.name]=(node,None)
        elif isinstance(node,ast.ClassDef):
            for method in node.body:
                if not isinstance(method,ast.FunctionDef):continue
                copied=copy.deepcopy(method)
                if method.name=='__init__':
                    copied.name=node.name;copied.args.args=copied.args.args[1:];copied.returns=ast.Name(id=node.name,ctx=ast.Load())
                    result[node.name]=(copied,node.name)
                else:
                    if copied.args.args:copied.args.args[0].annotation=ast.Name(id=node.name,ctx=ast.Load())
                    result[node.name+'.'+method.name]=(copied,node.name)
    return result


def _body_sha(node):
    return hashlib.sha256(ast.dump(ast.Module(body=node.body,type_ignores=[]),include_attributes=False).encode('utf8')).hexdigest()


def build_contracts(tree, interface, *, source_sha256=None, snapshots=None, imports_resolved=False, body_available=True):
    """All selected declarations get ownership; complete source bodies only feed conservative facts."""
    records=_records(tree)
    paths={}
    unavailable=set(records) if not body_available else set()
    if snapshots:
        from ail_source_edit import _parsed_source
        for path,data in snapshots.items():
            try:parsed=ast.parse(_parsed_source(data.decode('utf8'))[0])
            except (SyntaxError,ValueError,UnicodeError):continue
            for name,record in _records(parsed).items():
                records[name]=record;paths[name]=(str(path),hashlib.sha256(data).hexdigest());unavailable.discard(name)
    structs={row['name'] for row in interface['structs']}|{node.name for node in tree.body if isinstance(node,ast.ClassDef)}
    declarations={row['name']:row for row in interface['functions']}
    for row in interface['structs']:
        declarations.setdefault(row['name'],dict(name=row['name'],parameters=row['constructor_parameters'],returns=row['name']))
        for method in row['methods']:
            item=copy.deepcopy(method);item['name']=row['name']+'.'+method['name']
            if item['parameters'] and item['parameters'][0]['name']=='self':item['parameters'][0]['type']=row['name']
            declarations[item['name']]=item
    cache={};calls={};callee_entries={}
    def inspect(name,active=()):
        if name in cache:return cache[name]
        if name in active:return [_summary(unknown=['recursive_call']) for _ in range(3)]
        if name not in records or name in unavailable:return [_summary(unknown=['body_unavailable']) for _ in range(3)]
        node,owner=records[name]
        values=[set(),set(),set()];unknown=[set(),set(),set()];call_rows=[]
        result_type=declarations.get(name,{}).get('returns')
        if result_type is None and node.returns is not None:
            result_type=ast.unparse(node.returns).removeprefix('__ail_checked_').removesuffix('__')
            if result_type=='flist':result_type='list[float]'
        result_ownership=ownership(result_type,structs,result=True)['ownership']
        if result_ownership in ('unknown','owned_snapshot','owned_reference'):
            unknown[0].add('owned_return_or_unresolved_return')
            unknown[2].add('owned_return_or_cleanup')
        shadow={arg.arg for arg in (*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs)}
        shadow.update(arg.arg for arg in (node.args.vararg,node.args.kwarg) if arg is not None)
        shadow.update(part.name for part in ast.walk(node) if part is not node and isinstance(part,(ast.FunctionDef,ast.ClassDef)))
        shadow.update(part.id for statement in tree.body if isinstance(statement,(ast.Assign,ast.AnnAssign)) for part in ast.walk(statement) if isinstance(part,ast.Name) and isinstance(part.ctx,ast.Store))
        shadow.update(part.id for part in ast.walk(node) if isinstance(part,ast.Name) and isinstance(part.ctx,(ast.Store,ast.Del)))
        shadow.update(part.name for part in ast.walk(node) if isinstance(part,ast.ExceptHandler) and part.name)
        # Binding and error closure are uncertain for nontrivial operations/control flow.
        for part in ast.walk(node):
            if isinstance(part,ast.Constant) and isinstance(part.value,(str,bytes)):
                unknown[0].add('literal_storage_or_view')
                unknown[2].add('literal_storage_or_view')
            if isinstance(part,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
                unknown[0].add('local_storage_or_cleanup')
                unknown[2].add('local_storage_or_cleanup')
            if isinstance(part,(ast.BinOp,ast.UnaryOp,ast.Subscript,ast.Attribute)):
                unknown[2].add('operator_or_bounds')
                unknown[1].add('operator_or_bounds')
                unknown[0].add('typed_operator_or_view')
                if isinstance(part,(ast.BinOp,ast.Subscript)):unknown[0].add('typed_operator_or_view')
            if isinstance(part,(ast.List,ast.Dict,ast.Set)):
                values[0].add('allocation');values[2].add('allocation_failure');unknown[2].add('allocation_or_bounds')
            if isinstance(part,(ast.Try,ast.With)):
                for group in unknown:group.add('exception_control_flow')
            if isinstance(part,(ast.Assign,ast.AugAssign,ast.Delete)):
                targets=part.targets if isinstance(part,(ast.Assign,ast.Delete)) else [part.target]
                if any(isinstance(target,(ast.Attribute,ast.Subscript)) for target in targets):
                    values[0].add('mutation');unknown[0].add('mutation_binding')
            if isinstance(part,ast.Raise):
                target=part.exc
                label=target.func.id if isinstance(target,ast.Call) and isinstance(target.func,ast.Name) else target.id if isinstance(target,ast.Name) else None
                if label in EXCEPTIONS and label not in records and label not in shadow:values[1].add(label)
                else:unknown[1].add('reraise_or_unresolved_exception')
                if part.cause is not None:unknown[1].add('exception_chaining')
            if not isinstance(part,ast.Call):continue
            label=ast.unparse(part.func)
            mapped=owner+'.'+label[5:] if owner and label.startswith('self.') else label
            if isinstance(part.func,ast.Name) and label in shadow:
                kind='unresolved';facts=[_summary(unknown=['local_alias_or_callback']) for _ in range(3)]
            elif isinstance(part.func,ast.Name) and mapped in records:
                kind='source';facts=inspect(mapped,(*active,name))
            elif isinstance(part.func,ast.Name) and label in BUILTINS:
                kind='builtin';rule=BUILTINS[label]
                facts=[_summary(rule[0],['overload_and_arguments']),_summary(rule[1],['overload_and_arguments']),_summary(rule[2],['runtime_bounds_and_allocation'])]
            elif isinstance(part.func,ast.Name) and label in EXCEPTIONS:
                kind='builtin';facts=[_summary(['allocation']),_summary(),_summary(['allocation_failure'],['runtime_bounds_and_allocation'])]
            else:
                kind='unresolved';facts=[_summary(unknown=['unclassified_call']) for _ in range(3)]
            call_rows.append(dict(name=mapped,kind=kind))
            if kind!='source':callee_entries[(kind,mapped)]=facts
            for index,fact in enumerate(facts):
                values[index].update(fact['values']);unknown[index].update(fact['unknown_reasons'])
        if owner and name==owner:
            values[0].add('allocation');values[2].add('allocation_failure');unknown[2].add('constructor_allocation')
        facts=[_summary(value,reasons) for value,reasons in zip(values,unknown)]
        calls[name]=sorted({(row['name'],row['kind']) for row in call_rows})
        cache[name]=facts
        return facts
    entries=[]
    for name,row in declarations.items():
        facts=inspect(name)
        entry=dict(name=name,kind='source',signature_known=True,parameters=[dict(name=param['name'],**ownership(param['type'],structs)) for param in row['parameters']],
                   result=ownership(row['returns'],structs,result=True),effects=facts[0],raises=facts[1],fatal=facts[2],
                   calls=[dict(name=called,kind=kind) for called,kind in calls.get(name,())],
                   provenance=dict(profile=PROFILE,registry_version=REGISTRY_VERSION,source_sha256=paths.get(name,(None,source_sha256))[1],source_path=paths.get(name,(None,None))[0],
                                   body_sha256=None if name not in records or name in unavailable else _body_sha(records[name][0]),body_hash_kind='canonical_ast',
                                   body_available=name in records and name not in unavailable,type_verified=False,binding_verified=False,runtime_verified=False,
                                   evidence=['SEM declared type/ownership','source may-effects'],imports_resolved=imports_resolved))
        entries.append(entry)
    for (kind,name),facts in sorted(callee_entries.items()):
        entries.append(dict(name=name,kind=kind,signature_known=False,parameters=[],result=ownership(None),effects=facts[0],raises=facts[1],fatal=facts[2],calls=[],
                            provenance=dict(profile=PROFILE,registry_version=REGISTRY_VERSION,source_sha256=None,source_path=None,body_sha256=None,body_hash_kind='canonical_ast',body_available=False,
                                            type_verified=False,binding_verified=False,runtime_verified=False,evidence=[BUILTINS[name][3]] if name in BUILTINS and kind=='builtin' else ['unclassified call'],imports_resolved=imports_resolved)))
    result=dict(schema=SCHEMA,registry_version=REGISTRY_VERSION,profile=PROFILE,entries=entries)
    validate_contracts(result)
    return result


def validate_contracts(payload):
    """Structural validation; metadata never authorizes execution or establishes binding proof."""
    if not isinstance(payload,dict) or set(payload)!={'schema','registry_version','profile','entries'} or payload.get('schema')!=SCHEMA or type(payload.get('registry_version')) is not int or payload.get('registry_version')!=REGISTRY_VERSION or payload.get('profile')!=PROFILE or not isinstance(payload.get('entries'),list):
        raise ValueError('invalid API contracts schema')
    for entry in payload['entries']:
        if not isinstance(entry,dict) or set(entry)!={'name','kind','signature_known','parameters','result','effects','raises','fatal','calls','provenance'} or not isinstance(entry['name'],str) or not entry['name'] or not isinstance(entry['kind'],str) or entry['kind'] not in ('source','builtin','unresolved') or type(entry['signature_known']) is not bool or entry['kind']!='source' and entry['signature_known'] or not isinstance(entry['parameters'],list) or not isinstance(entry['calls'],list):
            raise ValueError('invalid API contract entry')
        for item in [*entry['parameters'],entry['result']]:
            required={'type','ownership','access'}|({'name'} if item is not entry['result'] else set())
            if not isinstance(item,dict) or set(item)!=required or not isinstance(item['ownership'],str) or item['ownership'] not in OWNERSHIP or not isinstance(item['access'],str) or item['access'] not in ACCESS or not (item['type'] is None or isinstance(item['type'],str)):
                raise ValueError('invalid API ownership contract')
            if 'name' in item and (not isinstance(item['name'],str) or not item['name']):
                raise ValueError('invalid API ownership parameter')
        for call in entry['calls']:
            if not isinstance(call,dict) or set(call)!={'name','kind'} or not isinstance(call['name'],str) or not call['name'] or not isinstance(call['kind'],str) or call['kind'] not in ('source','builtin','unresolved'):
                raise ValueError('invalid API call contract')
        for key in ('effects','raises','fatal'):
            value=entry[key]
            if not isinstance(value,dict) or set(value)!={'known','values','unknown_reasons'} or type(value['known']) is not bool or any(not isinstance(value[group],list) or any(not isinstance(item,str) for item in value[group]) or value[group]!=sorted(set(value[group])) for group in ('values','unknown_reasons')) or value['known']!=(not bool(value['unknown_reasons'])):
                raise ValueError('invalid API effect contract')
        proof=entry['provenance']
        if not isinstance(proof,dict) or set(proof)!={'profile','registry_version','source_sha256','source_path','body_sha256','body_hash_kind','body_available','type_verified','binding_verified','runtime_verified','evidence','imports_resolved'} or proof.get('profile')!=PROFILE or type(proof.get('registry_version')) is not int or proof.get('registry_version')!=REGISTRY_VERSION or proof.get('body_hash_kind')!='canonical_ast' or type(proof.get('body_available')) is not bool or type(proof.get('imports_resolved')) is not bool or not isinstance(proof.get('evidence'),list) or any(not isinstance(item,str) for item in proof['evidence']) or not (proof.get('source_path') is None or isinstance(proof['source_path'],str)) or any(proof.get(key) is not False for key in ('type_verified','binding_verified','runtime_verified')):
            raise ValueError('invalid API contract provenance')
        if proof['body_available'] and proof['body_sha256'] is None:
            raise ValueError('available API body needs a hash')
        for key in ('source_sha256','body_sha256'):
            if proof.get(key) is not None and (not isinstance(proof[key],str) or not re.fullmatch(r'[0-9a-f]{64}',proof[key])):
                raise ValueError('invalid API contract hash')
    return payload