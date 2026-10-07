"""Check this presentation revision against the delivered RC5 source."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'vFlow_v4.4.3rc5_Task_Tabs_and_Control_Preservation.zip'
PRESENTATION={'vflow/ui/flow_app_shell.py','vflow/ui/task_sidebar.py','vflow/ui/gate_manager.py','vflow/ui/axis_name_resolver.py','vflow/ui/batch_stats_dialog.py','vflow/ui/folder_scan_dialog.py','vflow/ui/statistical_audit_dialog.py','vflow/ui/polar_analysis_window.py','vflow/ui/batch_plot_window.py','vflow/workspace/ui.py','vflow/workspace/controller.py','vflow/config/styles.py'}
METADATA={'vflow/__init__.py','vflow/legacy/vflow_app.py','vflow/statistics/audit_runner.py','vflow/workspace/model.py','vflow/io/derivatives.py'}
def sha(data):return hashlib.sha256(data).hexdigest()
records=[]
with zipfile.ZipFile(BASE) as z:
 prefix='vFlow_v4.4.3rc5/'
 originals={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
 for name,before in sorted(originals.items()):
  after=(ROOT/name).read_bytes();category='unchanged' if before==after else 'presentation / UI persistence' if name in PRESENTATION else 'release version only' if name in METADATA else 'unexpected'
  assert category!='unexpected',name
  if category=='release version only':assert after.replace(b'4.4.3rc6',b'4.4.3rc5')==before,name
  records.append({'path':name,'category':category,'rc5_sha256':sha(before),'rc6_sha256':sha(after)})
 added=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py') if p.relative_to(ROOT).as_posix() not in originals)
 assert added==['vflow/ui/layout_helpers.py'],added
 protected=[r for r in records if r['path'].startswith(('vflow/core/','vflow/statistics/','vflow/services/','vflow/io/'))]
 assert all(r['category'] in ('unchanged','release version only') for r in protected)
report={'baseline':'4.4.3rc5','candidate':'4.4.3rc6','original_modules':len(records),'unchanged_modules':sum(r['category']=='unchanged' for r in records),'presentation_modules':sum(r['category']=='presentation / UI persistence' for r in records),'version_only_modules':sum(r['category']=='release version only' for r in records),'added_modules':added,'protected_scientific_and_ingestion_modules':len(protected),'unexpected_changes':[],'analysis_version':'audit-4','review_policy':'review-3','modules':records}
(ROOT/'validation/ui_preservation_rc6.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
