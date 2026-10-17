"""Context-bound builtin source forms: pure C-generation proof, no runtime proof.

These examples do not declare generic iterator values or ordinary call overloads.
"""
from copy import deepcopy

SCHEMA = 'ail.builtin_syntax_forms/1'


def _form(context, source, inputs, bindings=(), expression_result=None, anchor='_for'):
    return dict(context=context, source=source,
                inputs=[dict(name=name, type=kind) for name, kind in inputs],
                bound_names=[dict(name=name, type=kind) for name, kind in bindings],
                expression_result_type=expression_result,
                generic_iterator_result_type=None,
                ordinary_call_signature_published=False,
                source_anchor=anchor,
                proof='translate(module=True) then to_c(library=True, strict=True); published example only',
                compile_verified=False, binding_verified=False, runtime_verified=False)


SYNTAX_FORMS = {
    'range': [_form('direct_for',
        'fn probe(n:int)->int {let total:int=0;for i in range(n) {total=total+i;}return total;}',
        [('n', 'int')], [('i', 'int')])],
    'enumerate': [_form('direct_for',
        'fn probe(xs:list[int])->int {let total:int=0;for i,v in enumerate(xs) {total=total+i+v;}return total;}',
        [('xs', 'list[int]')], [('i', 'int'), ('v', 'int')])],
    'reversed': [_form('direct_for',
        'fn probe(xs:list[int])->int {let total:int=0;for v in reversed(xs) {total=total+v;}return total;}',
        [('xs', 'list[int]')], [('v', 'int')])],
    'zip': [_form('pair_generator_reduction',
        'fn probe(xs:list[int],ys:list[int])->int {let result:int=sum(a+b for a,b in zip(xs,ys));return result;}',
        [('xs', 'list[int]'), ('ys', 'list[int]')], [('a', 'int'), ('b', 'int')], anchor='_pair_plan')],
    'map': [_form('tuple_assignment',
        'fn probe(words:list[str])->int {a,b=map(int,words);return a+b;}',
        [('words', 'list[str]')], [('a', 'int'), ('b', 'int')], anchor='_stmt')],
    'open': [_form('inline_read_expression',
        'fn probe(path:str)->str {let result:str=open(path).read();return result;}',
        [('path', 'str')], [('result', 'str')], expression_result='str', anchor='_str_value')],
    'print': [_form('bare_statement',
        'fn probe(x:int)->int {print(x);return x;}',
        [('x', 'int')], anchor='_print_stmt')],
}

SYNTAX_FORMS['range'][0]['constraints'] = ['one positional int bound in this published form; int loop target']
SYNTAX_FORMS['enumerate'][0]['constraints'] = ['one list[int] source; two name targets; zero-based counter']
SYNTAX_FORMS['reversed'][0]['constraints'] = ['one list[int] source; one name target; direct for context']
SYNTAX_FORMS['zip'][0]['constraints'] = ['two list[int] sources; stops at shorter source; pair generator consumed by sum']
SYNTAX_FORMS['map'][0]['constraints'] = ['int converter and list[str] source; two-name assignment without let; length mismatch raises ValueError']
SYNTAX_FORMS['open'][0]['constraints'] = ['one str path; inline whole-file UTF-8 read; bare open file value unsupported']
SYNTAX_FORMS['print'][0]['constraints'] = ['one int argument in this published form; bare statement; result value unsupported']


