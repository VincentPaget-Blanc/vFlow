"""Both exports derive exclusively from the same canonical audit payload."""
import csv
import io
import json
import os
import re
from pathlib import Path
import tempfile
import zipfile
from .audit_runner import clean

SHEETS=('Summary','Sample_QC','Variable_QC','Global_Distance_Matrix','Variable_Distances',
        'Variable_Matrices','Hierarchy','Variance_Components','Influence','Flags_Decisions','Provenance')
EXCEL_MAX_ROWS=1048576
EXCEL_MAX_COLUMNS=16384

def validate_export(bundle,path,reference=None,workspace=None,protected_paths=()):
    from .audit_serialization import validate_bundle
    validate_bundle(bundle)
    if reference and (reference.audit_id!=bundle['audit_id'] or reference.selected_sample_ids!=[s['sample_id'] for s in bundle['samples']]):
        raise ValueError('Export reference does not belong to this audit.')
    if workspace and reference and workspace.audits.get(reference.audit_id) is not reference:
        raise ValueError('Export review state belongs to another workspace. Reopen the current audit or export without current state.')
    protected=list(protected_paths)+[s['source'].get('absolute_path') for s in bundle['samples']]
    if reference:protected.append(reference.result.absolute_path)
    if workspace:protected.extend(ref.absolute_path for _,ref in workspace.references())
    from vflow.io.export_safety import validate_export_destination
    validate_export_destination(path,protected)

def review_context(bundle,reference=None,workspace=None):
    return {'audit_id':bundle['audit_id'],'display_name':reference.name if reference else bundle['name'],
        'decision_history':reference.decision_history if reference else [],
        'current_states':{s['sample_id']:('Excluded' if workspace.samples[s['sample_id']].excluded else 'Included')
            if workspace and s['sample_id'] in workspace.samples else 'Unknown' for s in bundle['samples']}}

def cell(value):
    if isinstance(value,(dict,list,tuple)):return json.dumps(clean(value),ensure_ascii=False,allow_nan=False,sort_keys=True)
    return clean(value)

def spreadsheet_safe_text(value):
    """CSV quoting alone does not prevent spreadsheet formula execution."""
    if isinstance(value,str) and value.lstrip(' \t\r\n').startswith(('=','+','-','@')):
        return "'"+value
    return value

def tables(bundle,reference=None,workspace=None):
    samples=[]
    for raw in bundle['sample_qc']:
        row=dict(raw);sid=row['sample_id'];s=workspace.samples.get(sid) if workspace else None
        decisions=[d for d in reference.decision_history if d['sample_id']==sid] if reference else []
        row['current_state']='Excluded' if s and s.excluded else ('Included' if s else 'Unknown')
        row['latest_audit_decision']=decisions[-1] if decisions else None
        row['top_contributors']=[r['variable'] for r in row['contributors'][:3]]
        samples.append(row)
    ids=[s['sample_id'] for s in bundle['samples']]
    # Namespacing prevents IDs such as "sample_id" or "variable" from replacing metadata.
    distance_headers=['distance:'+sid for sid in ids]
    matrix=[{'sample_id':sid,**dict(zip(distance_headers,bundle['global_distance_matrix'][i]))} for i,sid in enumerate(ids)]
    variable_matrices=[]
    for variable,m in bundle['variable_matrices'].items():
        variable_matrices.extend({'variable':variable,'sample_id':sid,**dict(zip(distance_headers,m[i]))} for i,sid in enumerate(ids))
    flags=[{'timestamp':bundle['created_at'],'sample_id':r['sample_id'],'action':'statistical_result',
        'status':r['status'],'reason_code':r['reason_codes']} for r in bundle['sample_qc']]
    if reference:flags.extend(reference.decision_history)
    summary={'audit_id':bundle['audit_id'],'name':reference.name if reference else bundle['name'],'calculation_name':bundle['name'],
        'audit_type':bundle['audit_type'],'created_at':bundle['created_at'],'population':bundle['population_label'],
        'selected_samples':len(ids),'selected_variables':len(bundle['variables']),'particles':sum(s['event_count'] for s in samples),
        'n_biological':len(set(bundle['hierarchy_mapping'].values())) if bundle['hierarchy_mapping'] else None,
        'n_nested_samples':len(bundle['hierarchy']) if bundle['hierarchy'] else None,'warnings':bundle['warnings'],
        'interpretation':bundle['interpretation'],'vflow_version':bundle['vflow_version'],'analysis_version':bundle['analysis_version']}
    provenance={k:bundle[k] for k in ('audit_schema','samples','variables','excluded_variables','scaling','policy','dependencies',
        'transformation','event_subsampling','projection_repeat_matrix','equal_bio_centers','hierarchy_mapping')}
    provenance['distance_column_sample_ids']=dict(zip(distance_headers,ids))
    provenance['display_cell_text']='Excel table text is limited to 32767 characters; full audit and review context are retained in numbered JSON chunks. XML control characters in table text are escaped.'
    return dict(zip(SHEETS,[[{'key':k,'value':v} for k,v in summary.items()],samples,bundle['variable_qc'],matrix,
        bundle['variable_distances'],variable_matrices,bundle['hierarchy'],bundle['variance_components'],bundle['influence'],flags,
        [{'key':k,'value':v} for k,v in provenance.items()]]))

