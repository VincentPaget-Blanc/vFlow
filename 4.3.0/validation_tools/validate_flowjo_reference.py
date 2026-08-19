#!/usr/bin/env python3
"""Compare vFlow's FCS decode with an independent raw float DATA decode."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import numpy as np

from vflow.core.fcs_reader import read_fcs


def _hdr_int(raw: bytes, a: int, b: int) -> int:
    s = raw[a:b].decode("ascii").strip()
    return int(s) if s else 0


def _primary_meta(raw: bytes) -> dict[str, str]:
    ts, te = _hdr_int(raw, 10, 18), _hdr_int(raw, 18, 26)
    text = raw[ts:te + 1].decode("ascii")
    d = text[0]
    toks, buf, i = [], [], 1
    while i < len(text):
        if text[i] == d:
            if i + 1 < len(text) and text[i + 1] == d:
                buf.append(d); i += 2; continue
            toks.append("".join(buf)); buf = []; i += 1; continue
        buf.append(text[i]); i += 1
    return {k.strip().upper(): v for k, v in zip(toks[0::2], toks[1::2])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fcs", type=Path)
    args = p.parse_args()
    raw = args.fcs.read_bytes()
    meta = _primary_meta(raw)
    total, par = int(meta["$TOT"]), int(meta["$PAR"])
    data_start = _hdr_int(raw, 26, 34) or int(meta["$BEGINDATA"])
    datatype = meta["$DATATYPE"].upper()
    byteord = meta["$BYTEORD"].replace(" ", "")
    endian = ">" if byteord == "4,3,2,1" else "<"
    if datatype == "F":
        dtype = np.dtype(endian + "f4")
    elif datatype == "D":
        dtype = np.dtype(endian + "f8")
    else:
        raise SystemExit(f"Reference validator expects floating DATA, got {datatype}")
    nbytes = total * par * dtype.itemsize
    direct = np.frombuffer(raw[data_start:data_start + nbytes], dtype=dtype,
                           count=total * par).astype(np.float64).reshape(total, par)

    df, _ = read_fcs(str(args.fcs))
    decoded = df.to_numpy(dtype=np.float64, copy=False)
    if direct.shape != decoded.shape:
        raise SystemExit(f"shape mismatch: direct={direct.shape}, reader={decoded.shape}")
    maxdiff = float(np.max(np.abs(direct - decoded))) if direct.size else 0.0
    finite = bool(np.isfinite(decoded).all())
    sha = hashlib.sha256(decoded.tobytes()).hexdigest()
    print(f"FCS path: {args.fcs.name}")
    print(f"shape: {decoded.shape[0]} x {decoded.shape[1]}")
    print(f"compatibility normalizations: {len(df.attrs.get('fcs_compatibility_fixes', ())) }")
    print(f"all finite: {finite}")
    print(f"maximum direct {('big' if endian == '>' else 'little')}-endian {dtype.name} DATA difference: {maxdiff}")
    print(f"decoded float64 SHA-256: {sha}")
    if maxdiff != 0.0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
