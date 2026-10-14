"""Opt-in native build diagnostics; unconfigured calls keep subprocess behavior unchanged."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

LIMIT = 512 * 1024
_report_path = None
_debug_dir = None
_report = None
_LOCATION = re.compile(r'^(.*?):(\d+)(?::(\d+))?:\s*(warning|error|fatal error|note):\s*(.*)$')


def _capture(value):
    if value is None:
        return dict(text='', bytes=0, truncated=False)
    raw=value if isinstance(value,bytes) else str(value).encode('utf8',errors='replace')
    decoded=raw[:LIMIT].decode('utf8',errors='replace')
    encoded=decoded.encode('utf8')
    text=encoded[:LIMIT].decode('utf8',errors='ignore')
    return dict(text=text,bytes=len(raw),truncated=len(raw)>LIMIT or len(encoded)>LIMIT)


def _locations(stdout, stderr):
    result=[]
    for stream in (stdout,stderr):
        for line in stream['text'].splitlines():
            match=_LOCATION.match(line)
            if match:
                path,row,column,severity,message=match.groups()
                result.append(dict(path=path,line=int(row),column=int(column) if column else None,severity=severity,message=message))
    return result


def _save():
    if _report_path is None:
        return
    # The parent gives a new private backend report path; updates replace only this configured file.
    data=json.dumps(_report,ensure_ascii=False,indent=2).encode('utf8')
    _report_path.write_bytes(data)
    if _debug_dir is not None:
        (_debug_dir/'native_report.json').write_bytes(data)


def enabled():
    return _report is not None


def configure(report_path, debug_dir=None):
    global _report_path,_debug_dir,_report
    path=Path(report_path)
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise FileNotFoundError(path.parent)
    directory=Path(debug_dir) if debug_dir is not None else None
    if directory is not None:
        directory.mkdir(parents=False,exist_ok=False)
    _report_path,_debug_dir=path,directory
    _report=dict(schema='ail.native_build/1',operations=[],generated=[])
    _save()
    return _report


def _command(command):
    return command if isinstance(command,str) else [os.fspath(part) if isinstance(part,os.PathLike) else str(part) for part in command]


def _unique(path,data):
    for index in range(1,10001):
        candidate=path if index==1 else path.with_name(path.stem+'-'+str(index)+path.suffix)
        try:
            with candidate.open('xb') as output:
                output.write(data)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError('native debug filenames exhausted')


def generated(path, functions=()):
    if _report is None:
        return None
    source=Path(path)
    data=source.read_bytes()
    text=data.decode('utf8',errors='replace')
    rows=[]
    for name,body in functions:
        matches=set()
        if isinstance(body,str) and body:
            normalized=body.replace('\r\n','\n')
            for candidate in {body,normalized,normalized.replace('\n','\r\n')}:
                start=text.find(candidate)
                while start>=0:
                    matches.add((start,start+len(candidate)))
                    start=text.find(candidate,start+1)
        if len(matches)==1:
            start,end=next(iter(matches))
            rows.append(dict(function=name,mapped=True,c_line_start=text.count('\n',0,start)+1,
                             c_line_end=text.count('\n',0,end-1)+1,c_start=start,c_end=end))
        else:
            rows.append(dict(function=name,mapped=False,c_line_start=None,c_line_end=None,c_start=None,c_end=None))
    item=dict(path=str(source.resolve()),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),functions=rows,debug_path=None)
    if _debug_dir is not None:
        item['debug_path']=str(_unique(_debug_dir/source.name,data).resolve())
    _report['generated'].append(item)
    _save()
    return item


def run(command, *, phase, **subprocess_kwargs):
    if _report is None:
        return subprocess.run(command,**subprocess_kwargs)
    record=dict(phase=phase,command=_command(command),cwd=os.fspath(subprocess_kwargs.get('cwd') or os.getcwd()),exit_code=None,
                stdout=_capture(None),stderr=_capture(None),locations=[],error=None)
    try:
        result=subprocess.run(command,**subprocess_kwargs)
    except OSError as error:
        record['error']=dict(type=type(error).__name__,message=str(error),errno=error.errno)
        _report['operations'].append(record)
        _save()
        raise
    record.update(exit_code=result.returncode,stdout=_capture(result.stdout),stderr=_capture(result.stderr))
    record['locations']=_locations(record['stdout'],record['stderr'])
    _report['operations'].append(record)
    _save()
    return result

def failure(error):
    if _report is None:
        return
    value=dict(type=type(error).__name__,message=str(error))
    for target,attribute in [('source_location','source_location' if hasattr(error,'source_location') else 'source_position'),('type_details','type_details'),('argument_details','argument_details'),('repair_hint','repair_hint'),('source_function','source_function'),('source_line','source_line'),('source_column','source_column'),('diagnostic_code','diagnostic_code')]:
        if not hasattr(error,attribute):
            continue
        item=getattr(error,attribute)
        try:
            json.dumps(item,allow_nan=False)
        except (TypeError,ValueError):
            continue
        value[target]=item
    if _report['operations'] and (_report['operations'][-1]['error'] is not None or _report['operations'][-1]['exit_code'] != 0):
        value['phase']=_report['operations'][-1]['phase']
    _report['failure']=value
    _save()
