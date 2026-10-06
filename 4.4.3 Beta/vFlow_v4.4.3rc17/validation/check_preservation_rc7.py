"""Compare RC7 to RC6 and constrain behavior changes to the requested feature."""
from pathlib import Path
import ast,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'vFlow_v4.4.3rc6_UI_Restoration.zip'
CHANGES={'vflow/legacy/vflow_app.py':'threshold edit controller; empty-region guard; export guidance',
 'vflow/core/gate_serialization.py':'explicit empty-threshold marker roundtrip',
 'vflow/workspace/gates.py':'missing linked region fails with a useful error',
 'vflow/workspace/controller.py':'surface unavailable parent-population reason',
 'vflow/workspace/autogating.py':'surface fit controls and clear empty marker on refit',
 'vflow/rendering/flow_renderer.py':'show unavailable population reason',
 'vflow/ui/gate_manager.py':'delete/undo controls, precise values, flag repair and guidance',
 'vflow/ui/task_sidebar.py':'keep threshold controls in view after deletion',
 'vflow/ui/tooltips.py':'keyboard access, blank suppression and screen bounds',
 'vflow/ui/layout_helpers.py':'optional horizontal scroll support',
 'vflow/ui/folder_scan_dialog.py':'scroll long filenames and file-list controls',
 'vflow/workspace/ui.py':'disable Show sample for unavailable/multiple selections'}
METADATA={'vflow/__init__.py','vflow/statistics/audit_runner.py','vflow/io/derivatives.py','vflow/workspace/model.py'}
def sha(b):return hashlib.sha256(b).hexdigest()
def methods(source):
 tree=ast.parse(source)
 return {node.name:ast.dump(node,include_attributes=False) for item in tree.body if isinstance(item,ast.ClassDef) and item.name=='FlowApp' for node in item.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
records=[]
with zipfile.ZipFile(BASE) as z:
 prefix='vFlow_v4.4.3rc6/'
 originals={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
 for name,before in sorted(originals.items()):
  after=(ROOT/name).read_bytes()
  category='unchanged' if before==after else CHANGES.get(name) or ('release version only' if name in METADATA else 'unexpected')
  assert category!='unexpected',name
  if category=='release version only':assert after.replace(b'4.4.3rc7',b'4.4.3rc6')==before,name
  records.append({'path':name,'change':category,'rc6_sha256':sha(before),'rc7_sha256':sha(after)})
 added=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py') if p.relative_to(ROOT).as_posix() not in originals)
 assert added==['vflow/core/threshold_edits.py']
 old=methods(originals['vflow/legacy/vflow_app.py']);new=methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
 changed_methods=sorted(n for n in old if old[n]!=new.get(n));new_methods=sorted(set(new)-set(old))
 assert changed_methods==['_compute_gate_stats_for','_on_thresh_toggle','export_stats'],changed_methods
 assert new_methods==['_delete_threshold'],new_methods
 assert not set(old)-set(new)
 protected=[n for n in originals if n.startswith(('vflow/statistics/','vflow/io/','vflow/services/'))]
 assert all((ROOT/n).read_bytes().replace(b'4.4.3rc7',b'4.4.3rc6')==originals[n] for n in protected)
 core_unchanged=[n for n in originals if n.startswith('vflow/core/') and n!='vflow/core/gate_serialization.py']
 assert all((ROOT/n).read_bytes()==originals[n] for n in core_unchanged)
report={'baseline':'4.4.3rc6','candidate':'4.4.3rc7','original_modules':len(records),'unchanged_modules':sum(r['change']=='unchanged' for r in records),'version_only_modules':sum(r['change']=='release version only' for r in records),'changed_feature_and_ui_modules':sum(r['path'] in CHANGES and r['change']!='unchanged' for r in records),'added_modules':added,'unchanged_original_core_modules':len(core_unchanged),'protected_statistics_ingestion_service_modules':len(protected),'changed_existing_controller_methods':changed_methods,'new_controller_methods':new_methods,'unexpected_changes':[],'analysis_version':'audit-4','review_policy':'review-3','modules':records}
(ROOT/'validation/preservation_rc7.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
