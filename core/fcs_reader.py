"""Pure-Python FCS reader for vFlow."""

from __future__ import annotations

import numpy as np
import pandas as pd


def read_fcs(path: str):
    """
    Read an FCS file and return (DataFrame, metadata_dict).

    Column names prefer $PnS (stain/marker name) over $PnN (short technical
    name).  Falls back to "Ch{n}" if neither is present.

    Handles:
      - FCS 2.0 / 3.0 / 3.1
      - DATATYPE F (float32), D (float64), I (integer, per-channel bit widths)
      - Big-endian and little-endian byte order
      - $PnE log-decade encoding for integer data
      - $BEGINDATA / $ENDDATA override for non-standard writers and large files
      - Mixed per-channel $PnB widths (8 / 16 / 32 / 64-bit) in DATATYPE I

    Fixed in v4.0.14 (Bugs 1, 2, 3, 6):
      Bug 1: DATATYPE I now builds a per-channel structured dtype so mixed
             bit-widths (e.g. Time=64-bit + fluorescence=16-bit) are read
             correctly rather than misaligned via a uniform max-bits dtype.
      Bug 2: Data-bytes slice guard now evaluated AFTER $BEGINDATA/$ENDDATA
             override, not before; previously large-file header zeros caused
             the guard to fire the wrong branch.
      Bug 3: $PnE f2==0 handled with explicit float comparison (not truthiness)
             to match FCS 3.1 §3.3 unambiguously.
      Bug 6: data_end==0 is treated as "read to EOF" even after override,
             preventing a 0:1 slice when both offsets legitimately absent.
    """
    with open(path, 'rb') as f:
        raw = f.read()

    version = raw[:6].decode('ascii', errors='replace').strip()
    if not version.startswith('FCS'):
        raise ValueError(f"Not a valid FCS file — header: {version!r}")

    def _hdr_int(b):
        s = b.decode('ascii', errors='replace').strip()
        return int(s) if s else 0

    text_start = _hdr_int(raw[10:18])
    text_end   = _hdr_int(raw[18:26])
    # Read header offsets — may be zero for large (>99 MB) FCS 3.1 files.
    # Real offsets for those files live in $BEGINDATA / $ENDDATA in the TEXT
    # segment; we store the header values here and override below.
    data_start = _hdr_int(raw[26:34])
    data_end   = _hdr_int(raw[34:42])

    # ── Parse TEXT segment ────────────────────────────────────────────────
    text_raw = raw[text_start:text_end + 1].decode('latin-1', errors='replace')
    if not text_raw:
        raise ValueError("FCS TEXT segment is empty")
    delim = text_raw[0]
    parts = text_raw[1:].split(delim)
    if parts and parts[-1] == '':
        parts = parts[:-1]
    meta: dict = {}
    for i in range(0, len(parts) - 1, 2):
        meta[parts[i].strip().upper()] = parts[i + 1]

    n_params = int(meta.get('$PAR', '0'))
    if n_params == 0:
        raise ValueError("FCS file reports 0 parameters ($PAR=0)")

    # ── Channel names (prefer $PnS stain label) ───────────────────────────
    channels = []
    seen: dict = {}
    for i in range(1, n_params + 1):
        short = meta.get(f'$P{i}N', f'Ch{i}').strip()
        stain = meta.get(f'$P{i}S', '').strip()
        name  = stain if stain else short
        if name in seen:
            seen[name] += 1
            name = f'{name}_{seen[name]}'
        else:
            seen[name] = 0
        channels.append(name)

    # ── Locate DATA segment ($BEGINDATA / $ENDDATA override header) ───────
    # FIX BUG 2 + BUG 6: Override MUST happen before the data_bytes slice is
    # computed.  Original code evaluated the slice guard before this block.
    if '$BEGINDATA' in meta:
        try:
            data_start = int(meta['$BEGINDATA'])
        except ValueError:
            pass
    if '$ENDDATA' in meta:
        try:
            data_end = int(meta['$ENDDATA'])
        except ValueError:
            pass

    # ── Determine dtype ───────────────────────────────────────────────────
    data_type  = meta.get('$DATATYPE', 'F').upper()
    byte_order = meta.get('$BYTEORD', '1,2,3,4').strip()
    big_endian = byte_order.startswith('4')
    endian     = '>' if big_endian else '<'

    if data_type == 'F':
        dtype = np.dtype(endian + 'f4')
        bpp   = 4
        uniform_width = True

    elif data_type == 'D':
        dtype = np.dtype(endian + 'f8')
        bpp   = 8
        uniform_width = True

    elif data_type == 'I':
        # FIX BUG 1: FCS 3.1 §3.1 states each parameter may have an independent
        # $PnB value.  The original code used max($PnB) for ALL channels, which
        # misaligns the byte stream whenever channels differ in width.
        # Build one dtype entry per channel using a numpy structured dtype.
        bits_per_param = []
        for i in range(1, n_params + 1):
            try:
                b = int(meta.get(f'$P{i}B', '32'))
            except ValueError:
                b = 32
            bits_per_param.append(b)

        # Check whether all channels share the same width — if so we can use
        # the fast frombuffer/reshape path; otherwise use the structured dtype.
        unique_widths = set(bits_per_param)
        if len(unique_widths) == 1:
            # Fast path: uniform width
            max_bits = bits_per_param[0]
            if   max_bits <=  8: dtype = np.dtype(endian + 'u1'); bpp = 1
            elif max_bits <= 16: dtype = np.dtype(endian + 'u2'); bpp = 2
            elif max_bits <= 32: dtype = np.dtype(endian + 'u4'); bpp = 4
            else:                dtype = np.dtype(endian + 'u8'); bpp = 8
            uniform_width = True
        else:
            # Mixed-width path: numpy structured dtype with one field per channel
            fields   = []
            row_bytes_struct = 0
            for i, bits in enumerate(bits_per_param):
                if   bits <=  8: t = 'u1'; w = 1
                elif bits <= 16: t = 'u2'; w = 2
                elif bits <= 32: t = 'u4'; w = 4
                else:            t = 'u8'; w = 8
                fields.append((f'_f{i}', np.dtype(endian + t)))
                row_bytes_struct += w
            struct_dtype  = np.dtype(fields)
            uniform_width = False
            bpp = None  # not used in mixed path; row_bytes_struct used instead

    else:
        raise ValueError(f"Unsupported FCS $DATATYPE: {data_type!r}")

    # ── Slice DATA bytes ──────────────────────────────────────────────────
    # FIX BUG 2 + BUG 3: Evaluate the slice AFTER the $BEGINDATA/$ENDDATA
    # override.  Guard: data_end must be strictly positive AND > data_start.
    # When both are 0 (unset in header AND absent from TEXT), fall back to
    # reading from data_start to EOF.
    if data_end > 0 and data_end > data_start:
        data_bytes = raw[data_start : data_end + 1]  # FCS byte ranges are inclusive
    else:
        data_bytes = raw[data_start:]

    # ── Compute event count ───────────────────────────────────────────────
    total_events = int(meta.get('$TOT', '0'))

    if data_type == 'I' and not uniform_width:
        # Mixed-width: row size comes from the structured dtype
        row_bytes = struct_dtype.itemsize
    else:
        row_bytes = n_params * bpp if bpp else 0

    if row_bytes > 0:
        n_fit = len(data_bytes) // row_bytes
        if total_events == 0 or n_fit < total_events:
            # Trust the byte count over $TOT when they disagree — some writers
            # truncate the file or report $TOT before writing all events.
            total_events = n_fit

    # ── Read DATA array ───────────────────────────────────────────────────
    payload = data_bytes[:total_events * row_bytes]

    if data_type in ('F', 'D'):
        arr = np.frombuffer(payload, dtype=dtype).reshape(
            total_events, n_params).astype(np.float64)

    elif data_type == 'I' and uniform_width:
        arr = np.frombuffer(payload, dtype=dtype).reshape(
            total_events, n_params).astype(np.float64)

    else:
        # Mixed per-channel widths: unpack via structured dtype then stack
        arr_struct = np.frombuffer(payload, dtype=struct_dtype)
        arr = np.column_stack(
            [arr_struct[f'_f{i}'].astype(np.float64)
             for i in range(n_params)]
        )

    # ── Apply $PnE (log-decade) scaling for integer channels ─────────────
    # FIX BUG 3 (minor): FCS spec says f2=0 means "use f2=1".
    # Use an explicit float comparison rather than truthiness to be
    # unambiguous for IEEE edge cases.
    if data_type == 'I':
        for i in range(n_params):
            pne = meta.get(f'$P{i+1}E', '0,0')
            try:
                f1_str, f2_str = pne.split(',')
                f1 = float(f1_str)
                f2 = float(f2_str)
                rng_val = float(meta.get(f'$P{i+1}R', '1024'))
                if f1 > 0 and rng_val > 0:
                    # FCS 3.1 §3.3: channel_value = f2 × 10^(f1 × raw / range)
                    # When f2 == 0, the spec requires treating f2 as 1.
                    f2_eff = f2 if f2 != 0.0 else 1.0
                    arr[:, i] = f2_eff * (10.0 ** (f1 * arr[:, i] / rng_val))
            except Exception:
                pass  # malformed $PnE — leave channel as raw integer counts

    return pd.DataFrame(arr, columns=channels), meta

