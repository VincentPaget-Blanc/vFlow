"""Verify RC16 source boundaries against the delivered RC15 archive."""
from pathlib import Path
import ast,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
import argparse
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);BASE=p.parse_args().baseline
ALLOWED={'vflow/workspace/model.py','vflow/workspace/controller.py','vflow/ui/statistical_audit_dialog.py','vflow/io/registry.py','vflow/io/derivatives.py'}
def sha(data):return hashlib.sha256(data).hexdigest()
def methods(data):
    return {c.name+'.'+f.name:ast.dump(f,include_attributes=False) for c in ast.parse(data).body if isinstance(c,ast.ClassDef)
        for f in c.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
records=[]
with zipfile.ZipFile(BASE) as z:
    assert z.testzip() is None
    prefix='vFlow_v4.4.3rc15/';manifest=json.loads(z.read(prefix+'SOURCE_SHA256.json'))
    assert all(sha(z.read(prefix+n))==v for n,v in manifest.items())
    original={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
    for name,before in sorted(original.items()):
        after=(ROOT/name).read_bytes();normal=after.replace(b'4.4.3rc16',b'4.4.3rc15')
        kind='unchanged' if before==after else 'version only' if before==normal else 'bug fix'
        assert kind!='bug fix' or name in ALLOWED,name
        assert not set(methods(before))-set(methods(after)),name
        records.append({'path':name,'change':kind,'rc15_sha256':sha(before),'rc16_sha256':sha(after)})
    files={p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')}
    assert files-set(original)=={'vflow/workspace/file_guard.py'}
    core=[n for n in original if n.startswith('vflow/core/')];statistics=[n for n in original if n.startswith('vflow/statistics/')]
    assert all((ROOT/n).read_bytes()==original[n] for n in core)
    assert all((ROOT/n).read_bytes().replace(b'4.4.3rc16',b'4.4.3rc15')==original[n] for n in statistics)
    assert methods(original['vflow/legacy/vflow_app.py'])==methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
    controller=methods(original['vflow/workspace/controller.py']);current=methods((ROOT/'vflow/workspace/controller.py').read_bytes())
    for name in ('capture','auto_gate_data','gate_bundle','commit_gates'):assert controller['WorkspaceController.'+name]==current['WorkspaceController.'+name]
    launcher=z.read(prefix+'run_vflow.py');assert (ROOT/'run_vflow.py').read_bytes()==launcher
report={'baseline':'4.4.3rc15','candidate':'4.4.3rc16','verified_baseline_manifest_files':len(manifest),'original_modules':len(records),
    'unchanged_modules':sum(r['change']=='unchanged' for r in records),'version_only_modules':sum(r['change']=='version only' for r in records),
    'behavioral_modules':sum(r['change']=='bug fix' for r in records),'unchanged_core_modules':len(core),'protected_statistical_modules':len(statistics),
    'no_original_methods_removed':True,'all_legacy_methods_unchanged':True,'population_capture_unchanged':True,'source_launcher_changed':False,
    'analysis_version':'audit-4','review_policy':'review-3','launcher_sha256':sha(launcher),'modules':records,
    'new_module_sha256':{'vflow/workspace/file_guard.py':sha((ROOT/'vflow/workspace/file_guard.py').read_bytes())}}
(ROOT/'validation/preservation_rc16.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
