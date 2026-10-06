"""Boundary edits preserve other flags and have independently known partitions."""
import copy
import numpy as np
import pytest
from vflow.core.threshold_edits import threshold_delete_plan
from vflow.core.gate_masks import compute_gate_regions


def fixture():
    return {'id':1,'type':'crosshair','applied':True,'x_boundaries':[40.,100.,200.],
            'x_thresh_vars':[True,False,True],'y_boundaries':[40.,100.],
            'y_thresh_vars':[False,True],'y_boundary':999.,'y_thresh_var':True}

def counts(g):
    regions,_=compute_gate_regions(g,np.array([30.,50.,90.,120.,220.]),np.array([30.,50.,90.,120.,70.]),
        x_scale='linear',y_scale='linear',cofactor=150,x_channel='X',y_channel='Y')
    return {name:int(mask.sum()) for name,mask in regions.items()}


def test_delete_enabled_x_merges_regions_and_preserves_inactive_flags():
    g=fixture();before=copy.deepcopy(g);plan=threshold_delete_plan(g,'x',0)
    assert g==before
    g.update(plan)
    assert g['x_boundaries']==[100.,200.] and g['x_thresh_vars']==[False,True]
    assert sorted(counts(g).values())==[0,1,1,3]


def test_delete_disabled_boundary_does_not_change_current_partitions():
    g=fixture();before=counts(g);g.update(threshold_delete_plan(g,'x',1))
    assert counts(g)==before


def test_last_multi_y_delete_never_resurrects_legacy_single_y():
    g=fixture();g.update(threshold_delete_plan(g,'y',1))
    assert g['y_boundaries']==[40.] and g['y_thresh_vars']==[False]
    assert sorted(counts(g).values())==[1,1,3]
    g.update(threshold_delete_plan(g,'y',0))
    assert g['y_boundaries'] is None and g['y_boundary'] is None
    assert g['y_thresh_var'] is False and g['y_thresh_vars']==[]
    assert sorted(counts(g).values())==[1,1,3]


def test_single_y_delete_preserves_x_and_removes_y_partition():
    g=fixture();g.update(y_boundaries=None,y_thresh_vars=[],y_boundary=100.)
    x=copy.deepcopy((g['x_boundaries'],g['x_thresh_vars']))
    g.update(threshold_delete_plan(g,'y',0))
    assert (g['x_boundaries'],g['x_thresh_vars'])==x and g['y_boundary'] is None
    assert sorted(counts(g).values())==[1,1,3]


def test_deleting_all_boundaries_leaves_explicit_empty_gate():
    g=fixture()
    while g['x_boundaries']:g.update(threshold_delete_plan(g,'x',0))
    while g['y_boundaries']:g.update(threshold_delete_plan(g,'y',0))
    assert counts(g)=={} and g['type']=='crosshair'

@pytest.mark.parametrize('axis,index',[('z',0),('X',0),('x',-1),('x',99),('x',True),('y',.0),('y',None)])
def test_invalid_or_stale_rows_have_no_edit(axis,index):
    g=fixture();before=copy.deepcopy(g)
    assert threshold_delete_plan(g,axis,index) is None and g==before

@pytest.mark.parametrize('axis',['x','y'])
def test_missing_and_excess_flags_are_normalized_without_reenabling_remaining(axis):
    g=fixture();g[axis+'_thresh_vars']=[False]
    g.update(threshold_delete_plan(g,axis,1))
    assert g[axis+'_thresh_vars'][0] is False
    assert len(g[axis+'_thresh_vars'])==len(g[axis+'_boundaries'])


def test_explicit_empty_state_roundtrips_without_accepting_unmarked_malformed_geometry():
    from vflow.core.gate_serialization import gate_to_json_dict,gate_from_json_dict,validate_raw_gate
    g=fixture()
    while g['x_boundaries']:g.update(threshold_delete_plan(g,'x',0))
    while g['y_boundaries']:g.update(threshold_delete_plan(g,'y',0))
    raw=gate_to_json_dict(g);assert raw['thresholds_empty'] is True
    clean,_=gate_from_json_dict(raw,2);assert clean['thresholds_empty'] is True and clean['applied'] is True
    assert validate_raw_gate(raw)
    for marker in [None,False,'true',1]:
        raw['thresholds_empty']=marker;assert not validate_raw_gate(raw)
