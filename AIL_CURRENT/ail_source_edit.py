"""Produce a checked candidate by replacing AIL function bodies."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

import ast

from ail_syntax import SyntaxErrorAIL, detect, translate


def _line_starts(text):
    return [0, *(index + 1 for index, char in enumerate(text) if char == '\n')]


def _char_offset(text, starts, line, column):
    """The character offset of an ast (line, utf8 byte column) position."""
    line_text = text[starts[line - 1]:] if line <= len(starts) else ''
    prefix = line_text.encode('utf8')[:column]
    return starts[line - 1] + len(prefix.decode('utf8', 'replace'))


def _python_body_span(text, starts, node):
    """The body text as written: from the first statement's line through the last statement.

    A one-line body starts just after the header; a multi-line body includes the indentation of its
    first line, so a replacement body is the whole indented block."""
    first = node.body[0]
    if first.lineno == node.lineno:
        start = _char_offset(text, starts, first.lineno, first.col_offset)
    else:
        start = starts[first.lineno - 1]
    last = node.body[-1]
    return start, _char_offset(text, starts, last.end_lineno, last.end_col_offset)


def _python_bodies(text):
    starts = _line_starts(text)
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ValueError(str(error)) from error
    bodies = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            bodies[node.name] = _python_body_span(text, starts, node)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    bodies[node.name + '.' + member.name] = _python_body_span(text, starts, member)
    return bodies


def _python_imports(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ValueError(str(error)) from error
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names if alias.name != 'ail')
        elif isinstance(node, ast.ImportFrom) and node.module and node.module != 'ail' and not node.level:
            imports.append(node.module)
    return imports


def _parsed_source(text):
    if not detect(text):
        return text, _python_bodies(text), _python_imports(text)
    bodies, imports = {}, []
    try:
        translated = translate(text, module=True, imports=imports, function_bodies=bodies)
    except SyntaxErrorAIL as error:
        if str(error)!='main must be in the entry source':
            raise
        bodies.clear(); imports.clear()
        translated = translate(text, imports=imports, function_bodies=bodies)
    return translated, bodies, imports


def _body_offsets(text):
    _, bodies, _ = _parsed_source(text)
    if not detect(text):
        return bodies
    starts = _line_starts(text)
    return {name: (starts[start[0]-1]+start[1], starts[end[0]-1]+end[1])
            for name, (start, end) in bodies.items()}


def replace_bodies(source, edits, expected_sha256):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256) or hashlib.sha256(source).hexdigest()!=expected_sha256.lower():
        raise ValueError('stale or invalid source SHA-256')
    if (not isinstance(edits,list) or not edits or any(not isinstance(edit,dict)
            or set(edit)!={'symbol','body'} or not isinstance(edit['symbol'],str)
            or not isinstance(edit['body'],str) for edit in edits)):
        raise ValueError('edits must be a nonempty array of symbol/body strings')
    for edit in edits:
        edit['symbol'].encode('utf8');edit['body'].encode('utf8')
    replacements={edit['symbol']:edit['body'] for edit in edits}
    if len(replacements)!=len(edits):
        raise ValueError('duplicate function target')
    text=source.decode('utf8');spans=_body_offsets(text)
    if replacements.keys()-spans.keys():
        raise ValueError('unknown function target: '+sorted(replacements.keys()-spans.keys())[0])
    pieces=[];cursor=shift=0;expected={}
    for symbol,(start,end) in sorted(spans.items(),key=lambda item:item[1][0]):
        body=replacements.get(symbol,text[start:end])
        pieces.extend((text[cursor:start],body))
        expected[symbol]=(start+shift,start+shift+len(body))
        shift+=len(body)-(end-start);cursor=end
    pieces.append(text[cursor:]);candidate=''.join(pieces)
    if _body_offsets(candidate)!=expected:
        raise ValueError('replacement escapes the selected function body')
    return candidate.encode('utf8')


def replace_body(source, symbol, body, expected_sha256):
    return replace_bodies(source,[dict(symbol=symbol,body=body.decode('utf8'))],expected_sha256)

def _unique_context(pairs):
    value=dict(pairs)
    if len(value)!=len(pairs):
        raise ValueError('duplicate JSON key')
    return value


def _verify_context(payload,source,original,args, target=None):
    from ail_source_context import context, expand_context
    if isinstance(payload,dict) and payload.get('schema')=='ail.context.compact/1':
        payload=expand_context(payload)
    if (not isinstance(payload,dict) or payload.get('schema')!='ail.context/1'
            or payload.get('status')!='available'
            or not isinstance(payload.get('interface'),dict)
            or payload['interface'].get('scope')!='source_import_closure'):
        raise ValueError('edit requires a resolved-source context')
    if args.module:
        raise ValueError('context binding requires source imports, not explicit --module')
    expected=payload.get('dependency_sha256')
    if not isinstance(expected,dict) or any(not isinstance(name,str) or not isinstance(digest,str)
            or not re.fullmatch(r'[0-9a-f]{64}',digest) for name,digest in expected.items()):
        raise ValueError('invalid context dependency hashes')
    actual=context(original,target or args.symbol,source_path=source,module_paths=args.module_path,resolve_imports=True)
    if any(payload.get(key)!=actual[key] for key in ('target','source_sha256','body_sha256','dependency_sha256')):
        raise ValueError('stale or mismatched source context')
    return expected

def run(args, check):
    report = dict(schema='ail.edit/1', status='failed', source=str(args.source),
                  target=args.symbol, link_verified=False, runtime_verified=False)
    try:
        source = Path(args.source).resolve(strict=True)
        output = Path(args.output).absolute()
        if source.suffix.lower() not in ('.ail', '.py') or output.suffix.lower() not in ('.ail', '.py'):
            raise ValueError('source and candidate output must use .ail or .py suffix')
        if output.suffix.lower()!=source.suffix.lower():
            raise ValueError('candidate output must use the source suffix')
        if output.exists() or output.is_symlink():
            raise ValueError('output must be a new candidate file')
        original = source.read_bytes()
        edits_text=getattr(args,'edits_text',None)
        if edits_text is not None:
            if args.symbol is not None:
                raise ValueError('--symbol cannot be combined with --edits-text')
            edits=json.loads(edits_text,object_pairs_hook=_unique_context)
            candidate=replace_bodies(original,edits,args.base_sha256)
            context_target=edits[0]['symbol']
            report.update(targets=[edit['symbol'] for edit in edits],context_target=context_target)
        else:
            if args.symbol is None:
                raise ValueError('--symbol is required for a single body edit')
            inline=getattr(args,'body_text',None)
            body=Path(args.body).read_bytes() if inline is None else inline.encode('utf8')
            candidate=replace_body(original,args.symbol,body,args.base_sha256)
            context_target=args.symbol
        pinned_context=None
        if getattr(args,'context',None) is not None:
            context_bytes=Path(args.context).read_bytes()
            pinned_context=json.loads(context_bytes,object_pairs_hook=_unique_context)
            if isinstance(pinned_context,dict) and pinned_context.get('schema')=='ail.check/1':
                if pinned_context.get('status')!='failed':
                    raise ValueError('edit requires a failed check report')
                pinned_context=pinned_context.get('repair_context')
                if not isinstance(pinned_context,dict):
                    raise ValueError('check report requires a repair context')
                context_source=pinned_context.get('source_path')
                if not isinstance(context_source,str) or Path(context_source)!=source:
                    raise ValueError('check repair context source path does not match edit source')
            dependencies=_verify_context(pinned_context,source,original,args,context_target)
            report.update(context_sha256=hashlib.sha256(context_bytes).hexdigest(),
                          dependency_sha256=dependencies,dependency_scope='source imports only')
        report.update(source=str(source),base_sha256=hashlib.sha256(original).hexdigest(),
                      candidate_sha256=hashlib.sha256(candidate).hexdigest())
        with tempfile.TemporaryDirectory(prefix='ail-body-edit-') as directory:
            staged = Path(directory)/source.name
            staged.write_bytes(candidate)
            options = SimpleNamespace(source=staged, syntax='auto', library=args.library,
                                      module=args.module, object=args.object,
                                      module_path=[source.parent,*args.module_path],
                                      interface=False, symbol=[], types_used=False)
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = check(options)
            checked = json.loads(stream.getvalue())
            for diagnostic in checked.get('diagnostics',[]):
                if diagnostic.get('path')==str(staged):
                    diagnostic['path']=str(output)
                    diagnostic['location_context']='candidate'
        report['candidate_check']=checked
        report['module_paths']=[str(source.parent),*(str(Path(path).resolve()) for path in args.module_path)]
        if source.read_bytes()!=original:
            raise ValueError('source changed while checking candidate')
        if pinned_context is not None:
            _verify_context(pinned_context,source,original,args,context_target)
        if status:
            return status, report
        if checked.get('status')!='passed' or checked.get('source_sha256')!=report['candidate_sha256']:
            raise ValueError('checker did not verify the proposed candidate')
        with output.open('xb') as stream:
            stream.write(candidate)
        report.update(status='passed',candidate=str(output),source_unchanged_at_check=True)
        return 0, report
    except (OSError,UnicodeError,ValueError) as error:
        report['error']=str(error)
        return 2, report
