"""Bounded candidate validation for FCS-compatible LMD containers.

Independent valid members are exposed independently. Equivalent representations
are deduplicated only when their decoded event tables are actually identical.
"""
import mmap
import re
from pathlib import Path
import pandas as pd
from vflow.core.fcs_reader import read_fcs_bytes
from .models import FlowReadResult, FlowSamplePayload, UnsupportedFlowFormatError

def decode_lmd(path):
    candidates = []; failures = []
    with open(path, 'rb') as stream:
        if Path(path).stat().st_size < 58: raise UnsupportedFlowFormatError('LMD is too short for an event dataset.')
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as raw:
            for match in re.finditer(rb'FCS[123]\.[012]', raw):
                base = match.start()
                if len(candidates) > 128: raise UnsupportedFlowFormatError('LMD has too many embedded dataset candidates.')
                try:
                    if base+58 > len(raw): continue
                    offsets = [int(raw[base+i:base+i+8].strip() or b'0') for i in (10,18,26,34,42,50)]
                    ts,te,ds,de,as_,ae = offsets
                    if ts < 58 or te < ts or base+te >= len(raw): continue
                    from vflow.core.fcs_reader import _parse_text_segment
                    meta = _parse_text_segment(raw[base+ts:base+te+1].decode('utf-8'))
                    ds = ds or int(meta.get('$BEGINDATA',0));de = de or int(meta.get('$ENDDATA',0))
                    end = max(te,de,ae,int(meta.get('$ENDSTEXT',0)))
                    if ds < 58 or de < ds or base+end >= len(raw): continue
                    df,metadata = read_fcs_bytes(raw[base:base+end+1],allow_nextdata=True)
                    candidates.append((base, df, metadata))
                except (ValueError, UnicodeError, OverflowError) as exc: failures.append(str(exc))
    if not candidates: raise UnsupportedFlowFormatError('No validated embedded FCS event dataset in LMD. '+ '; '.join(failures[:2]))
    by_offset={base:(df,meta) for base,df,meta in candidates}
    ignored=set();representation_choices=[]
    for base,df,meta in candidates:
        nxt=int(meta.get('$NEXTDATA',0))
        if not nxt:continue
        target=base+nxt
        if target not in by_offset:raise UnsupportedFlowFormatError('LMD next-dataset pointer has no validated target; incomplete containers are rejected.')
        modern,mm=by_offset[target]
        legacy_version=meta.get('_vflow_fcs_version')=='FCS2.0'
        instrument=meta.get('$CYT','').lower()
        beckman=any(v in instrument for v in ('gallios','navios','fc500','fc 500','cytomics'))
        addresses=lambda m:{m.get(f'@P{i}ADDRESS') for i in range(1,int(m['$PAR'])+1)}
        legacy_addresses=addresses(meta);modern_addresses=addresses(mm)
        # The Beckman dual representation is identified by its chained dataset,
        # instrument identity, equal counts and exact hardware measurement IDs.
        # Legacy compressed display values are intentionally not substituted for
        # the higher-resolution 3.0 list-mode measurements.
        if legacy_version and beckman and mm.get('_vflow_fcs_version','')>='FCS3.0' and df.shape==modern.shape and None not in legacy_addresses and legacy_addresses==modern_addresses:
            ignored.add(base)
            representation_choices.append({'selected_offset':target,'superseded_display_offset':base,
                'reason':'Beckman chained legacy display / high-resolution dataset with matching event counts and hardware parameter identities'})
            modern.attrs['lmd_acquisition_metadata']=meta
    candidates=[item for item in candidates if item[0] not in ignored]
    # Highest version first, but only proven equivalent tables are collapsed.
    candidates.sort(key=lambda x:x[2].get('_vflow_fcs_version',''),reverse=True)
    unique = []
    for base,df,meta in candidates:
        if any(df.equals(item[1]) for item in unique): continue
        unique.append((base,df,meta))
    unique.sort(key=lambda x:x[0])
    return FlowReadResult([FlowSamplePayload(df, Path(path).name + ('' if len(unique)==1 else f' dataset {i+1}'),
        str(Path(path).resolve()), f'offset-{base}', 'lmd', {'embedded_offset':base,'fcs_metadata':meta,'representation_choices':representation_choices})
        for i,(base,df,meta) in enumerate(unique)])
