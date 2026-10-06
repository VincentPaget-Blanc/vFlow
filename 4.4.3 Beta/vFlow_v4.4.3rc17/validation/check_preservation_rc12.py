"""Constrain RC12 changes to explicit bug fixes; verify numerical and launcher preservation."""
from pathlib import Path
import ast,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'rc12_downloads/vFlow/vFlow_v4.4.3rc11_Audit_Selection_and_Edge_Cases.zip'
ALLOWED={'vflow/legacy/vflow_app.py','vflow/workspace/model.py','vflow/workspace/controller.py',
 'vflow/controllers/project_data_load_coordinator.py','vflow/statistics/audit_export.py','vflow/io/derivatives.py',
 'vflow/services/batch_stats_runner.py','vflow/ui/batch_plot_window.py','vflow/ui/polar_analysis_window.py','vflow/ui/folder_scan_dialog.py'}
ADDED={'vflow/io/export_safety.py','vflow/ui/session_guard.py'}
def sha(b):return hashlib.sha256(b).hexdigest()
def functions(data):
 tree=ast.parse(data)
 return {f'{c.name}.{f.name}':f for c in tree.body if isinstance(c,ast.ClassDef) for f in c.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
records=[]
with zipfile.ZipFile(BASE) as z:
 prefix='vFlow_v4.4.3rc11/'
 originals={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
 for name,before in sorted(originals.items()):
  after=(ROOT/name).read_bytes();version_normalized=after.replace(b'4.4.3rc12',b'4.4.3rc11')
  kind='unchanged' if before==after else 'release version only' if before==version_normalized else 'bug fix'
  assert kind!='bug fix' or name in ALLOWED,name
  records.append({'path':name,'change':kind,'rc11_sha256':sha(before),'rc12_sha256':sha(after)})
 added={p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')}-set(originals)
 assert added==ADDED,added
 # Core kernels and audit numerical kernels remain exact, except release version.
 core=[n for n in originals if n.startswith('vflow/core/')]
 audit_math=[n for n in originals if n.startswith('vflow/statistics/') and n!='vflow/statistics/audit_export.py']
 assert all((ROOT/n).read_bytes()==originals[n] for n in core)
 assert all((ROOT/n).read_bytes().replace(b'4.4.3rc12',b'4.4.3rc11')==originals[n] for n in audit_math)
 old=functions(originals['vflow/legacy/vflow_app.py']);new=functions((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
 assert not set(old)-set(new),'An original class method was removed'
 flow_changes=[name for name in old if name.startswith('FlowApp.') and ast.dump(old[name],include_attributes=False)!=ast.dump(new[name],include_attributes=False)]
 assert set(flow_changes)=={'FlowApp.load_from_folder','FlowApp.export_stats','FlowApp.batch_export_stats','FlowApp.export_gated_data','FlowApp.export_figure'},flow_changes
 for name in ('PolarAnalysisWindow._compute_and_plot','BatchPlotWindow._compute_and_plot'):
  node=new[name];offset=1 if isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str) else 0
  assert isinstance(node.body[offset],ast.ImportFrom) and node.body[offset].module=='vflow.ui.session_guard'
  assert isinstance(node.body[offset+1],ast.If)
  del node.body[offset:offset+2]
  assert ast.dump(node,include_attributes=False)==ast.dump(old[name],include_attributes=False),name
 launcher=z.read(prefix+'run_vflow.py');assert launcher==(ROOT/'run_vflow.py').read_bytes()
report={'baseline':'4.4.3rc11','candidate':'4.4.3rc12','original_modules':len(records),'new_modules':sorted(added),
 'unchanged_modules':sum(r['change']=='unchanged' for r in records),'version_only_modules':sum(r['change']=='release version only' for r in records),
 'bug_fix_modules':sum(r['change']=='bug fix' for r in records),'unchanged_core_modules':len(core),
 'unchanged_audit_numerical_modules':len(audit_math),'no_original_methods_removed':True,'flowapp_changed_methods':flow_changes,
 'secondary_numerical_bodies_unchanged_after_session_guard':True,'source_launcher_changed':False,'launcher_sha256':sha(launcher),
 'analysis_version':'audit-4','review_policy':'review-3','modules':records}
(ROOT/'validation/preservation_rc12.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
