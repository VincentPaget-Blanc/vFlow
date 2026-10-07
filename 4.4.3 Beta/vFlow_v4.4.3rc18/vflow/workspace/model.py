"""Versioned, typed workspace state. Raw data and gate definitions stay external."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import uuid
import re
from numbers import Real
from vflow.core.transforms import VALID_SCALES
from vflow.core.logicle import LogicleParameters
from vflow.workspace.file_guard import byte_revision, file_revision, check_revision, workspace_lock

SCHEMA = 2


def fingerprint(path, algorithm='sha256'):
    """Full content identity for new references; old sampled identities remain readable."""
    p = Path(path)
    if algorithm == 'sha256':
        revision=file_revision(p)
        if revision is None:raise FileNotFoundError(p)
        return 'sha256:' + revision
    if algorithm != 'sampled-sha256':raise ValueError('Unknown fingerprint algorithm.')
    size = p.stat().st_size
    digest = hashlib.sha256(str(size).encode('ascii'))
    with p.open('rb') as f:
        for offset in sorted(set((0, max(0, size // 2 - 32768), max(0, size - 65536)))):
            f.seek(offset)
            digest.update(f.read(65536))
    return 'sampled-sha256:' + digest.hexdigest()


def matches_fingerprint(path, recorded):
    if not isinstance(recorded,str):return False
    algorithm=recorded.partition(':')[0]
    if algorithm not in ('sha256','sampled-sha256'):return False
    return fingerprint(path,algorithm)==recorded


def atomic_json(path, payload, before_replace=None):
    """Validate before writing; fsync file, replace, and fsync directory when available."""
    data = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    json.loads(data)
    p = Path(path).absolute()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + p.name + '.', suffix='.tmp', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if before_replace:before_replace()
        os.replace(tmp, p)
        if hasattr(os, 'O_DIRECTORY'):
            dir_fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


@dataclass
class FileReference:
    absolute_path: str = ''
    relative_path: str | None = None
    filename: str = ''
    size: int | None = None
    identity_fingerprint: str | None = None
    kind: str = 'source'
    content_sha256: str | None = None

    def validate(self):
        if any(not isinstance(v,str) for v in (self.absolute_path,self.filename,self.kind)) or (self.relative_path is not None and not isinstance(self.relative_path,str)):
            raise ValueError('Invalid recorded file path.')
        if self.size is not None and (type(self.size) is not int or self.size<0):raise ValueError('Invalid recorded file size.')
        if self.identity_fingerprint is not None and not isinstance(self.identity_fingerprint,str):raise ValueError('Invalid recorded file identity.')
        if self.content_sha256 is not None and (not isinstance(self.content_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',self.content_sha256)):raise ValueError('Invalid full file identity.')
        return self

    @classmethod
    def create(cls, path, workspace_path=None, kind='source'):
        p = Path(path).resolve()
        ref = cls(str(p), filename=p.name, size=p.stat().st_size,
                  identity_fingerprint=fingerprint(p), kind=kind)
        ref.rebase(workspace_path)
        return ref

    def rebase(self, workspace_path):
        if workspace_path and self.absolute_path:
            try: self.relative_path = os.path.relpath(self.absolute_path, Path(workspace_path).resolve().parent)
            except ValueError: self.relative_path = None

    def matches(self, path):
        p = Path(path)
        try:
            return (p.is_file() and (self.size is None or p.stat().st_size == self.size)
                    and (not self.content_sha256 or file_revision(p) == self.content_sha256)
                    and (not self.identity_fingerprint or matches_fingerprint(p,self.identity_fingerprint)))
        except (OSError, ValueError): return False

    def resolve(self, workspace_path):
        choices = [Path(self.absolute_path)] if self.absolute_path else []
        if self.relative_path and workspace_path:
            choices.append(Path(workspace_path).resolve().parent / self.relative_path)
        return next((str(p.resolve()) for p in choices if self.matches(p)), None)

    def accept(self, path, workspace_path):
        if not self.matches(path): raise ValueError('Selected file does not match the recorded identity.')
        self.absolute_path = str(Path(path).resolve())
        self.filename = Path(path).name
        if self.size is None: self.size = Path(path).stat().st_size
        if not self.identity_fingerprint: self.identity_fingerprint = fingerprint(path)
        if self.identity_fingerprint.startswith('sampled-sha256:') and not self.content_sha256:
            self.content_sha256=file_revision(path)
        self.rebase(workspace_path)


@dataclass
class ViewState:
    x_channel: str | None = None
    y_channel: str | None = None
    x_transform: str = 'asinh'
    y_transform: str = 'asinh'
    cofactor: float = 150.0
    x_transform_params: dict = field(default_factory=lambda: LogicleParameters().as_dict())
    y_transform_params: dict = field(default_factory=lambda: LogicleParameters().as_dict())
    plot_mode: str = 'Density'
    axis_limits: dict | None = None
    axis_fit_mode: str = 'automatic'

    def validate(self):
        if any(v is not None and not isinstance(v,str) for v in (self.x_channel,self.y_channel)):
            raise ValueError('Saved channel names must be text.')
        if any(not isinstance(v,str) or v not in VALID_SCALES for v in (self.x_transform,self.y_transform)):
            raise ValueError('Unsupported saved display transform.')
        if isinstance(self.cofactor,bool) or not isinstance(self.cofactor,Real) or not math.isfinite(self.cofactor) or self.cofactor <= 0: raise ValueError('Invalid cofactor.')
        for params in (self.x_transform_params, self.y_transform_params):
            LogicleParameters.from_mapping(params)
        if self.plot_mode not in ('Dot Plot', 'Density', 'Contour Plot'): raise ValueError('Unknown plot mode.')
        if self.axis_fit_mode not in ('automatic', 'fit', 'locked'): raise ValueError('Invalid axis fit mode.')
        if self.axis_limits is not None:
            if not isinstance(self.axis_limits,dict):raise ValueError('Invalid saved axis limits.')
            for axis in ('x', 'y'):
                lim = self.axis_limits.get(axis)
                if lim is not None and (not isinstance(lim,(list,tuple)) or len(lim) != 2 or not all(isinstance(x,Real) and not isinstance(x,bool) and math.isfinite(x) for x in lim) or lim[0] >= lim[1]):
                    raise ValueError('Invalid saved axis limits.')
        return self

    def missing_channels(self, columns):
        return [ch for ch in (self.x_channel, self.y_channel) if ch and ch not in columns]

    @classmethod
    def from_dict(cls, data):
        if data is not None and not isinstance(data,dict):raise ValueError('Saved view must be an object.')
        d = dict(data or {})
        # Accept the proposed handoff representation without mapping channel names.
        params = d.pop('transform_parameters', {})
        if params is not None and not isinstance(params,dict):raise ValueError('Saved transform parameters must be an object.')
        if params:
            d.setdefault('cofactor', params.get('cofactor', 150.0))
            if all(k in params for k in ('T', 'W', 'M', 'A')):
                for axis in ('x', 'y'): d.setdefault(axis + '_transform_params', {k: params[k] for k in ('T', 'W', 'M', 'A')})
        if d.get('plot_mode') == 'Dot': d['plot_mode'] = 'Dot Plot'
        return cls(**d).validate()


@dataclass
class SampleReference:
    sample_id: str
    display_name: str
    source: FileReference
    active: bool = True
    excluded: bool = False
    view: ViewState | None = None
    gate_session: FileReference | None = None
    source_member_id: str | None = None


@dataclass
class AuditReference:
    audit_id: str
    name: str
    audit_type: str
    created_at: str
    result: FileReference
    selected_sample_ids: list[str]
    population_label: str
    status_summary: dict = field(default_factory=dict)
    decision_history: list[dict] = field(default_factory=list)

    def validate(self):
        if not isinstance(self.audit_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',self.audit_id) or self.audit_type not in ('qc','hierarchy'):
            raise ValueError('Invalid audit identity/type in workspace.')
        if any(not isinstance(v,str) for v in (self.name,self.created_at,self.population_label)):raise ValueError('Invalid audit metadata in workspace.')
        ids=self.selected_sample_ids
        if not isinstance(ids,list) or not ids or any(not isinstance(s,str) or not s for s in ids) or len(set(ids))!=len(ids):raise ValueError('Invalid audited sample selection in workspace.')
        if not isinstance(self.status_summary,dict) or not isinstance(self.decision_history,list):raise ValueError('Invalid audit history in workspace.')
        if any(not isinstance(k,str) or type(v) is not int or v<0 for k,v in self.status_summary.items()):raise ValueError('Invalid audit status counts in workspace.')
        for row in self.decision_history:
            if not isinstance(row,dict) or row.get('sample_id') not in ids or row.get('action') not in ('keep','exclude','restore','note') or any(not isinstance(row.get(key),str) for key in ('timestamp','reason_code','note')):
                raise ValueError('Invalid review decision in workspace.')
        self.result.validate()
        return self


@dataclass
class Workspace:
    workspace_schema: int = SCHEMA
    workspace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_with: str = 'vFlow 4.4.3rc18'
    samples: dict[str, SampleReference] = field(default_factory=dict)
    audits: dict[str, AuditReference] = field(default_factory=dict)
    overlay_view: ViewState = field(default_factory=ViewState)
    default_gate_session: FileReference | None = None
    groups: dict = field(default_factory=dict)
    gate_scope_state: dict = field(default_factory=lambda: {'default_scope': 'all_samples'})
    ui_state: dict = field(default_factory=lambda: {'view_mode': 'overlay', 'current_sample_id': None})
    tabs: dict = field(default_factory=dict)
    axis_aliases: dict = field(default_factory=dict)

    def references(self):
        for sid, sample in self.samples.items():
            yield 'sample:' + sid, sample.source
            if sample.gate_session: yield 'gate:' + sid, sample.gate_session
        if self.default_gate_session: yield 'gate:default', self.default_gate_session
        for aid,audit in self.audits.items(): yield 'audit:' + aid, audit.result

    def payload(self):
        return asdict(self)

    def save(self, path):
        canonical=str(Path(path).resolve());nominal=str(Path(path).absolute())
        if getattr(self,'_disk_nominal_path',None)==nominal and getattr(self,'_disk_path',None)!=canonical:
            raise ValueError('The saved workspace location changed outside this session. Your edits remain open; use Save As to keep a separate copy or reopen the current file.')
        expected=self._disk_revision if getattr(self,'_disk_path',None)==canonical else file_revision(canonical)
        staged=copy.deepcopy(self)
        for _,ref in staged.references():ref.rebase(canonical)
        payload=staged.payload()
        def validate_commit():
            if str(Path(path).resolve())!=canonical:raise ValueError('The workspace location changed while saving. Your edits remain open; retry with a separate Save As destination.')
            check_revision(canonical,expected)
        with workspace_lock(canonical):
            validate_commit()
            atomic_json(canonical,payload,before_replace=validate_commit)
        self._disk_path=canonical;self._disk_nominal_path=nominal
        self._disk_revision=byte_revision((json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
        staged_refs=dict(staged.references())
        for key,ref in self.references():ref.relative_path=staged_refs[key].relative_path

    @classmethod
    def load(cls, path):
        def reject_constant(value):raise ValueError('Non-finite JSON value in workspace: '+value)
        raw=Path(path).read_bytes();data=json.loads(raw.decode('utf-8'),parse_constant=reject_constant)
        if not isinstance(data, dict): raise ValueError('Workspace must be a JSON object.')
        validate_workspace_structure(data)
        version = data.get('workspace_schema')
        if type(version) is not int or version not in (1, SCHEMA):
            raise ValueError(f'Unsupported workspace schema {version!r}; supported: {SCHEMA}.')
        d = copy.deepcopy(data)
        d["workspace_schema"] = SCHEMA
        if not isinstance(d.get('audits',{}),dict):raise ValueError('Workspace audits must be an object.')
        try:
            d['audits']={aid:AuditReference(**{**item,'result':FileReference(**item['result'])}).validate() for aid,item in d.get('audits',{}).items()}
        except (KeyError,TypeError,AttributeError) as exc:raise ValueError('Malformed workspace audit reference.') from exc
        if any(aid!=ref.audit_id for aid,ref in d['audits'].items()):raise ValueError('Workspace audit key/identity mismatch.')
        for metadata in ('benchmark_fixture', 'note'): d.pop(metadata, None)
        default_path = d.pop('default_gate_session_path', None)
        sample_paths = d.pop('sample_gate_session_paths', {})
        if default_path and not d.get('default_gate_session'):
            d['default_gate_session'] = {'absolute_path': default_path if Path(default_path).is_absolute() else '', 'relative_path': default_path if not Path(default_path).is_absolute() else None, 'filename': Path(default_path).name, 'kind': 'gates'}
        samples = {}
        for sid, item in d.pop('samples', {}).items():
            source = FileReference(**item['source'])
            gate = item.get('gate_session')
            legacy_gate = sample_paths.get(sid) or item.get('gate_session_path')
            if legacy_gate and not gate:
                gate = {'absolute_path': legacy_gate if Path(legacy_gate).is_absolute() else '', 'relative_path': legacy_gate if not Path(legacy_gate).is_absolute() else None, 'filename': Path(legacy_gate).name, 'kind': 'gates'}
            samples[sid] = SampleReference(sid, item['display_name'], source,
                item.get('active', True), item.get('excluded', False),
                ViewState.from_dict(item['view']) if item.get('view') else None,
                FileReference(**gate) if gate else None, item.get("source_member_id"))
        d['samples'] = samples
        d['overlay_view'] = ViewState.from_dict(d.get('overlay_view'))
        if d.get('default_gate_session'):
            d['default_gate_session'] = FileReference(**d['default_gate_session'])
        result = cls(**d)
        result._disk_path=str(Path(path).resolve());result._disk_nominal_path=str(Path(path).absolute());result._disk_revision=byte_revision(raw)
        for _,ref in result.references():
            ref.validate()
            if not ref.absolute_path and ref.relative_path:
                ref.absolute_path=str((Path(result._disk_path).parent/ref.relative_path).resolve())
        # Validate all views before mutating any application state.
        for tab in result.tabs.values():
            ViewState.from_dict(tab.get('overlay_view'))
            for view in tab.get('sample_views', {}).values(): ViewState.from_dict(view)
        return result


def validate_workspace_structure(data):
    """Reject malformed containers before the live workspace can be replaced."""
    for name in ('samples','audits','tabs','groups','gate_scope_state','ui_state','axis_aliases','sample_gate_session_paths'):
        if name in data and not isinstance(data[name],dict):raise ValueError('Workspace '+name+' must be an object.')
    for name in ('workspace_id','created_with'):
        if name in data and (not isinstance(data[name],str) or not data[name].strip()):raise ValueError('Invalid workspace '+name+'.')
    if 'workspace_id' in data and not re.fullmatch(r'[A-Za-z0-9_-]+',data['workspace_id']):raise ValueError('Invalid workspace identity.')
    validate_ui_state(data.get('ui_state',{}))
    if any(not isinstance(value,str) for value in data.get('axis_aliases',{}).values()):raise ValueError('Channel aliases must be text.')
    for sid,item in data.get('samples',{}).items():
        if not isinstance(sid,str) or not sid or not isinstance(item,dict):raise ValueError('Malformed workspace sample.')
        if item.get('sample_id',sid)!=sid:raise ValueError('Workspace sample key/identity mismatch.')
        if not isinstance(item.get('display_name'),str) or not item['display_name'].strip() or not isinstance(item.get('source'),dict):raise ValueError('Malformed workspace sample metadata/source.')
        for key in ('active','excluded'):
            if key in item and type(item[key]) is not bool:raise ValueError('Sample '+key+' must be boolean.')
        if item.get('source_member_id') is not None and not isinstance(item['source_member_id'],str):raise ValueError('Invalid source member ID.')
    for tid,tab in data.get('tabs',{}).items():
        if not isinstance(tid,str) or not tid or not isinstance(tab,dict):raise ValueError('Malformed workspace tab.')
        for key in ('ui_state','sections','sample_views'):
            if key in tab and not isinstance(tab[key],dict):raise ValueError('Tab '+key+' must be an object.')
        validate_ui_state(tab.get('ui_state',{}))
        if any(type(value) is not bool for value in tab.get('sections',{}).values()):raise ValueError('Section visibility must be boolean.')
        if 'title' in tab and not isinstance(tab['title'],str):raise ValueError('Tab title must be text.')
        members=tab.get('sample_ids')
        if members is not None and (not isinstance(members,list) or any(not isinstance(s,str) for s in members)):raise ValueError('Invalid population membership.')
        lineage=tab.get('lineage',[])
        if not isinstance(lineage,list) or any(not isinstance(stage,dict) for stage in lineage):raise ValueError('Invalid population lineage.')
        for stage in lineage:
            if stage.get('workspace_tab_id') is not None and not isinstance(stage['workspace_tab_id'],str):raise ValueError('Invalid parent population tab.')
            if stage.get('gate_id') is not None and (type(stage['gate_id']) is not int or stage['gate_id']<0):raise ValueError('Invalid parent gate identity.')
            if 'region' in stage and not isinstance(stage['region'],str):raise ValueError('Invalid parent gate region.')

def validate_ui_state(ui):
    """Validate persisted fields consumed by Tk before replacing the live session.

    Unknown optional fields remain forward compatible; missing fields use the
    existing restore defaults. References may name removed/unavailable samples.
    """
    for key in ('view_mode','gate_scope','interface_size','auto_gate_input','workspace_name',
                'sidebar_task','sidebar_gate_tool','auto_gate_method'):
        if key in ui and not isinstance(ui[key],str):raise ValueError('Saved '+key+' must be text.')
    for key in ('current_sample_id','active_tab_id'):
        if ui.get(key) is not None and not isinstance(ui[key],str):raise ValueError('Invalid saved '+key+'.')
    for key in ('selected_sample_ids','active_sample_ids'):
        if key in ui and (not isinstance(ui[key],list) or any(not isinstance(s,str) for s in ui[key])):
            raise ValueError('Saved '+key+' must be a list of sample identities.')
    gid=ui.get('selected_gate_id')
    if gid is not None and (type(gid) is not int or gid<0):raise ValueError('Invalid saved selected gate.')
    width=ui.get('sidebar_width')
    if width is not None and (isinstance(width,bool) or not isinstance(width,Real) or not math.isfinite(width) or not 0<=width<=2147483647):raise ValueError('Invalid saved sidebar width.')
    fraction=ui.get('sample_panel_fraction')
    if fraction is not None and (isinstance(fraction,bool) or not isinstance(fraction,Real) or not math.isfinite(fraction) or not 0<=fraction<=1):raise ValueError('Invalid saved sample panel fraction.')
