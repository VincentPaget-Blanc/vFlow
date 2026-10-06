"""Sparse gate ownership and one sample-aware lineage boundary."""
import copy
from dataclasses import dataclass, field
from vflow.core.gate_definition import GateDefinition
from vflow.services.gate_session import prepare_gate_session_load
from vflow.core.gate_masks import selected_region_mask
from vflow.services.population_evaluation import regions_in_explicit_context


def plain(gate):
    return GateDefinition.from_live_dict(gate).to_plain_dict()


def decode_session(payload, fallback_context=None):
    if not isinstance(payload, dict): raise ValueError('Gate session must be an object.')
    version = payload.get('version', 1)
    if type(version) is not int or version not in (1, 2, 3): raise ValueError('Unsupported gate session version.')
    prep = prepare_gate_session_load(payload, gate_file_version=version, current_next_id=0)
    if prep.skipped_count or prep.context_errors or not prep.contexts_container_valid:
        raise ValueError('Invalid gate geometry/context: ' + '; '.join(prep.context_errors))
    result = []
    for clean in prep.clean_gates:
        g = copy.deepcopy(clean)
        ctx = (prep.saved_contexts or {}).get(str(g['id'])) or fallback_context
        if not ctx: raise ValueError('Legacy gate session needs an explicit saved view context.')
        g['_analysis_context'] = copy.deepcopy(ctx)
        g['x_thresh_vars'] = list(g['x_thresh_active'])
        g['y_thresh_var'] = g['y_thresh_active']
        g['y_thresh_vars'] = list(g['y_thresh_actives'])
        metadata = payload.get('workspace_auto_fit', {}).get(str(g['id']))
        if isinstance(metadata, dict): g['_auto_fit'] = copy.deepcopy(metadata)
        result.append(g)
    return result


