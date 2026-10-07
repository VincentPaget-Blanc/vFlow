"""Single source of truth for ingestion, pickers and discovery.

MQD is recognized but deliberately fail-closed pending same-acquisition truth.
An FCS signature in an MQD is not sufficient to establish numeric semantics.
"""
from pathlib import Path
from .models import (ProbeResult, FlowSamplePayload, FlowReadResult,
                     UnsupportedFlowFormatError, UnvalidatedFlowFormatError)

FORMATS = {'csv': ('.csv',), 'fcs': ('.fcs',), 'lmd': ('.lmd',), 'mqd': ('.mqd',)}
DECODER_VERSION = 'ingestion-1'

def supported_flow_extensions():
    return tuple(ext for exts in FORMATS.values() for ext in exts)

def extensions_for_selection(selection='all'):
    # Preserve the historical csv+fcs batch filter as an explicitly narrow option.
    if selection == 'both': return FORMATS['csv'] + FORMATS['fcs']
    if selection in ('all', 'supported'): return supported_flow_extensions()
    return FORMATS.get(selection, ())

def supported_flow_filetypes_for_tk():
    exts = supported_flow_extensions()
    patterns = ' '.join(p for e in exts for p in ('*'+e, '*'+e.upper()))
    return [('Supported data files (MQD validation pending)', patterns)] + [
        (k.upper()+' files', ' '.join('*'+e+' *'+e.upper() for e in v)) for k,v in FORMATS.items()]

def is_generated_derivative(path):
    """Only hide a derivative from discovery when a matching sidecar proves ownership."""
    from .derivatives import derivative_is_owned
    return derivative_is_owned(path)

def probe_flow_format(path):
    path = Path(path)
    with path.open('rb') as stream: head = stream.read(4096)
    ext = path.suffix.lower()
    if ext == '.mqd': return ProbeResult('mqd', 'proprietary; validation pending', False)
    if ext == '.lmd': return ProbeResult('lmd', 'embedded FCS; validated on decode')
    if head[:3] == b'FCS': return ProbeResult('fcs', head[:6].decode('ascii', errors='replace'))
    if ext == '.csv':
        if b'\x00' in head: raise UnsupportedFlowFormatError('Binary data is not a supported CSV source.')
        try: head.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise UnsupportedFlowFormatError('CSV source must be UTF-8 text.') from exc
        return ProbeResult('csv', 'UTF-8 tabular text')
    raise UnsupportedFlowFormatError('Unsupported or corrupt data format: '+path.name)

class Reader:
    def __init__(self, format_id):
        self.format_id = format_id
        self.extensions = FORMATS[format_id]
    def probe(self, path): return probe_flow_format(path)
    def read(self, path):
        path = str(Path(path).resolve())
        if self.format_id == 'mqd':
            raise UnvalidatedFlowFormatError('MQD scientific decoding is blocked pending a validated same-acquisition MQD/FCS/CSV pair. No event values have been inferred.')
        if self.format_id == 'lmd':
            from .derivatives import load_or_materialize
            from .lmd_reader import decode_lmd
            return load_or_materialize(path, self.format_id, decode_lmd)
        if self.format_id == 'csv':
            from vflow.core.data_io import smart_read_csv
            df = smart_read_csv(path); meta = {}
            from .derivatives import read_meta, derivative_is_owned
            owned = read_meta(path) if derivative_is_owned(path) else None
            if owned:
                import pandas as pd
                source = str(Path(path).parent / owned['source_path_basename'])
                if not Path(source).is_file():source=owned['source_absolute_path']
                # Always load through the authoritative source: modified source
                # or stale/missing derived data must be validated/regenerated.
                result = read_flow_source(source)
                member = next((s for s in result.samples if s.source_member_id == owned['source_member_id']), None)
                if member is None: raise UnsupportedFlowFormatError('Recorded proprietary member is unavailable.')
                member.dataframe.attrs['vflow_sample_key'] = path
                return FlowReadResult([member], result.warnings)
        else:
            from vflow.core.fcs_reader import read_fcs
            df, meta = read_fcs(path)
        df.attrs.update(vflow_source_path=path, vflow_source_format=self.format_id,
                        vflow_materialized_path=None, vflow_source_member_id=None)
        return FlowReadResult([FlowSamplePayload(df, Path(path).name, path, source_format=self.format_id, metadata=meta)])

READERS = {k: Reader(k) for k in FORMATS}

def reader_for(path): return READERS[probe_flow_format(path).format_id]

def read_flow_source(path):
    from vflow.workspace.model import fingerprint
    source=Path(path).resolve();reader=reader_for(source)
    # Unsupported MQD still fails immediately without expensive whole-file I/O.
    if reader.format_id=='mqd':return reader.read(source)
    before=fingerprint(source);size=source.stat().st_size
    result=reader.read(source)
    direct=[sample for sample in result.samples if Path(sample.source_path).resolve()==source]
    # An owned CSV redirects to its original acquisition, which is checked by
    # the recursive read and may legitimately regenerate this derivative CSV.
    if direct and fingerprint(source)!=before:raise ValueError('Source changed while decoding; no events were admitted.')
    for sample in direct:
        sample.dataframe.attrs.update(vflow_source_identity=before,vflow_source_size=size)
    return result
