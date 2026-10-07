"""Population snapshots and review actions through the existing workspace owner."""
import copy
from dataclasses import asdict
from vflow.workspace.gates import resolve_lineage_for_sample,filter_lineage,plain
from .models import AuditSample
from .audit_serialization import commit_bundle,append_decision

def capture_population_inputs(owner,app,sample_ids,gate_id=None,region='IN'):
    owner.capture(app)
    membership=owner.document.tabs.get(app._workspace_tab_id,{}).get('sample_ids') if app is not owner.main else None
    if membership is not None and any(sid not in membership for sid in sample_ids):
        raise ValueError('Selected sample does not belong to this population. Reopen the audit for its current sample membership.')
    result=[]
    for sid in sample_ids:
        sample=owner.document.samples[sid];path=owner.path_for(sid)
        df=owner.main.loaded_files.get(path,owner.main.excluded_files.get(path))
        if df is None:raise ValueError(sample.display_name+': source/population unavailable.')
        lineage=resolve_lineage_for_sample(sid,app.population_lineage,owner.stores)
        if owner.document.tabs.get(app._workspace_tab_id,{}).get('lineage') and not lineage:
            raise ValueError('Required parent population lineage is unavailable.')
        if gate_id is not None:
            gate=owner.stores[app._workspace_tab_id].resolve_gate(sid,gate_id)
            if gate is None:raise ValueError(sample.display_name+': selected gate is unavailable.')
            context=gate.get('_analysis_context')
            if not context:raise ValueError('Selected gate has no recorded measurement context.')
            lineage.append({'gate':gate,'context':context,'region':region})
        snapshot={'tab_id':app._workspace_tab_id,'lineage':[{**copy.deepcopy(stage),'gate':plain(stage['gate'])} for stage in lineage],
                  'source_member_id':sample.source_member_id,
                  'resolved_tab_gates':[plain(gate) for gate in owner.stores[app._workspace_tab_id].resolve_gate_set(sid)]}
        result.append((sid,sample.display_name,df,lineage,asdict(sample.source),snapshot))
    return result

def materialize_population_inputs(inputs,cancel=None,progress=None):
    from .models import checkpoint
    result=[]
    for sid,name,df,lineage,source,snapshot in inputs:
        checkpoint(cancel,progress,'Preparing populations: '+name)
        filtered=filter_lineage(df,lineage)
        result.append(AuditSample(sid,name,filtered.copy(deep=True),source,snapshot))
    return result

def prepare_samples(owner,app,sample_ids,gate_id=None,region='IN'):
    return materialize_population_inputs(capture_population_inputs(owner,app,sample_ids,gate_id,region))

def commit(owner,bundle):
    # Do not commit results whose acquisition identity changed while running.
    for item in bundle['samples']:
        sample=owner.document.samples.get(item['sample_id'])
        if (sample is None or sample.source.identity_fingerprint!=item['source'].get('identity_fingerprint')
            or not sample.source.resolve(owner.path)
            or ('source_member_id' in item['population_snapshot'] and sample.source_member_id!=item['population_snapshot']['source_member_id'])):
            raise ValueError('Source identity changed during calculation; result was not registered.')
    ref=commit_bundle(owner.document,bundle,owner.path,owner.state_dir)
    owner.mark_dirty()
    return ref

def validate_decision(owner,reference,sample_id,action):
    if owner.document.audits.get(reference.audit_id) is not reference:
        raise ValueError('This audit belongs to a previously opened workspace. Reopen it from the current workspace before reviewing.')
    if sample_id not in reference.selected_sample_ids:raise ValueError('Select an audited sample.')
    if action not in ('keep','exclude','restore','note'):raise ValueError('Unknown decision.')
    sample=owner.document.samples.get(sample_id)
    if action in ('exclude','restore'):
        if sample is None:raise ValueError('Sample no longer belongs to this workspace.')
        path=owner.path_for(sample_id)
        if action=='exclude':
            if path not in owner.main.loaded_files and path not in owner.main.excluded_files:raise ValueError('Sample is not loaded.')
        else:
            if path not in owner.main.loaded_files and owner.main.excluded_files.get(path) is None:raise ValueError('Source is unavailable; relink it before restoring.')
    return sample

def decide_many(owner,reference,sample_ids,action,reason='no_reason_supplied',note=''):
    ids=list(sample_ids)
    if not ids or len(set(ids))!=len(ids):raise ValueError('Select unique audited samples.')
    if not isinstance(reason,str) or not isinstance(note,str):raise ValueError('Review reason and note must be text.')
    for sid in ids:validate_decision(owner,reference,sid,action)
    main=owner.main;history_length=len(reference.decision_history)
    if action not in ('exclude','restore'):
        for sid in ids:append_decision(reference,sid,action,reason,note)
        owner.mark_dirty();return
    # DataFrames remain shared immutable inputs. Only state and metadata are
    # snapshotted, so rollback does not duplicate full event tables.
    state={k:dict(getattr(main,k)) for k in ('loaded_files','excluded_files','file_vars','file_colors')}
    document_state={k:copy.deepcopy(getattr(owner.document,k)) for k in ('samples','tabs','ui_state','overlay_view','axis_aliases')}
    stores=copy.deepcopy(owner.stores);view=owner.capture_view(main)
    dirty,gates_dirty,last_state=owner.dirty,owner.gates_dirty,owner._last_state
    try:
        for sid in ids:
            path=owner.path_for(sid)
            (main._exclude_file if action=='exclude' else main._restore_file)(path)
            expected=main.excluded_files if action=='exclude' else main.loaded_files
            if path not in expected:raise ValueError('The requested inclusion change did not complete.')
        owner.sync_sources();owner.update_tree(main)
        for sid in ids:append_decision(reference,sid,action,reason,note)
        owner.mark_dirty()
    except Exception as exc:
        for key,values in state.items():
            current=getattr(main,key);current.clear();current.update(values)
        for key,value in document_state.items():setattr(owner.document,key,value)
        owner.stores=stores;del reference.decision_history[history_length:]
        restoring=owner.restoring;owner.restoring=True
        refresh_error=None
        try:
            main._invalidate_analysis_caches(data_changed=True)
            for widget in main.file_list_frame.winfo_children():widget.destroy()
            for path in main.loaded_files:main._add_file_row(path)
            main._rebuild_excluded_list();owner.before_render(main);owner.apply_view(main,view)
            main._recompute_all_gate_stats();main.refresh_plot();owner.update_tree(main)
        except Exception as refresh_exc:refresh_error=refresh_exc
        finally:
            owner.restoring=restoring;owner.dirty=dirty;owner.gates_dirty=gates_dirty;owner._last_state=last_state;owner.title()
        message='Review failed; inclusion and audit history were restored: '+str(exc)
        if refresh_error is not None:message+=' (Display refresh also failed; reopen the workspace to refresh the view: '+str(refresh_error)+')'
        raise ValueError(message) from exc

def decide(owner,reference,sample_id,action,reason='no_reason_supplied',note=''):
    return decide_many(owner,reference,[sample_id],action,reason,note)