# Additional concrete contexts, without generic iterator value types.
SYNTAX_FORMS.update({
  "ord": [
    {
      "context": "proven_single_code_point_expression",
      "source": "fn probe(s:str,i:int)->int {let r:int=ord(s[i]);return r;}",
      "inputs": [
        {
          "name": "s",
          "type": "str"
        },
        {
          "name": "i",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "r",
          "type": "int"
        }
      ],
      "expression_result_type": "int",
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "str index supplies a proven single code point; general str ord remains refused"
      ],
      "source_anchor": "_call",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "dict": [
    {
      "context": "local_container_construction",
      "source": "fn probe(k:int,v:int)->int {let d=dict();d[k]=v;return d[k];}",
      "inputs": [
        {
          "name": "k",
          "type": "int"
        },
        {
          "name": "v",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "d",
          "type": None
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "zero-argument dict construction in a local; int keys and int values in this example",
        "no generic dict public parameter/result type is declared"
      ],
      "source_anchor": "_container_literal",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "set": [
    {
      "context": "local_container_construction",
      "source": "fn probe(xs:list[int])->int {let s=set(xs);return len(s);}",
      "inputs": [
        {
          "name": "xs",
          "type": "list[int]"
        }
      ],
      "bound_names": [
        {
          "name": "s",
          "type": None
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "one integer-list source consumed into a local set; no generic set parameter/result type is declared"
      ],
      "source_anchor": "_container_literal",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "set.add": [
    {
      "context": "local_container_statement",
      "source": "fn probe(v:int)->int {let s=set();s.add(v);return len(s);}",
      "inputs": [
        {
          "name": "v",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "s",
          "type": None
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "owning local integer set constructed with set(); one int argument",
        "only statement use is published; method result type is not declared"
      ],
      "source_anchor": "_method",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "set.discard": [
    {
      "context": "local_container_statement",
      "source": "fn probe(v:int)->int {let s=set();s.discard(v);return len(s);}",
      "inputs": [
        {
          "name": "v",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "s",
          "type": None
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "owning local integer set constructed with set(); one int argument",
        "only statement use is published; method result type is not declared"
      ],
      "source_anchor": "_method",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "set.remove": [
    {
      "context": "local_container_statement",
      "source": "fn probe(v:int)->int {let s=set();s.add(v);s.remove(v);return len(s);}",
      "inputs": [
        {
          "name": "v",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "s",
          "type": None
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "constraints": [
        "owning local integer set constructed with set(); one int argument",
        "only statement use is published; method result type is not declared"
      ],
      "source_anchor": "_method",
      "proof": "translate(module=True) then to_c(library=True, strict=True); example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False
    }
  ],
  "dict[str,int].items": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,int])->int {let result:int=0;for key,value in m.items() {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,int]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        },
        {
          "name": "value",
          "type": "int"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 83",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "zero-argument items(); exactly two name targets; direct for only; no stored items view",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,int]": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,int])->int {let result:int=0;for key in m {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,int]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 83",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "exactly one key name target; direct map for context",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,int].keys": [
    {
      "context": "owned_key_snapshot_for",
      "source": "fn probe(m:dict[str,int])->int {let d:dict[str,int]=m.copy();let result:int=0;for key in list(d.keys()) {d.clear();result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,int]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 83",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "keys() supplies an independent owned list[str] snapshot",
        "the source is an owning local copy; clearing it during snapshot iteration is permitted",
        "borrowed input map is unchanged; no generic iterator value is declared",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,float].items": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,float])->int {let result:int=0;for key,value in m.items() {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,float]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        },
        {
          "name": "value",
          "type": "float"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 94 (Owned string-key binary64 maps, R524)",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "zero-argument items(); exactly two name targets; direct for only; no stored items view",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,float]": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,float])->int {let result:int=0;for key in m {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,float]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 94 (Owned string-key binary64 maps, R524)",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "exactly one key name target; direct map for context",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,float].keys": [
    {
      "context": "owned_key_snapshot_for",
      "source": "fn probe(m:dict[str,float])->int {let d:dict[str,float]=m.copy();let result:int=0;for key in list(d.keys()) {d.clear();result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,float]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 94 (Owned string-key binary64 maps, R524)",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "keys() supplies an independent owned list[str] snapshot",
        "the source is an owning local copy; clearing it during snapshot iteration is permitted",
        "borrowed input map is unchanged; no generic iterator value is declared",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,str].items": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,str])->int {let result:int=0;for key,value in m.items() {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,str]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        },
        {
          "name": "value",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 84",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "zero-argument items(); exactly two name targets; direct for only; no stored items view",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,str]": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,str])->int {let result:int=0;for key in m {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,str]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 84",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "exactly one key name target; direct map for context",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,str].keys": [
    {
      "context": "owned_key_snapshot_for",
      "source": "fn probe(m:dict[str,str])->int {let d:dict[str,str]=m.copy();let result:int=0;for key in list(d.keys()) {d.clear();result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,str]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 84",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "keys() supplies an independent owned list[str] snapshot",
        "the source is an owning local copy; clearing it during snapshot iteration is permitted",
        "borrowed input map is unchanged; no generic iterator value is declared",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,bytes].items": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,bytes])->int {let result:int=0;for key,value in m.items() {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,bytes]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        },
        {
          "name": "value",
          "type": "bytes"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 87",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "zero-argument items(); exactly two name targets; direct for only; no stored items view",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,bytes]": [
    {
      "context": "direct_for",
      "source": "fn probe(m:dict[str,bytes])->int {let result:int=0;for key in m {result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,bytes]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 87",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "exactly one key name target; direct map for context",
        "borrowed map input is readonly; this example performs no structural mutation",
        "direct map/items loops snapshot owned keys and check source epoch before every advance, including exhaustion/continue",
        "current values are read per entry; present-value overwrite is permitted",
        "new key, deletion, nonempty clear or rebinding raises RuntimeError on next advance, including same-size changes",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "dict[str,bytes].keys": [
    {
      "context": "owned_key_snapshot_for",
      "source": "fn probe(m:dict[str,bytes])->int {let d:dict[str,bytes]=m.copy();let result:int=0;for key in list(d.keys()) {d.clear();result=result+len(key);}return result;}",
      "inputs": [
        {
          "name": "m",
          "type": "dict[str,bytes]"
        }
      ],
      "bound_names": [
        {
          "name": "key",
          "type": "str"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_str",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 87",
        "python/pkg-v12/SEMANTICS.md section 83 (shared epoch/snapshot profile)"
      ],
      "constraints": [
        "keys() supplies an independent owned list[str] snapshot",
        "the source is an owning local copy; clearing it during snapshot iteration is permitted",
        "borrowed input map is unchanged; no generic iterator value is declared",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ],
  "file_chunks": [
    {
      "context": "direct_for",
      "source": "fn probe(path:str,size:int)->int {let total:int=0;for chunk in file_chunks(path,size) {total=total+len(chunk);}return total;}",
      "inputs": [
        {
          "name": "path",
          "type": "str"
        },
        {
          "name": "size",
          "type": "int"
        }
      ],
      "bound_names": [
        {
          "name": "chunk",
          "type": "bytes"
        }
      ],
      "expression_result_type": None,
      "generic_iterator_result_type": None,
      "ordinary_call_signature_published": False,
      "source_anchor": "_for_file_chunks",
      "proof": "translate(module=True) then to_c(library=True, strict=True); published example only",
      "compile_verified": False,
      "binding_verified": False,
      "runtime_verified": False,
      "specification_references": [
        "python/pkg-v12/SEMANTICS.md section 90"
      ],
      "constraints": [
        "exactly two positional arguments evaluated left to right once; str path and int size; one name target; no for-else",
        "nonpositive size raises ValueError before opening; positive reads cap at min(size,65536)",
        "owned binary bytes; no UTF-8/newline/Ctrl-Z conversion; EOF performs no iteration",
        "direct for only; not a first-class file/iterator, enumerate source or with-open API",
        "EOF/break/return/escaping exceptions release reader/buffer; retained chunks survive later reads and close",
        "read cap is not an RSS bound; allocation and universal OS failure behavior is not closed",
        "pure compilation proof only; runtime behavior remains unverified"
      ]
    }
  ]
})
for name in ('get','pop'):
    call='d.get(k,0)' if name=='get' else 'd.pop(k)'
    form=_form('local_container_expression',
               'fn probe(k:int,v:int)->int {let d=dict();d[k]=v;return '+call+';}',
               [('k','int'),('v','int')],[('d',None)],expression_result='int',anchor='_method')
    form['constraints']=['legacy owning local dict with int keys/int values; no generic dict parameter/result type',
                         'only the published source example is checked; other profiles and errors remain open']
    SYNTAX_FORMS['dict.'+name]=[form]

# heapq / bisect mutators (2026-10-14): lowered in place on an owning local or a struct field; a
# list parameter is read-only, so no ordinary call signature with a list parameter is published.
for name, body, result in [
        ('heappush', 'let h:list[int]=[];heappush(h,x);heappush(h,x+1);return h[0];', 'int'),
        ('heappop', 'let h:list[int]=[x,1];heapify(h);let r:int=heappop(h);return r;', 'int'),
        ('heapify', 'let h:list[int]=[x,3,1];heapify(h);return h[0];', 'int'),
        ('heappushpop', 'let h:list[int]=[1];let r:int=heappushpop(h,x);return r;', 'int'),
        ('heapreplace', 'let h:list[int]=[1];let r:int=heapreplace(h,x);return r;', 'int'),
        ('insort', 'let xs:list[int]=[1,5];insort(xs,x);return xs[1];', 'int')]:
    form = _form('local_list_mutation', 'fn probe(x:int)->int {' + body + '}', [('x', 'int')],
                 expression_result=result, anchor='_lower_list_operations')
    form['constraints'] = ['the changed list is an owning local or a struct field, never a list parameter',
                           'list[int], list[float], list[str]; a struct list with key= as in sort',
                           'heappop/heapreplace on an empty heap raise IndexError',
                           'CPython heapq/bisect algorithms; heap layout equals CPython']
    SYNTAX_FORMS[name] = [form]


def forms_for(symbol):
    """Return independent examples; unknown symbols have no published forms."""
    return deepcopy(SYNTAX_FORMS.get(symbol, []))
