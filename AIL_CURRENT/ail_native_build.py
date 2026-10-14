"""Opt-in CLI build reports using the existing validators and native build commands."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def enabled(args):
    return getattr(args, 'json', False) or getattr(args, 'debug_dir', None) is not None


def prepare(args, parser):
    args._native_data = None
    args._native_origins = {}
    args._native_source_map = {}
    args._native_sources = {}
    args._native_source_sha256 = None
    args._native_invoked = False
    if args.json:
        def error(message):
            emit(args, {}, 2, 'configuration', message)
            raise SystemExit(2)
        parser.error = error
    try:
        if args.source.is_file():
            args._native_source_sha256 = hashlib.sha256(args.source.read_bytes()).hexdigest()
    except OSError as error:
        if args.json:
            emit(args, {}, 2, 'loader', str(error))
            raise SystemExit(2)
        raise
    if args.debug_dir is not None:
        directory = Path(os.path.abspath(args.debug_dir))
        output = Path(os.path.abspath(args.output))
        source = args.source.resolve()
        if (directory.exists() or directory.is_symlink() or not directory.parent.is_dir()
                or directory in (source, output, Path(str(output)+'.exe'))
                or output.is_relative_to(directory)):
            parser.error('--debug-dir requires a new directory in an existing parent, distinct from source and output')
        args.debug_dir = directory


def loading(args):
    return {'origins': args._native_origins, 'source_map': args._native_source_map, 'source_bytes': args._native_sources} if enabled(args) else {}


def invoke(args, command, temporary, **kwargs):
    if not enabled(args):
        return subprocess.run(command, **kwargs)
    source = args._native_sources.get(args.source.resolve())
    if source is not None:
        args._native_source_sha256 = hashlib.sha256(source).hexdigest()
    report = Path(temporary) / 'native-build.json'
    command = [*command, '--native-report', str(report)]
    if args.debug_dir is not None:
        command += ['--native-debug-dir', str(args.debug_dir)]
    kwargs.update(capture_output=True, text=True)
    args._native_invoked = True
    try:
        result = subprocess.run(command, **kwargs)
    except subprocess.TimeoutExpired as error:
        result = subprocess.CompletedProcess(command, 124, '', str(error))
    except OSError as error:
        result = subprocess.CompletedProcess(command, 2, '', str(error))
    if report.is_file():
        try:
            data = json.loads(report.read_bytes())
            if data.get('schema') == 'ail.native_build/1':
                args._native_data = data
        except (OSError, ValueError):
            pass
    return result


def _position(args, name):
    position = args._native_origins.get(name)
    if position and len(position) == 4:
        data = args._native_sources.get(Path(position[0]))
        return dict(path=position[0], line=position[1], column=position[2], function=position[3], location_kind='function_declaration',
                    source_sha256=hashlib.sha256(data).hexdigest() if data is not None else None)
    return None


def _locations(args, native):
    result = []
    for operation in native.get('operations', []):
        for item in operation.get('locations', []):
            absolute = Path(item['path'])
            if not absolute.is_absolute():
                absolute = Path(operation['cwd']) / absolute
            records = [row for row in native.get('generated', [])
                       if os.path.normcase(str(Path(row['path']).resolve())) == os.path.normcase(str(absolute.resolve()))]
            generated = records[0] if len(records) == 1 else None
            functions = [row for row in (generated or {}).get('functions', []) if row['mapped']
                         and row['c_line_start'] <= item['line'] <= row['c_line_end']]
            function = functions[0]['function'] if len(functions) == 1 else None
            result.append(dict(item, phase=operation['phase'], function=function,
                               source_location=_position(args, function),
                               generated_sha256=(generated or {}).get('sha256'),
                               debug_path=(generated or {}).get('debug_path')))
    return result


def emit(args, output, status=0, stage=None, message=None):
    if not args.json:
        if status:
            print(message or '', file=sys.stderr, end='' if message and message.endswith('\n') else '\n')
        else:
            print(json.dumps(output, ensure_ascii=args.command != 'compile'))
        return status
    native = args._native_data or {}
    operations = native.get('operations', [])
    for generated in native.get('generated', []):
        for function in generated['functions']:
            function['source_location'] = _position(args, function['function']) if function['mapped'] else None
    if stage is None:
        failed_operation = operations[-1] if operations and (operations[-1]['exit_code'] != 0 or operations[-1]['error']) else None
        stage = 'complete' if status == 0 else failed_operation['phase'] if failed_operation else 'type' if status == 3 else 'backend'
    report = dict(schema='ail.build/1', status='passed' if status == 0 else 'failed', stage=stage,
                  command=args.command, source=str(args.source.resolve()), source_sha256=args._native_source_sha256,
                  dependency_sha256={str(path):hashlib.sha256(data).hexdigest() for path,data in args._native_sources.items()
                                     if path != args.source.resolve()},
                  exit_code=status, output=output if status == 0 else None,
                  link_verified=status == 0 and args.command == 'compile', runtime_verified=False,
                  diagnostics=_locations(args, native), native_build=native or None)
    if status:
        failure = native.get('failure', {})
        report['message'] = message or failure.get('message', 'build failed')
        if failure and not report['diagnostics']:
            location = _position(args, failure.get('source_function'))
            position = args._native_source_map.get(failure.get('source_line'))
            if position is not None:
                location = dict(path=position[0], line=position[1], column=position[2],
                                function=(location or {}).get('function', failure.get('source_function')), location_kind='source_statement')
            diagnostic = dict(code=failure.get('diagnostic_code', stage), message=failure.get('message', report['message']), source_location=location)
            for field in ('type_details', 'argument_details', 'repair_hint'):
                if field in failure:
                    diagnostic[field] = failure[field]
            report['diagnostics'].append(diagnostic)
    if args.debug_dir is not None and args._native_invoked and (args.debug_dir / 'native_report.json').is_file():
        with (args.debug_dir / 'ail_build.json').open('x', encoding='utf8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False))
    return status