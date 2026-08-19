#!/usr/bin/env python3
"""AST + live-host refactor wiring check for extracted UI/controller modules."""
from __future__ import annotations
import ast, json, sys
from pathlib import Path
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'source'/'vFlow_v4.3.0-dev'
sys.path.insert(0,str(SRC))
from vflow.legacy.vflow_app import FlowApp

root=tk.Tk(); root.withdraw(); app=FlowApp(root)
out={}

def refs_for(rel, owner):
    tree=ast.parse((SRC/rel).read_text())
    refs={}
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id==owner:
            refs.setdefault(node.attr,[]).append(node.lineno)
    missing=[]
    for attr, lines in sorted(refs.items()):
        try: getattr(app,attr)
        except AttributeError: missing.append({'attribute':attr,'lines':lines[:8]})
    return {'references':len(refs),'missing':missing}

ui_refs={}
for rel in ('vflow/ui/flow_app_shell.py','vflow/ui/file_list.py','vflow/ui/gate_manager.py'):
    tree=ast.parse((SRC/rel).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='self':
            ui_refs.setdefault(node.attr,[]).append((rel,node.lineno))
ui_missing=[]
for attr, where in sorted(ui_refs.items()):
    try:getattr(app,attr)
    except AttributeError:ui_missing.append({'attribute':attr,'where':where[:8]})
out['ui_shell_file_gate_manager']={'references':len(ui_refs),'missing':ui_missing}
out['gate_interaction_controller']=refs_for('vflow/controllers/gate_interaction_controller.py','host')
out['flow_renderer']=refs_for('vflow/rendering/flow_renderer.py','host')
out['status']='PASS' if all(not x['missing'] for x in out.values() if isinstance(x,dict) and 'missing' in x) else 'FAIL'
print(json.dumps(out,indent=2))
try: app.container.destroy(); root.destroy()
except Exception: pass
raise SystemExit(0 if out['status']=='PASS' else 1)
