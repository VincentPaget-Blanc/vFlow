"""Owned CSV refresh keeps original identity and recursive source checks."""
from pathlib import Path
import pandas as pd
import pytest
from tests.format_fixtures import write_fixture
from vflow.io.registry import read_flow_source
from vflow.io.derivatives import sidecar
from vflow.workspace.model import fingerprint


def test_owned_derivative_refresh_preserves_original_integrity(tmp_path, monkeypatch):
    source, _ = write_fixture(tmp_path/'sample.lmd', types=('F','F'), bits=(32,32),
                              names=('X','Y'), rows=[(1.,2.),(3.,4.)])
    first = read_flow_source(source).samples[0]
    csv = Path(first.materialized_path)
    old_csv = fingerprint(csv)
    old_member = first.source_member_id
    # Keep the embedded offset/member stable while changing the actual values.
    write_fixture(source, types=('F','F'), bits=(32,32), names=('X','Y'),
                  rows=[(9.,8.),(7.,6.)])
    refreshed = read_flow_source(csv).samples[0]
    assert refreshed.source_member_id == old_member
    assert Path(refreshed.source_path).resolve() == source.resolve()
    assert fingerprint(csv) != old_csv
    assert refreshed.dataframe.to_numpy().tolist() == [[9.,8.],[7.,6.]]
    assert refreshed.dataframe.attrs['vflow_source_identity'] == fingerprint(source)
    assert refreshed.dataframe.attrs['vflow_source_size'] == source.stat().st_size
    assert refreshed.dataframe.attrs['vflow_sample_key'] == str(csv.resolve())
    pd.testing.assert_frame_equal(refreshed.dataframe, read_flow_source(csv).samples[0].dataframe)
    # Force a real decode, then alter the authoritative source during that read.
    # The redirect must retain the recursive source integrity rejection.
    import vflow.io.lmd_reader as reader
    decode = reader.decode_lmd
    meta = sidecar(csv)
    raw = meta.read_text(); meta.write_text(raw.replace('embedded-fcs-1','obsolete-decoder'))
    def changing(path):
        result = decode(path)
        write_fixture(source, types=('F','F'), bits=(32,32), names=('X','Y'),
                      rows=[(5.,4.),(3.,2.)])
        return result
    monkeypatch.setattr(reader, 'decode_lmd', changing)
    with pytest.raises(ValueError, match='Source changed'):
        read_flow_source(csv)
