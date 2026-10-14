"""Local declared context for a function body repair, without type or runtime proof."""
import ast
import copy
import hashlib
from pathlib import Path
from ail_source_edit import _parsed_source, _body_offsets


def language_rules():
    return dict(syntax='ail_block', exceptions=dict(
        raise_examples=['raise ValueError;', 'raise ValueError();', 'raise ValueError("message");'],
        exception_data=True, chaining=False, handler_binding=True,
        value_type='exception', constructor='zero arguments or one str expression',
        fields={'kind': 'str', 'message': 'str'},
        struct_fields=True, list_type='list[exception]',
        reraise='raise; rethrows the dynamically handled exception',
        assert_supported=True, python_assertion_behavior='raises AssertionError; uncaught: stderr AssertionError: message, exit 1'))

def context(source, symbol, include_body=False, *, source_path=None, module_paths=(), resolve_imports=False, contracts=False):
    from ail_chatgpt import _source_interface, _load_sources
    text=source.decode('utf8')
    translated, spans, imports=_parsed_source(text)
    if symbol not in spans:
        raise ValueError('unknown function target: '+symbol)
    tree=ast.parse(translated)
    snapshots={}
    root=None
    if resolve_imports:
        if source_path is None:
            raise ValueError('import resolution requires the source path')
        root=Path(source_path).resolve(strict=True)
        if root.read_bytes()!=source:
            raise ValueError('source bytes do not match the source path')
        library=not any(isinstance(node,ast.FunctionDef) and node.name=='main' for node in tree.body)
        loaded=_load_sources(root,module_only=library,module_paths=module_paths,
                             declarations_only=True,source_bytes=snapshots)[0]
        if snapshots.get(root)!=source:
            raise ValueError('source changed while resolving imports')
        tree=ast.parse(loaded)
    functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    constructors=set()
    for node in tree.body:
        if isinstance(node,ast.ClassDef):
            constructor=next(member for member in node.body if isinstance(member,ast.FunctionDef) and member.name=='__init__')
            item=copy.copy(constructor);item.name=node.name;item.args=copy.deepcopy(constructor.args)
            item.args.args=item.args.args[1:];item.returns=ast.Name(id=node.name,ctx=ast.Load())
            functions[node.name]=item;constructors.add(node.name);tree.body.append(item)
            for method in node.body:
                if isinstance(method,ast.FunctionDef) and method.name!='__init__':
                    key=node.name+'.'+method.name
                    item=copy.copy(method);item.name=key;item.args=copy.deepcopy(method.args)
                    item.args.args[0].annotation=ast.Name(id=node.name,ctx=ast.Load())
                    functions[key]=item
                    tree.body.append(item)
    target=functions[symbol]
    owner=symbol.rsplit('.',1)[0] if '.' in symbol else None
    expressions={ast.unparse(node.func) for node in ast.walk(target) if isinstance(node,ast.Call)}
    mapped={name:(owner+'.'+name[5:] if owner and name.startswith('self.') else name) for name in expressions}
    candidates={name for name in mapped.values() if name in functions}
    selected=[name for name in functions if name==symbol or name in candidates]
    interface=_source_interface(tree,selected,True)
    interface['scope']='source_import_closure' if resolve_imports else 'local_source'
    if owner or constructors.intersection(selected):
        interface['types']='declared_annotations plus implicit receiver/constructor owner types'
    offsets=_body_offsets(text);start,end=offsets[symbol];body=text[start:end]
    result=dict(schema='ail.context/1',status='available',target=symbol,source_sha256=hashlib.sha256(source).hexdigest(),
                body_sha256=hashlib.sha256(body.encode('utf8')).hexdigest(),syntax_verified=True,
                type_verified=False,link_verified=False,runtime_verified=False,
                language_rules=language_rules(),
                binding_scope='source declarations; syntactic candidates; no type/binding proof' if resolve_imports else 'local declarations; syntactic call candidates; imports not resolved',
                interface=interface,imports=list(dict.fromkeys(imports)),
                other_call_expressions=sorted(name for name,qualified in mapped.items() if qualified not in functions))
    if contracts:
        from ail_api_contracts import build_contracts
        result['contracts']=build_contracts(tree,interface,source_sha256=result['source_sha256'],snapshots=snapshots,imports_resolved=resolve_imports,body_available=not resolve_imports)
    if owner:result['receiver_owner']=owner
    if include_body:result['body']=body
    if resolve_imports:
        if any(path.read_bytes()!=data for path,data in snapshots.items()):
            raise ValueError('source dependency changed while collecting context')
        result['dependency_sha256']={str(path):hashlib.sha256(data).hexdigest()
                                     for path,data in sorted(snapshots.items()) if path!=root}
    return result