def rows(records):
    headers=list(dict.fromkeys(k for r in records for k in r)) or ['status']
    return [headers]+[[cell(r.get(k)) for k in headers] for r in records]

def atomic_export(path,writer):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent);os.close(fd)
    try:
        writer(tmp)
        with open(tmp,'rb') as f:os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def export_xlsx(bundle,path,reference=None,workspace=None,protected_paths=()):
    validate_export(bundle,path,reference,workspace,protected_paths)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();wb.remove(wb.active)
    for name,records in tables(bundle,reference,workspace).items():
        content=rows(records)
        if len(content)>EXCEL_MAX_ROWS or len(content[0])>EXCEL_MAX_COLUMNS:
            raise ValueError(name+' exceeds Excel limits. Export the CSV package instead.')
        sheet=wb.create_sheet(name)
        for values in content:
            # Excel cells have a finite text limit. Full structured provenance is
            # always retained in the canonical JSON entry included below.
            sheet.append([v if not isinstance(v,str) else re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]',lambda m:'\\u'+format(ord(m[0]),'04x'),v)[:32767] for v in values])
            for c in sheet[sheet.max_row]:
                if isinstance(c.value,str):c.data_type='s'  # never execute filenames/notes as formulas
        for c in sheet[1]:c.font=Font(bold=True);c.fill=PatternFill('solid',fgColor='E3EDF0')
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for column in sheet.columns:
            letter=column[0].column_letter
            sheet.column_dimensions[letter].width=min(55,max(14,max(len(str(c.value or '')) for c in list(column)[:100])+2))
            for c in column[1:]:
                if isinstance(c.value,float):c.number_format='0.000000E+00' if c.value!=0 and abs(c.value)<1e-5 else '0.000000'
    # Canonical payload in numbered text chunks avoids Excel's per-cell limit.
    prov=wb['Provenance']
    for label,payload in [('canonical_bundle',bundle),('review_context',review_context(bundle,reference,workspace))]:
        text=json.dumps(clean(payload),allow_nan=False,ensure_ascii=True,sort_keys=True)
        for i in range(0,len(text),30000):prov.append([label+'_chunk_'+str(i//30000),text[i:i+30000]])
    if prov.max_row>EXCEL_MAX_ROWS:raise ValueError('Provenance exceeds Excel limits. Export the CSV package instead.')
    for row in prov:
        for c in row:
            if isinstance(c.value,str):c.data_type='s'
    prov.auto_filter.ref=prov.dimensions
    atomic_export(path,wb.save)

def export_csv_package(bundle,path,reference=None,workspace=None,protected_paths=()):
    validate_export(bundle,path,reference,workspace,protected_paths)
    def writer(tmp):
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            for name,records in tables(bundle,reference,workspace).items():
                stream=io.StringIO(newline='');w=csv.writer(stream)
                w.writerows([[spreadsheet_safe_text(v) for v in row] for row in rows(records)])
                z.writestr(name.lower()+'.csv',stream.getvalue())
            z.writestr('canonical_audit.json',json.dumps(clean(bundle),allow_nan=False,ensure_ascii=False,sort_keys=True))
            z.writestr('review_context.json',json.dumps(clean(review_context(bundle,reference,workspace)),allow_nan=False,ensure_ascii=False,sort_keys=True))
    atomic_export(path,writer)
