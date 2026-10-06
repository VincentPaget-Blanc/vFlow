"""RC12 adversarial boundary checks; numerical kernels are deliberately unchanged."""
import copy,csv,io,json,os,threading,time,zipfile
from pathlib import Path
import pytest
from tests.test_statistical_audit import samples
from vflow.workspace.model import Workspace,FileReference,SampleReference
from vflow.statistics import run_audit
from vflow.statistics.audit_export import export_csv_package
from vflow.io.derivatives import read_meta,sidecar

@pytest.mark.parametrize('mutation',[
 lambda d:d.update(samples=[]),lambda d:d.update(tabs=[]),lambda d:d.update(ui_state=[]),
 lambda d:d.update(axis_aliases=[]),lambda d:d.update(groups=[]),
 lambda d:d['samples']['A'].update(source=[]),lambda d:d['samples']['A'].update(active='false'),
 lambda d:d['samples']['A'].update(sample_id='different'),
 lambda d:d.update(tabs={'main':{'ui_state':[]}}),lambda d:d.update(tabs={'main':{'sample_views':[]}}),
 lambda d:d['overlay_view'].update(axis_limits=[]),lambda d:d['overlay_view'].update(cofactor=True),
 lambda d:d['overlay_view'].update(axis_limits={'x':['1','10']}),
 lambda d:d.update(workspace_id=[]),lambda d:d.update(gate_scope_state=[]),
 lambda d:d.update(workspace_id='../outside'),lambda d:d['overlay_view'].update(x_transform=[]),
])
def test_malformed_workspace_is_a_value_error(tmp_path,mutation):
 source=tmp_path/'A.csv';source.write_text('X,Y\n1,2\n')
 w=Workspace();w.samples['A']=SampleReference('A','A',FileReference.create(source))
 d=w.payload();mutation(d);p=tmp_path/'bad.vflow';p.write_text(json.dumps(d))
 with pytest.raises(ValueError):Workspace.load(p)

@pytest.mark.parametrize('value',[[],None,True,1,'text'])
def test_non_object_derivative_metadata_is_ignored(tmp_path,value):
 p=tmp_path/'data.vflow.csv';sidecar(p).write_text(json.dumps(value))
 assert read_meta(p) is None

@pytest.mark.parametrize('prefix',['=','+','-','@','\t=','\r=','  ='])
def test_csv_audit_text_never_starts_a_spreadsheet_formula(tmp_path,prefix):
 b=run_audit(samples(n=2),name=prefix+'SUM(1,2)',policy={'n_projections':2})
 p=tmp_path/'out.zip';export_csv_package(b,p)
 with zipfile.ZipFile(p) as z:
  entries=dict(csv.reader(io.StringIO(z.read('summary.csv').decode())))
  assert entries['name'].startswith("'")
  assert json.loads(z.read('canonical_audit.json'))['name']==b['name']

@pytest.mark.parametrize('alias',['symlink','hardlink'])
def test_export_guard_checks_physical_file_aliases(tmp_path,alias):
 from vflow.io.export_safety import atomic_csv
 import pandas as pd
 source=tmp_path/'source.csv';source.write_text('X\n1\n');other=tmp_path/'other.csv'
 (other.symlink_to(source) if alias=='symlink' else os.link(source,other))
 with pytest.raises(ValueError,match='replace'):atomic_csv(pd.DataFrame({'x':[2]}),other,[source])
 assert source.read_text()=='X\n1\n' and other.read_text()=='X\n1\n'

def test_failed_csv_write_preserves_existing_export_and_cleans_temp(tmp_path,monkeypatch):
 import pandas as pd
 from vflow.io.export_safety import atomic_csv
 p=tmp_path/'out.csv';p.write_bytes(b'previous export')
 def fail(self,path,**k):Path(path).write_text('partial');raise OSError('disk full')
 monkeypatch.setattr(pd.DataFrame,'to_csv',fail)
 with pytest.raises(OSError):atomic_csv(pd.DataFrame({'x':[1]}),p)
 assert p.read_bytes()==b'previous export' and list(tmp_path.iterdir())==[p]

@pytest.mark.parametrize('collision',['main','excluded_log'])
def test_batch_csv_and_log_cannot_replace_discovered_inputs(tmp_path,collision):
 from tests.test_v43_batch_stats_runner import _base_adapters,_request
 from vflow.services.batch_stats_runner import BatchStatsRunner
 source=tmp_path/('batch_excluded.csv' if collision=='excluded_log' else 'source.csv')
 source.write_text('X,Y\n1,2\n3,4\n');before=source.read_bytes()
 target=tmp_path/'batch.csv' if collision=='excluded_log' else source
 with pytest.raises(ValueError,match='replace'):
  BatchStatsRunner(_base_adapters()).run(_request(tmp_path,suffix='',save_path=str(target)))
 assert source.read_bytes()==before and not (tmp_path/'batch.csv').exists()

@pytest.mark.parametrize('mutation',[
 lambda m:m.pop('columns'),lambda m:m.pop('logical_name'),lambda m:m.update(source_member_id=[]),
 lambda m:m.update(dtypes={'X':'no-such-dtype'}),lambda m:m.update(member_ids=[{}]),
])
def test_corrupt_derivative_cache_is_regenerated_from_original(tmp_path,mutation):
 import pandas as pd,hashlib
 from tests.test_universal_ingestion import lmd
 from vflow.io import read_flow_source
 source=lmd(tmp_path);raw=hashlib.sha256(source.read_bytes()).hexdigest()
 first=read_flow_source(source).samples[0];p=Path(first.materialized_path)
 metadata=json.loads(sidecar(p).read_text());mutation(metadata);sidecar(p).write_text(json.dumps(metadata))
 second=read_flow_source(source).samples[0]
 pd.testing.assert_frame_equal(first.dataframe,second.dataframe)
 assert not second.dataframe.attrs['vflow_derivative_reused']
 assert hashlib.sha256(source.read_bytes()).hexdigest()==raw

def test_audit_export_guard_also_protects_hardlinked_sources(tmp_path):
 from vflow.statistics.audit_export import export_xlsx
 b=run_audit(samples(n=2),policy={'n_projections':2})
 p=tmp_path/'source.csv';p.write_text('source bytes');other=tmp_path/'alias.xlsx';os.link(p,other)
 with pytest.raises(ValueError,match='replace'):export_xlsx(b,other,protected_paths=[p])
 assert p.read_text()=='source bytes'
