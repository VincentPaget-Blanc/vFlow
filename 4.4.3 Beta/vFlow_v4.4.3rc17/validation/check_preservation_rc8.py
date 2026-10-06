"""Compare RC8 to RC7 and constrain behavior changes to the requested feature."""
from pathlib import Path
import ast,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'vFlow_v4.4.3rc7_Threshold_Deletion_and_UX.zip'
CHANGES={'vflow/ui/flow_app_shell.py':'outer scrolling host and themed surfaces',
 'vflow/ui/task_sidebar.py':'task reveal, automatic/manual preference and scroll restoration',
 'vflow/workspace/ui.py':'delegate measured sample layout; reflow on font changes',
 'vflow/workspace/controller.py':'schedule presentation layout after sample-list updates'}
METADATA={'vflow/__init__.py','vflow/legacy/vflow_app.py','vflow/statistics/audit_runner.py','vflow/io/derivatives.py','vflow/workspace/model.py'}
def sha(b):return hashlib.sha256(b).hexdigest()
def methods(source):
 tree=ast.parse(source)
 return {node.name:ast.dump(node,include_attributes=False) for item in tree.body if isinstance(item,ast.ClassDef) and item.name=='FlowApp' for node in item.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
records=[]
with zipfile.ZipFile(BASE) as z:
 prefix='vFlow_v4.4.3rc7/'
 originals={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
 for name,before in sorted(originals.items()):
  after=(ROOT/name).read_bytes()
  category='unchanged' if before==after else CHANGES.get(name) or ('release version only' if name in METADATA else 'unexpected')
  assert category!='unexpected',name
  if category=='release version only':assert after.replace(b'4.4.3rc8',b'4.4.3rc7')==before,name
  records.append({'path':name,'change':category,'rc7_sha256':sha(before),'rc8_sha256':sha(after)})
 added=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py') if p.relative_to(ROOT).as_posix() not in originals)
 assert added==['vflow/ui/adaptive_samples.py']
 old=methods(originals['vflow/legacy/vflow_app.py']);new=methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
 changed_methods=sorted(n for n in old if old[n]!=new.get(n));new_methods=sorted(set(new)-set(old))
 assert changed_methods==[],changed_methods
 assert new_methods==[],new_methods
 assert not set(old)-set(new)
 protected=[n for n in originals if n.startswith(('vflow/statistics/','vflow/io/','vflow/services/'))]
 assert all((ROOT/n).read_bytes().replace(b'4.4.3rc8',b'4.4.3rc7')==originals[n] for n in protected)
 core_unchanged=[n for n in originals if n.startswith('vflow/core/') ]
 assert all((ROOT/n).read_bytes()==originals[n] for n in core_unchanged)
report={'baseline':'4.4.3rc7','candidate':'4.4.3rc8','original_modules':len(records),'unchanged_modules':sum(r['change']=='unchanged' for r in records),'version_only_modules':sum(r['change']=='release version only' for r in records),'changed_feature_and_ui_modules':sum(r['path'] in CHANGES and r['change']!='unchanged' for r in records),'added_modules':added,'unchanged_original_core_modules':len(core_unchanged),'protected_statistics_ingestion_service_modules':len(protected),'changed_existing_controller_methods':changed_methods,'new_controller_methods':new_methods,'unexpected_changes':[],'analysis_version':'audit-4','review_policy':'review-3','modules':records}
(ROOT/'validation/preservation_rc8.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