_PARAMETER_COLUMNS = ['name', 'type', 'kind', 'default']
_PARAMETER_KINDS = {'positional_only', 'positional', 'keyword_only', 'variadic', 'variadic_keyword'}


def _parameter_rows(value, decode):
    if not isinstance(value, list):
        raise ValueError('invalid compact parameters')
    result = []
    for item in value:
        if decode:
            if not isinstance(item, list) or len(item) != 4:
                raise ValueError('invalid compact parameter row')
            parameter = dict(zip(_PARAMETER_COLUMNS, item))
        else:
            if not isinstance(item, dict) or set(item) != set(_PARAMETER_COLUMNS):
                raise ValueError('invalid context parameter')
            parameter = item
        if (not isinstance(parameter['name'], str)
                or not (parameter['type'] is None or isinstance(parameter['type'], str))
                or not isinstance(parameter['kind'], str) or parameter['kind'] not in _PARAMETER_KINDS
                or not (parameter['default'] is None or isinstance(parameter['default'], str))):
            raise ValueError('invalid compact parameter value')
        result.append(parameter if decode else [parameter[key] for key in _PARAMETER_COLUMNS])
    return result


def _function_rows(value, decode):
    if (not isinstance(value, dict) or set(value) != {'name', 'parameters', 'returns'}
            or not isinstance(value['name'], str)
            or not (value['returns'] is None or isinstance(value['returns'], str))):
        raise ValueError('invalid compact function')
    return dict(value, parameters=_parameter_rows(value['parameters'], decode))


def _context_transport(payload, decode):
    expected = 'ail.context.compact/1' if decode else 'ail.context/1'
    if not isinstance(payload, dict) or payload.get('schema') != expected:
        raise ValueError('invalid context transport schema')
    result = copy.deepcopy(payload)
    if 'contracts' in result:
        from ail_api_contracts import validate_contracts
        validate_contracts(result['contracts'])
    if decode:
        if result.pop('parameter_columns', None) != _PARAMETER_COLUMNS:
            raise ValueError('invalid compact parameter columns')
    elif 'parameter_columns' in result:
        raise ValueError('context parameter columns already present')
    interface = result.get('interface')
    if (not isinstance(interface, dict) or not isinstance(interface.get('functions'), list)
            or not isinstance(interface.get('structs'), list)):
        raise ValueError('invalid compact interface')
    interface['functions'] = [_function_rows(item, decode) for item in interface['functions']]
    for item in interface['structs']:
        if (not isinstance(item, dict)
                or set(item) != {'name', 'constructor_parameters', 'fields', 'methods'}
                or not isinstance(item['name'], str) or not isinstance(item['fields'], list)
                or not isinstance(item['methods'], list)):
            raise ValueError('invalid compact struct')
        for field in item['fields']:
            if (not isinstance(field, dict) or set(field) != {'name', 'type'}
                    or not isinstance(field['name'], str)
                    or not (field['type'] is None or isinstance(field['type'], str))):
                raise ValueError('invalid compact field')
        item['constructor_parameters'] = _parameter_rows(item['constructor_parameters'], decode)
        item['methods'] = [_function_rows(method, decode) for method in item['methods']]
    result['schema'] = 'ail.context/1' if decode else 'ail.context.compact/1'
    if not decode:
        result['parameter_columns'] = list(_PARAMETER_COLUMNS)
    return result


def compact_context(payload):
    """Encode parameter dictionaries as rows; preserve every other context fact."""
    return _context_transport(payload, False)


def expand_context(payload):
    """Decode compact JSON before ordinary context binding verification."""
    return _context_transport(payload, True)
