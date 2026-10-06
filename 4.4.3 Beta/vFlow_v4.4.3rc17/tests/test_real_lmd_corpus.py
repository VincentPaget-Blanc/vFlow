"""Full event/column checks against independently frozen FlowIO reference values."""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import pytest
from vflow.io.registry import read_flow_source

CORPUS=Path(__file__).resolve().parents[1]/'benchmark_extensions/lmd'
TRUTH=json.loads((CORPUS/'reference_values.json').read_text())['fixtures']

@pytest.mark.parametrize('truth',TRUTH,ids=[r['file'] for r in TRUTH])
def test_gallios_high_resolution_values_and_derivative_reuse(truth,tmp_path):
    source=tmp_path/truth['file'];shutil.copyfile(CORPUS/truth['file'],source)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==truth['source_sha256']
    result=read_flow_source(source)
    assert len(result.samples)==1
    sample=result.samples[0];df=sample.dataframe
    assert sample.source_member_id==f"offset-{truth['embedded_offset']}"
    assert list(df)==truth['columns'] and len(df)==truth['events']
    values=np.asarray(df,dtype='<f8')
    assert hashlib.sha256(values.tobytes()).hexdigest()==truth['canonical_float64_sha256']
    for i,c in enumerate(df):assert hashlib.sha256(values[:,i].tobytes()).hexdigest()==truth['column_sha256'][c]
    # Reused derivative retains every value, rather than accepting shape only.
    repeated=read_flow_source(source).samples[0].dataframe
    assert np.array_equal(repeated.to_numpy(),df.to_numpy())
    assert source.with_suffix('.vflow.csv').exists()
