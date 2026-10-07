import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from vflow.core.data_io import read_flow_data_file
from vflow.core.fcs_reader import read_fcs
from vflow.io import read_flow_source,probe_flow_format,UnsupportedFlowFormatError,UnvalidatedFlowFormatError
from vflow.io.derivatives import sidecar,load_or_materialize
from vflow.io.lmd_reader import decode_lmd
from vflow.ui.folder_scan_dialog import matching_folder_scan_files
from tests.format_fixtures import write_fixture,kermit

@pytest.mark.parametrize('endian',['<','>'])
def test_fcs32_true_mixture_preserves_uint64_identity(tmp_path,endian):
    p,rows=write_fixture(tmp_path/'mixed.fcs',endian=endian)
    df,meta=read_fcs(p)
    assert df.shape==(3,3) and list(df)==['Index','Fluorescence','Distance']
    assert df['Index'].dtype==np.dtype('uint64')
    assert df['Index'].tolist()==[r[0] for r in rows]
    assert df['Fluorescence'].dtype==np.dtype('float32')
    assert df['Distance'].dtype==np.dtype('float64')
    assert df['Fluorescence'].tolist()==[r[1] for r in rows]
    assert df['Distance'].tolist()==[r[2] for r in rows]

@pytest.mark.parametrize('version',['FCS1.0','FCS2.0','FCS3.0','FCS3.1','FCS3.2'])
def test_version_binary_numeric_path(tmp_path,version):
    p,rows=write_fixture(tmp_path/'simple.fcs',version=version,types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(8,9)])
    df,_=read_fcs(p);assert df.to_numpy().tolist()==rows or df.to_numpy().tolist()==[list(r) for r in rows]
    if version=='FCS1.0':assert 'pending' in df.attrs['fcs_acceptance']

def test_crc_integrity_and_independent_check_vector(tmp_path):
    assert kermit(b'123456789')==0x2189
    p,_=write_fixture(tmp_path/'crc.fcs',crc=True)
    df,_=read_fcs(p);assert df.attrs['fcs_crc_status']=='verified'
    data=bytearray(p.read_bytes());data[-9]^=1;p.write_bytes(data)
    with pytest.raises(ValueError,match='CRC'):read_fcs(p)

def test_probe_content_beats_fcs_extension_and_unknown_fails(tmp_path):
    p,_=write_fixture(tmp_path/'misnamed.csv')
    assert probe_flow_format(p).format_id=='fcs'
    assert read_flow_data_file(p).shape==(3,3)
    bad=tmp_path/'unknown.dat';bad.write_text('X,Y\n1,2\n')
    with pytest.raises(UnsupportedFlowFormatError):read_flow_data_file(bad)
    bad=tmp_path/'bad.fcs';bad.write_text('X,Y\n1,2\n')
    with pytest.raises(UnsupportedFlowFormatError):read_flow_data_file(bad)

def lmd(tmp_path):
    p,_=write_fixture(tmp_path/'base.fcs',types=('F','F'),bits=(32,32),names=('X','Y'),rows=[(1.25,2.5),(3.,4.),(5.,6.)])
    target=tmp_path/'Sample.LMD';target.write_bytes(b'Beckman fixture\x00FCS9.9 invalid'+p.read_bytes());return target

def test_lmd_derivative_reuse_delete_edit_source_lifecycle(tmp_path):
    p=lmd(tmp_path);first=read_flow_source(p).samples[0];csv=Path(first.materialized_path)
    assert csv.name=='Sample.vflow.csv' and sidecar(csv).is_file()
    assert first.dataframe.attrs['vflow_source_path']==str(p)
    pd.testing.assert_frame_equal(first.dataframe,read_flow_data_file(csv))
    second=read_flow_source(p).samples[0];assert second.dataframe.attrs['vflow_derivative_reused']
    csv.unlink();regenerated=read_flow_source(p).samples[0];assert not regenerated.dataframe.attrs['vflow_derivative_reused']
    p.write_bytes(b'offset changed'+p.read_bytes())
    changed=read_flow_source(p).samples[0];assert not changed.dataframe.attrs['vflow_derivative_reused']
    assert changed.source_member_id!=first.source_member_id

