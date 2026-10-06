"""Package only a gated RC16 release, with exact wheel/source/README identity."""
import argparse, hashlib, json, os, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc16'
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
def sha(data):return hashlib.sha256(data).hexdigest()
gate=json.loads((ROOT/'validation/release_gate_rc16_final.json').read_text());assert gate['all_checks_passed'] and gate['ordinary_tests']==1663
assert all(sha((ROOT/n).read_bytes())==s for n,s in gate['sources'].items())
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
    assert z.testzip() is None
    for name,digest in gate['sources'].items():assert z.read(name)==(ROOT/name).read_bytes(),name
    metadata=z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
    assert f'Version: {VERSION}\n' in metadata
    assert metadata.split('\n\n',1)[1].strip()==(ROOT/'README.md').read_text().strip()
    assert '4.4.3rc16 — workspace integrity and recovery' in metadata
receipt={k:v for k,v in gate.items() if k!='sources'}
receipt.update(wheel=wheel.name,wheel_sha256=sha(wheel.read_bytes()),wheel_matches_source=True,embedded_README_matches_source=True,
    numerical_algorithms_changed=False,source_launcher_changed=False,analysis_version='audit-4',review_policy='review-3',
    acceptance_platform='Linux / Python 3.12.14 / Tk 9.0.4 / Xvfb; actual SpyderShell',
    native_platform_limits=['Fresh Tk 8.6','Native macOS','Native Windows'],
    format_limits=['MQD same-acquisition native/export truth remains required','real FCS1.0 acquisition acceptance pending','external/vendor FCS3.2 acquisition acceptance pending'])
(ROOT/'validation/package_contents_rc16.json').write_text(json.dumps(receipt,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
raw=json.loads((ROOT/'validation/raw_preservation_rc16_final.json').read_text())['hashes']
def include(path):
    rel=path.relative_to(ROOT)
    if any(part in excluded for part in rel.parts) or path.suffix=='.pyc':return False
    if rel.parts[0]=='dist' and path!=wheel:return False
    # Benchmark bytes are the original RC15 tree. Do not package derivatives
    # created by validation as extra benchmark acquisitions.
    if rel.parts[0]=='benchmark_extensions' and rel.as_posix() not in raw:return False
    return path.name!='SOURCE_SHA256.json'
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
manifest={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in payload}
mp=ROOT/'SOURCE_SHA256.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
archive=a.archive.resolve();archive.parent.mkdir(parents=True,exist_ok=True);assert not archive.exists()
staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in payload+[mp]:z.write(path,f'vFlow_v{VERSION}/'+path.relative_to(ROOT).as_posix())
with staged.open('r+b') as f:f.flush();os.fsync(f.fileno())
staged.replace(archive)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(manifest)+1
    for n,digest in manifest.items():assert sha(z.read(f'vFlow_v{VERSION}/'+n))==digest,n
final={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes()),'manifest_files':len(manifest),
    'wheel_python_sources_verified':len(gate['sources']),'all_release_checks_passed':True}
(ROOT.parent/'RC16_PACKAGE_RECEIPT.json').write_text(json.dumps(final,indent=2)+'\n')
archive.with_suffix('.sha256').write_text(final['sha256']+'  '+archive.name+'\n')
print(json.dumps(final,indent=2))