@dataclass
class GateStore:
    global_gates: list = field(default_factory=list)
    sample_overrides: dict = field(default_factory=dict)
    # Reserved extension point, kept out of current UI.
    group_overrides: dict = field(default_factory=dict)
    sample_groups: dict = field(default_factory=dict)
    revision: int = 0
    _undo: list = field(default_factory=list, repr=False)
    editing: bool = field(default=False, repr=False)

    def snapshot(self):
        return copy.deepcopy((self.global_gates, self.sample_overrides))

    def checkpoint(self):
        self._undo.append(self.snapshot())
        del self._undo[:-50]

    def undo(self):
        if not self._undo: return False
        self.global_gates, self.sample_overrides = self._undo.pop()
        self.revision += 1
        return True

    def resolve_gate(self, sample_id, gate_id):
        override = self.sample_overrides.get(sample_id, {})
        if gate_id in override: return copy.deepcopy(override[gate_id])
        group = self.sample_groups.get(sample_id)
        if gate_id in self.group_overrides.get(group, {}):
            return copy.deepcopy(self.group_overrides[group][gate_id])
        return copy.deepcopy(next((g for g in self.global_gates if g['id'] == gate_id), None))

    def resolve_gate_set(self, sample_id):
        ids = [g['id'] for g in self.global_gates]
        ids.extend(i for i in self.sample_overrides.get(sample_id, {}) if i not in ids)
        return [g for i in ids if (g := self.resolve_gate(sample_id, i)) is not None]

    def copy_to_sample(self, gate, sample_id, columns):
        context = gate.get('_analysis_context') or {}
        missing = [context.get(k) for k in ('x_channel', 'y_channel') if context.get(k) not in columns]
        if missing: raise ValueError('Gate unavailable for this sample. Required channel: ' + ', '.join(str(x) for x in missing))
        self.checkpoint()
        self.sample_overrides.setdefault(sample_id, {})[gate['id']] = plain(gate)
        self.revision += 1

    def reset(self, sample_id, gate_id):
        self.checkpoint()
        self.sample_overrides.get(sample_id, {}).pop(gate_id, None)
        self.revision += 1

    def promote(self, sample_id, gate_id):
        gate = self.resolve_gate(sample_id, gate_id)
        if not gate: raise ValueError('Gate unavailable.')
        self.checkpoint()
        self.global_gates = [g for g in self.global_gates if g['id'] != gate_id] + [gate]
        self.sample_overrides.get(sample_id, {}).pop(gate_id, None)
        self.revision += 1

    def apply_workspace(self, gate):
        """Make one resolved geometry authoritative, removing only its overrides."""
        self.checkpoint()
        gid = gate['id']
        self.global_gates = [g for g in self.global_gates if g['id'] != gid] + [plain(gate)]
        for overrides in self.sample_overrides.values(): overrides.pop(gid, None)
        for overrides in self.group_overrides.values(): overrides.pop(gid, None)
        self.revision += 1

    @staticmethod
    def selected_changes(gates, baseline):
        old = {g['id']: plain(g) for g in baseline}
        new = {g['id']: plain(g) for g in gates}
        changed = {}
        for gid in old.keys() | new.keys():
            a, b = copy.deepcopy(old.get(gid)), copy.deepcopy(new.get(gid))
            if a is not None and b is not None:
                a.pop('_analysis_context', None); b.pop('_analysis_context', None)
            if a != b: changed[gid] = new.get(gid)
        return changed

    def commit_selected(self, gates, sample_ids, baseline):
        changed = self.selected_changes(gates, baseline)
        if not changed: return False
        before = self.snapshot()
        if not self.editing and (not self._undo or self._undo[-1] != before): self.checkpoint()
        global_ids = {g['id'] for g in self.global_gates}
        for sid in sample_ids:
            overrides = self.sample_overrides.setdefault(sid, {})
            for gid, gate in changed.items():
                if gate is None and gid not in global_ids: overrides.pop(gid, None)
                else: overrides[gid] = copy.deepcopy(gate)
        if self.snapshot() != before:
            self.revision += 1
            return True
        if not self.editing: self._undo.pop()
        return False

    def commit(self, gates, sample_id=None):
        incoming = [plain(g) for g in gates]
        before = self.snapshot()
        if sample_id is None:
            self.global_gates = incoming
        else:
            global_map = {g['id']: g for g in self.global_gates}
            overrides = self.sample_overrides.setdefault(sample_id, {})
            present = {g['id'] for g in incoming}
            for g in incoming:
                # Ignore pure display-transform rebinding when deciding whether an override exists.
                a, b = copy.deepcopy(g), copy.deepcopy(global_map.get(g['id']))
                if b is not None:
                    a.pop('_analysis_context', None); b.pop('_analysis_context', None)
                if a != b or g['id'] in overrides: overrides[g['id']] = g
            for gid in set(global_map) - present:
                # A sample-only delete is a sparse tombstone, not a global delete.
                overrides[gid] = None
            for gid in list(overrides):
                if gid not in present and gid not in global_map: overrides.pop(gid)
        if before != self.snapshot():
            if not self.editing and (not self._undo or self._undo[-1] != before):
                self._undo.append(before); del self._undo[:-50]
            self.revision += 1
        return before != self.snapshot()


def resolve_lineage_for_sample(sample_id, lineage, stores):
    result = copy.deepcopy(lineage)
    for stage in result:
        tab_id = stage.get('workspace_tab_id')
        if tab_id is None: continue  # legacy immutable provenance remains supported
        store = stores.get(tab_id)
        if store is None: raise ValueError('Required parent gate session is unavailable.')
        gate = store.resolve_gate(sample_id, stage['gate']['id'])
        if gate is None: raise ValueError('Parent gate was removed for this sample.')
        stage['gate'] = gate
        stage['context'] = copy.deepcopy(gate.get('_analysis_context') or stage['context'])
    return result


def filter_lineage(df, lineage):
    for stage in lineage:
        ctx = stage['context']; x, y = ctx['x_channel'], ctx['y_channel']
        if x not in df or y not in df: raise ValueError(f'Parent gate unavailable. Required channels: {x}, {y}')
        regions, _ = regions_in_explicit_context(stage['gate'], df[x].to_numpy(float), df[y].to_numpy(float), ctx, fallback_cofactor=150.0)
        if stage['region'] != 'All regions' and stage['region'] not in regions:
            raise ValueError(f"Parent region {stage['region']!r} no longer exists. Undo the gate edit or select an existing region.")
        mask = selected_region_mask(regions, total=len(df), gate_type=stage['gate'].get('type', 'crosshair'), region_name=stage['region'])
        df = df.loc[mask].reset_index(drop=True)
    return df
