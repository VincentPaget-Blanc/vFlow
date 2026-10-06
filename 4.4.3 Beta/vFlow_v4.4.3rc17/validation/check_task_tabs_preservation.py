"""Compare this UI-only iteration with a supplied RC4 delivery ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = {
    'vflow/ui/flow_app_shell.py', 'vflow/ui/file_list.py', 'vflow/ui/tab_manager.py',
    'vflow/workspace/ui.py', 'vflow/workspace/controller.py', 'vflow/config/styles.py',
}
METADATA = {'vflow/__init__.py', 'vflow/legacy/vflow_app.py',
            'vflow/statistics/audit_runner.py', 'vflow/workspace/model.py', 'vflow/io/derivatives.py'}

def run(archive):
    records = []
    with zipfile.ZipFile(archive) as z:
        prefix = 'vFlow_v4.4.3rc4/'
        originals = {n[len(prefix):]: z.read(n) for n in z.namelist()
                     if n.startswith(prefix+'vflow/') and n.endswith('.py')}
    for name, before in sorted(originals.items()):
        after = (ROOT/name).read_bytes()
        unchanged = before == after
        category = ('unchanged' if unchanged else 'presentation / UI persistence' if name in PRESENTATION
                    else 'release version only' if name in METADATA else 'unexpected')
        assert category != 'unexpected', name
        if category == 'release version only':
            assert after.replace(b'4.4.3rc5', b'4.4.3rc4') == before, name
        records.append({'path': name, 'category': category,
                        'rc4_sha256': hashlib.sha256(before).hexdigest(),
                        'rc5_sha256': hashlib.sha256(after).hexdigest()})
    added = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')
                   if p.relative_to(ROOT).as_posix() not in originals)
    assert added == ['vflow/ui/task_sidebar.py'], added
    report = {'baseline': '4.4.3rc4', 'candidate': '4.4.3rc5',
              'original_modules': len(records), 'unchanged_modules': sum(r['category']=='unchanged' for r in records),
              'version_only_modules': sum(r['category']=='release version only' for r in records),
              'presentation_modules': sum(r['category']=='presentation / UI persistence' for r in records),
              'added_modules': added, 'unexpected_changes': [],
              'analysis_version': 'audit-4', 'review_policy': 'review-3', 'modules': records}
    (ROOT/'validation/task_tabs_preservation_rc5.json').write_text(json.dumps(report, indent=2)+'\n')
    core = json.loads((ROOT/'validation/core_integrity_rc4.json').read_text())
    core['candidate_version'] = '4.4.3rc5'
    for item in core['modules']:
        item['release_sha256'] = hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()
        item['unchanged'] = item['release_sha256'] == item['baseline_sha256']
    assert sum(item['unchanged'] for item in core['modules']) == 8
    (ROOT/'validation/core_integrity_rc5.json').write_text(json.dumps(core, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='modules'}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rc4_zip', type=Path)
    run(parser.parse_args().rc4_zip)