def test_collision_and_tampered_derivative_never_overwrite_user_bytes(tmp_path):
    p=lmd(tmp_path);existing=tmp_path/'Sample.vflow.csv';existing.write_text('user data')
    result=read_flow_source(p).samples[0];assert Path(result.materialized_path)!=existing
    assert existing.read_text()=='user data'
    generated=Path(result.materialized_path);generated.write_text('edited by user')
    refreshed=read_flow_source(p).samples[0]
    assert Path(refreshed.materialized_path)!=generated and generated.read_text()=='edited by user'

def test_read_only_fallback_and_no_partial_trusted_result(tmp_path,monkeypatch):
    p=lmd(tmp_path)
    import vflow.io.derivatives as mod
    original=mod._write
    def restricted(source,folder,meta,result):
        if folder==source.parent:raise PermissionError('read-only fixture')
        return original(source,folder,meta,result)
    monkeypatch.setattr(mod,'_write',restricted)
    result=load_or_materialize(p,'lmd',decode_lmd,cache_dir=tmp_path/'cache')
    assert result.warnings and '/cache/' in result.samples[0].materialized_path
    assert result.samples[0].source_path==str(p)

def test_multiple_members_and_discovery_avoids_duplicate_derivatives(tmp_path):
    one,_=write_fixture(tmp_path/'a.fcs',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(5,6)])
    two,_=write_fixture(tmp_path/'b.fcs',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(9,8),(7,6),(5,4)])
    p=tmp_path/'Plate.lmd';p.write_bytes(one.read_bytes()+two.read_bytes());one.unlink();two.unlink()
    result=read_flow_source(p);assert len(result.samples)==2
    assert [Path(s.materialized_path).name for s in result.samples]==['Plate__dataset-01.vflow.csv','Plate__dataset-02.vflow.csv']
    assert matching_folder_scan_files(str(tmp_path),'')==[str(p)]
    with pytest.raises(ValueError,match='multiple logical'):read_flow_data_file(p)

def test_equivalent_lmd_members_choose_newer_version(tmp_path):
    one,_=write_fixture(tmp_path/'old.fcs',version='FCS2.0',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(5,6)])
    two,_=write_fixture(tmp_path/'new.fcs',version='FCS3.0',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(5,6)])
    p=tmp_path/'sample.lmd';p.write_bytes(one.read_bytes()+two.read_bytes());result=read_flow_source(p)
    assert len(result.samples)==1 and result.samples[0].dataframe.attrs['fcs_version']=='FCS3.0'

def test_mqd_is_fail_closed_even_with_fcs_like_signature(tmp_path):
    p,_=write_fixture(tmp_path/'Sample.mqd')
    assert not probe_flow_format(p).validated
    with pytest.raises(UnvalidatedFlowFormatError,match='same-acquisition'):read_flow_source(p)
    assert not (tmp_path/'Sample.vflow.csv').exists()

def test_lmd_false_patterns_fail_closed(tmp_path):
    p=tmp_path/'bad.lmd';p.write_bytes(b'FCS3.1'+b'0'*80)
    with pytest.raises(UnsupportedFlowFormatError):read_flow_source(p)

@pytest.mark.parametrize('extra',[{'$P1G':'2'},{'$P1E':'4,1'}])
def test_wide_integer_scaling_cannot_silently_round(tmp_path,extra):
    p,_=write_fixture(tmp_path/'scale.fcs',extra=extra)
    with pytest.raises(ValueError,match='lose precision'):read_fcs(p)

def test_integer_time_unit_step_preserves_precision(tmp_path):
    p,values=write_fixture(tmp_path/'time.fcs',names=('Time','Fluorescence','Distance'),extra={'$P1TYPE':'Time','$TIMESTEP':'1'})
    df,_=read_fcs(p);assert df.Time.dtype==np.uint64 and df.Time.tolist()==[v[0] for v in values]
    p,_=write_fixture(p,names=('Time','Fluorescence','Distance'),extra={'$P1TYPE':'Time','$TIMESTEP':'.1'})
    with pytest.raises(ValueError,match='lose integer precision'):read_fcs(p)
