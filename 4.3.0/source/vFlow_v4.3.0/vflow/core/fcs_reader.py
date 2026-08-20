"""Pure-Python FCS 2.0/3.0/3.1 reader used by vFlow."""

from __future__ import annotations

import math
import re
import numpy as np
import pandas as pd


def _parse_text_segment(text_raw: str) -> dict:
    if not text_raw:
        raise ValueError("FCS TEXT segment is empty")
    delim = text_raw[0]
    if not delim or ord(delim) < 1 or ord(delim) > 126:
        raise ValueError("Invalid FCS TEXT delimiter")

    # In FCS, a delimiter occurring inside a keyword/value is escaped by
    # doubling it. Parse character-by-character so e.g. /$SYS/RSX-11//M/
    # yields the value RSX-11/M instead of corrupting all following pairs.
    tokens = []
    buf = []
    i = 1
    while i < len(text_raw):
        ch = text_raw[i]
        if ch == delim:
            if i + 1 < len(text_raw) and text_raw[i + 1] == delim:
                buf.append(delim)
                i += 2
                continue
            tokens.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        trailing = "".join(buf)
        # Compatibility: some TextToFCS/FlowJo-generated FCS 3.0 files pad
        # the declared TEXT segment with ASCII whitespace after the final
        # delimiter.  That padding is not a keyword/value token and must not
        # make an otherwise valid TEXT segment appear malformed.  Non-space
        # trailing content remains an error via the odd-token check below.
        if trailing.strip():
            tokens.append(trailing)
    if len(tokens) % 2:
        raise ValueError("Malformed FCS TEXT segment: unmatched keyword/value token")

    meta = {}
    for key, value in zip(tokens[0::2], tokens[1::2]):
        key = key.strip().upper()
        if not key:
            raise ValueError("Malformed FCS TEXT segment: empty keyword")
        if key in meta:
            raise ValueError(
                f"Malformed FCS TEXT segment: duplicate keyword {key!r}; "
                "FCS keywords must be unique within a data set."
            )
        meta[key] = value
    return meta


def _unique_channel_names(meta: dict, n_params: int) -> list[str]:
    channels, _ = _channel_names_with_ambiguities(meta, n_params)
    return channels


def _channel_names_with_ambiguities(meta: dict, n_params: int) -> tuple[list[str], tuple[str, ...]]:
    """Return display names and channels unsafe for positional cross-file matching.

    ``$PnS`` is preferred as the biological display label. Duplicate labels are
    suffixed to keep one DataFrame column per parameter, but those suffixes are
    determined by parameter order. Across files, reordered duplicate stains can
    therefore make the same visible suffix refer to a different detector. Mark
    every duplicate/collision-generated name as ambiguous so multi-file channel
    selection can fail closed until the user explicitly resolves nomenclature.
    """
    bases: list[str] = []
    for i in range(1, n_params + 1):
        short = meta.get(f"$P{i}N", f"Ch{i}").strip()
        stain = meta.get(f"$P{i}S", "").strip()
        base = stain if stain else short
        bases.append(base or f"Ch{i}")

    base_counts: dict[str, int] = {}
    for base in bases:
        base_counts[base.casefold()] = base_counts.get(base.casefold(), 0) + 1

    channels: list[str] = []
    ambiguous: list[str] = []
    used_casefold = set()
    for base in bases:
        name = base
        suffix = 1
        while name.casefold() in used_casefold:
            name = f"{base}_{suffix}"
            suffix += 1
        used_casefold.add(name.casefold())
        channels.append(name)
        if base_counts.get(base.casefold(), 0) > 1 or name != base:
            ambiguous.append(name)

    # If a generated suffix occupied another parameter's natural base name, that
    # latter channel is also part of the collision chain even if its base itself
    # was unique (e.g. A, A, A_1 -> A, A_1, A_1_1).
    generated_casefold = {
        name.casefold() for name, base in zip(channels, bases) if name != base
    }
    for name, base in zip(channels, bases):
        if base.casefold() in generated_casefold and name not in ambiguous:
            ambiguous.append(name)

    return channels, tuple(ambiguous)


def _byte_order(meta: dict) -> str:
    value = meta.get("$BYTEORD")
    if value is None:
        raise ValueError("FCS TEXT segment is missing required $BYTEORD")
    normalized = value.replace(" ", "")
    if normalized == "1,2,3,4":
        return "<"
    if normalized == "4,3,2,1":
        return ">"
    raise ValueError(
        f"Unsupported FCS $BYTEORD {value!r}; FCS 3.1 permits only "
        "'1,2,3,4' or '4,3,2,1'."
    )


def _unpack_integer_events(payload: bytes, bits_per_param: list[int], total_events: int, endian: str) -> np.ndarray:
    """Unpack FCS integer DATA, including non-byte-aligned tight packing."""
    event_bits = sum(bits_per_param)
    needed_bits = total_events * event_bits
    if len(payload) * 8 < needed_bits:
        raise ValueError("FCS DATA segment is truncated")

    # Fast byte-aligned path for the overwhelmingly common 8/16/32/64-bit case.
    if all(bits in (8, 16, 32, 64) for bits in bits_per_param):
        fields = []
        for i, bits in enumerate(bits_per_param):
            fields.append((f"f{i}", np.dtype(endian + f"u{bits // 8}")))
        dtype = np.dtype(fields)
        expected = total_events * dtype.itemsize
        data = np.frombuffer(payload[:expected], dtype=dtype, count=total_events)
        return np.column_stack([data[f"f{i}"].astype(np.uint64) for i in range(len(bits_per_param))])

    # Tight bit packing is defined as a continuous bit stream. Interpret bytes
    # in their declared numeric order and consume each parameter width exactly.
    bitorder = "little" if endian == "<" else "big"
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8), bitorder=bitorder)
    out = np.empty((total_events, len(bits_per_param)), dtype=np.uint64)
    pos = 0
    for event in range(total_events):
        for col, width in enumerate(bits_per_param):
            chunk = bits[pos:pos + width]
            pos += width
            if bitorder == "little":
                weights = 1 << np.arange(width, dtype=object)
            else:
                weights = 1 << np.arange(width - 1, -1, -1, dtype=object)
            out[event, col] = int(np.sum(chunk.astype(object) * weights))
    return out


def read_fcs(path: str):
    """Read an FCS 2.0/3.0/3.1 list-mode file as ``(DataFrame, metadata)``.

    The reader fails closed on malformed/truncated offsets instead of silently
    treating header/text bytes as events. FCS 3.1 TEXT escaping, the two legal
    byte orders, mixed integer widths, and tightly packed integer fields are
    handled explicitly.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) < 58:
        raise ValueError("FCS file is shorter than the required 58-byte HEADER")

    version = raw[:6].decode("ascii", errors="replace").strip()
    if version not in {"FCS2.0", "FCS3.0", "FCS3.1"}:
        raise ValueError(f"Unsupported or invalid FCS version/header: {version!r}")

    def hdr_int(segment: bytes) -> int:
        value = segment.decode("ascii", errors="strict").strip()
        return int(value) if value else 0

    text_start = hdr_int(raw[10:18])
    text_end = hdr_int(raw[18:26])
    data_start = hdr_int(raw[26:34])
    data_end = hdr_int(raw[34:42])
    header_data_start = data_start
    header_data_end = data_end

    if text_start < 58 or text_end < text_start or text_end >= len(raw):
        raise ValueError(
            f"Invalid FCS TEXT offsets: start={text_start}, end={text_end}, file={len(raw)} bytes"
        )
    text_encoding = "utf-8" if version == "FCS3.1" else "ascii"
    try:
        text_raw = raw[text_start:text_end + 1].decode(text_encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"FCS {version} TEXT segment is not valid {text_encoding.upper()}."
        ) from exc
    meta = _parse_text_segment(text_raw)
    compatibility_fixes = []
    # Record (rather than hide) tolerated exporter quirks. A TEXT segment
    # ending in whitespace after its final delimiter is emitted by FlowJo
    # TextToFCS and is safe to normalize because the padding is outside the
    # final keyword/value pair.
    if text_raw and text_raw[-1].isspace():
        compatibility_fixes.append("TEXT trailing whitespace padding ignored")

    required = ["$MODE", "$DATATYPE", "$PAR", "$TOT", "$BYTEORD"]
    if version == "FCS3.1":
        required += [
            "$BEGINANALYSIS", "$BEGINDATA", "$BEGINSTEXT",
            "$ENDANALYSIS", "$ENDDATA", "$ENDSTEXT", "$NEXTDATA",
        ]
    missing = [key for key in required if key not in meta]
    if missing:
        raise ValueError("FCS TEXT segment missing required keyword(s): " + ", ".join(missing))
    if meta["$MODE"].upper() != "L":
        raise ValueError(f"Unsupported FCS $MODE {meta['$MODE']!r}; vFlow requires list mode (L)")

    n_params = int(meta["$PAR"])
    total_events = int(meta["$TOT"])
    if n_params <= 0 or total_events < 0:
        raise ValueError(f"Invalid FCS $PAR/$TOT values: {n_params}/{total_events}")

    def _meta_offset(key: str, default: int = 0) -> int:
        if key not in meta:
            return default
        try:
            value = int(meta[key])
        except ValueError as exc:
            raise ValueError(f"Invalid numeric FCS keyword {key}={meta[key]!r}") from exc
        if value < 0:
            raise ValueError(f"FCS offset {key} cannot be negative")
        return value

    # Supplemental TEXT may legally contain optional keywords that affect
    # interpretation (for example $PnG, $PnS, $TIMESTEP, or $SPILLOVER).
    # Parse it before channel naming and numeric conversion so such metadata is
    # never silently ignored. Keywords are unique across the entire data set.
    stext_start = _meta_offset("$BEGINSTEXT", 0)
    stext_end = _meta_offset("$ENDSTEXT", 0)
    parsed_supplemental_offsets = None
    if bool(stext_start) != bool(stext_end):
        raise ValueError(
            "FCS supplemental TEXT requires both $BEGINSTEXT and $ENDSTEXT "
            "to be zero or both non-zero."
        )
    if stext_start and stext_end:
        overlaps_primary = not (stext_end < text_start or stext_start > text_end)
        # FlowJo TextToFCS v1.3 writes bogus STEXT offsets spanning its primary
        # TEXT segment. This is not a real supplemental segment; preserve the
        # certified compatibility normalization rather than parsing primary
        # metadata a second time as duplicates.
        is_texttofcs_overlap = (
            version == "FCS3.0"
            and "TEXTTOFCS" in meta.get("$CYT", "").upper()
            and overlaps_primary
        )
        if is_texttofcs_overlap:
            # Preserve the certified TextToFCS compatibility surface: this
            # exporter quirk was already tolerated before supplemental-TEXT
            # support existed, so do not add a new user-visible normalization
            # notice merely because the parser now recognizes the bogus fields.
            pass
        else:
            if stext_start < 58 or stext_end < stext_start or stext_end >= len(raw):
                raise ValueError(
                    f"Invalid FCS supplemental TEXT offsets: start={stext_start}, "
                    f"end={stext_end}, file={len(raw)} bytes"
                )
            if overlaps_primary:
                raise ValueError("FCS supplemental TEXT overlaps the primary TEXT segment.")
            # HEADER DATA offsets are already available even before the primary
            # TEXT $BEGINDATA/$ENDDATA values are reconciled below. Reject any
            # clear segment overlap instead of treating event bytes as metadata.
            if header_data_start and header_data_end:
                if not (stext_end < header_data_start or stext_start > header_data_end):
                    raise ValueError("FCS supplemental TEXT overlaps the DATA segment.")
            try:
                supplemental_raw = raw[stext_start:stext_end + 1].decode(
                    text_encoding, errors="strict"
                )
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"FCS {version} supplemental TEXT is not valid "
                    f"{text_encoding.upper()}."
                ) from exc
            supplemental = _parse_text_segment(supplemental_raw)
            duplicates = sorted(set(meta).intersection(supplemental))
            if duplicates:
                raise ValueError(
                    "FCS keyword(s) repeated between primary and supplemental TEXT: "
                    + ", ".join(duplicates)
                )
            meta.update(supplemental)
            parsed_supplemental_offsets = (stext_start, stext_end)

    channels, ambiguous_channel_names = _channel_names_with_ambiguities(meta, n_params)

    # DATA offsets are duplicated in HEADER/TEXT while they fit in HEADER.
    # Reject disagreement rather than choosing one source silently.

    text_data_start = _meta_offset("$BEGINDATA", 0)
    text_data_end = _meta_offset("$ENDDATA", 0)
    if header_data_start and text_data_start and header_data_start != text_data_start:
        raise ValueError(
            f"FCS DATA start offset disagrees between HEADER ({header_data_start}) "
            f"and $BEGINDATA ({text_data_start})."
        )
    if header_data_end and text_data_end and header_data_end != text_data_end:
        raise ValueError(
            f"FCS DATA end offset disagrees between HEADER ({header_data_end}) "
            f"and $ENDDATA ({text_data_end})."
        )
    data_start = header_data_start or text_data_start
    data_end = header_data_end or text_data_end

    if parsed_supplemental_offsets is not None and data_start > 0:
        ss, se = parsed_supplemental_offsets
        resolved_end = data_end if data_end > 0 else len(raw) - 1
        if not (se < data_start or ss > resolved_end):
            raise ValueError("FCS supplemental TEXT overlaps the resolved DATA segment.")

    next_data = _meta_offset("$NEXTDATA", 0)
    if next_data:
        raise ValueError(
            "This FCS file contains multiple data sets ($NEXTDATA is non-zero). "
            "vFlow currently reads one data set per file and refuses to ignore the rest."
        )

    if data_start <= 0 or data_start >= len(raw):
        raise ValueError(f"Invalid or missing FCS DATA start offset: {data_start}")
    if data_end > 0:
        if data_end < data_start or data_end > len(raw):
            raise ValueError(f"Invalid FCS DATA end offset: {data_end}")
        if data_end == len(raw):
            # Compatibility: FlowJo TextToFCS v1.3 writes the DATA end as an
            # exclusive one-past-EOF offset (and mirrors it in HEADER and
            # $ENDDATA), whereas FCS defines an inclusive end offset.  Accept
            # exactly this one-byte convention, then let the strict expected
            # payload-length checks below prove that no data are missing or
            # extra.  Values greater than EOF remain rejected.
            data_bytes = raw[data_start:data_end]
            compatibility_fixes.append("exclusive one-past-EOF DATA end normalized")
        else:
            data_bytes = raw[data_start:data_end + 1]
    else:
        data_bytes = raw[data_start:]

    data_type = meta["$DATATYPE"].upper()
    endian = _byte_order(meta)

    bits_per_param = []
    ranges = []
    for i in range(1, n_params + 1):
        for suffix in ("B", "N", "R"):
            key = f"$P{i}{suffix}"
            if key not in meta:
                raise ValueError(f"FCS TEXT segment missing required {key}")
        e_key = f"$P{i}E"
        if e_key not in meta:
            # Compatibility: FlowJo TextToFCS v1.3 can omit $PnE while
            # explicitly declaring the parameter as Linear in $PnD.  In that
            # narrow case there is no ambiguity: FCS linear amplification is
            # equivalent to $PnE=0,0.  Never infer this when $PnD is absent or
            # non-linear.
            display = meta.get(f"$P{i}D", "").strip()
            if display.lower().startswith("linear,") or display.lower() == "linear":
                meta[e_key] = "0,0"
                compatibility_fixes.append(
                    f"$P{i}E missing; inferred 0,0 from $P{i}D=Linear"
                )
            else:
                raise ValueError(f"FCS TEXT segment missing required {e_key}")
        key = f"$P{i}B"
        try:
            width = int(meta[key])
        except ValueError as exc:
            raise ValueError(f"Invalid {key} value {meta[key]!r}") from exc
        if width <= 0 or width > 64:
            raise ValueError(f"Unsupported {key} bit width {width}; expected 1..64")
        try:
            rng_val = int(meta[f"$P{i}R"])
        except ValueError as exc:
            raise ValueError(f"Invalid $P{i}R value {meta[f'$P{i}R']!r}") from exc
        if rng_val <= 0:
            raise ValueError(f"Invalid $P{i}R value {rng_val}")
        if data_type == "I" and rng_val > (1 << width):
            raise ValueError(
                f"$P{i}R={rng_val} cannot fit in the $P{i}B={width}-bit field."
            )
        bits_per_param.append(width)
        ranges.append(rng_val)

    if data_type == "F":
        if any(width != 32 for width in bits_per_param):
            raise ValueError("FCS $DATATYPE/F requires every $PnB to equal 32")
        row_bytes = 4 * n_params
        expected = total_events * row_bytes
        if len(data_bytes) != expected:
            raise ValueError(f"FCS DATA length mismatch: $TOT={total_events} requires {expected} bytes, found {len(data_bytes)}")
        arr = np.frombuffer(data_bytes[:expected], dtype=np.dtype(endian + "f4"), count=total_events * n_params).reshape(total_events, n_params).astype(np.float64)
    elif data_type == "D":
        if any(width != 64 for width in bits_per_param):
            raise ValueError("FCS $DATATYPE/D requires every $PnB to equal 64")
        row_bytes = 8 * n_params
        expected = total_events * row_bytes
        if len(data_bytes) != expected:
            raise ValueError(f"FCS DATA length mismatch: $TOT={total_events} requires {expected} bytes, found {len(data_bytes)}")
        arr = np.frombuffer(data_bytes[:expected], dtype=np.dtype(endian + "f8"), count=total_events * n_params).reshape(total_events, n_params).astype(np.float64)
    elif data_type == "I":
        expected_bits = total_events * sum(bits_per_param)
        expected_bytes = math.ceil(expected_bits / 8)
        if len(data_bytes) != expected_bytes:
            raise ValueError(f"FCS DATA length mismatch: $TOT={total_events} requires {expected_bytes} bytes, found {len(data_bytes)}")
        arr = _unpack_integer_events(data_bytes[:expected_bytes], bits_per_param, total_events, endian)
        # FCS integer fields may contain unused high bits.  $PnR defines the
        # significant range and the standard requires readers to ignore bits
        # above the next power-of-two needed to represent that range.  Mask
        # those bits *before* conversion to float so a wide integer field cannot
        # lose its low bits through IEEE-754 rounding.  Values that are still
        # outside a non-power-of-two $PnR remain malformed and fail closed.
        for i, (rng_val, width) in enumerate(zip(ranges, bits_per_param)):
            significant_bits = max(0, int(rng_val - 1).bit_length())
            if significant_bits < width:
                mask = np.uint64((1 << significant_bits) - 1) if significant_bits else np.uint64(0)
                original = arr[:, i].copy()
                arr[:, i] = np.bitwise_and(arr[:, i], mask)
                if np.any(original != arr[:, i]):
                    compatibility_fixes.append(
                        f"$P{i+1} unused integer high bits masked according to $P{i+1}R"
                    )
            invalid = arr[:, i] >= np.uint64(rng_val)
            if np.any(invalid):
                first = int(np.flatnonzero(invalid)[0])
                raise ValueError(
                    f"FCS integer value {int(arr[first, i])} for parameter {i+1} "
                    f"is outside $P{i+1}R={rng_val} after unused-bit masking "
                    f"(valid range 0..{rng_val-1})."
                )
            # vFlow's downstream numeric model is float64.  Reject integer
            # ranges that can contain values not exactly representable there
            # rather than silently rounding event measurements.
            if rng_val > (1 << 53):
                raise ValueError(
                    f"$P{i+1}R={rng_val} exceeds vFlow's exact float64 integer "
                    "precision limit (2^53); refusing lossy conversion."
                )
        arr = arr.astype(np.float64)
    else:
        raise ValueError(f"Unsupported FCS $DATATYPE: {data_type!r}")

    # Convert stored channel values to FCS scale values.  Integer logarithmic
    # parameters use $PnE; linear parameters with acquisition gain use $PnG.
    # F/D parameters are required to have $PnE/0,0/ but may still carry gain.
    for i in range(n_params):
        pne = meta[f"$P{i+1}E"]
        parts = pne.split(",")
        if len(parts) != 2:
            raise ValueError(f"Malformed $P{i+1}E value {pne!r}")
        try:
            f1, f2 = (float(parts[0]), float(parts[1]))
        except ValueError as exc:
            raise ValueError(f"Malformed $P{i+1}E value {pne!r}") from exc
        if not (math.isfinite(f1) and math.isfinite(f2)) or f1 < 0 or f2 < 0:
            raise ValueError(f"Invalid $P{i+1}E value {pne!r}")
        if f1 == 0.0 and f2 != 0.0:
            raise ValueError(
                f"Invalid linear $P{i+1}E value {pne!r}; linear parameters require 0,0."
            )
        if data_type in ("F", "D") and (f1 != 0.0 or f2 != 0.0):
            raise ValueError(
                f"$DATATYPE/{data_type}/ requires $P{i+1}E/0,0/."
            )
        try:
            gain = float(meta.get(f"$P{i+1}G", "1"))
        except ValueError as exc:
            raise ValueError(f"Invalid $P{i+1}G value {meta.get(f'$P{i+1}G')!r}") from exc
        if not math.isfinite(gain) or gain <= 0:
            raise ValueError(f"$P{i+1}G must be finite and > 0")
        if f1 > 0.0:
            if abs(gain - 1.0) > 1e-12:
                raise ValueError(
                    f"$P{i+1}G={gain} cannot be combined with logarithmic $P{i+1}E={pne}."
                )
            # Widely encountered legacy f2=0 is handled as f2=1 as recommended
            # by FCS 3.1 even though writers should not create it.
            f2_eff = f2 if f2 != 0.0 else 1.0
            arr[:, i] = f2_eff * (10.0 ** (f1 * arr[:, i] / float(ranges[i])))
        elif abs(gain - 1.0) > 1e-12:
            arr[:, i] = arr[:, i] / gain

    # TIME is stored in integer/floating steps; expose seconds when $TIMESTEP
    # identifies a TIME parameter.
    time_indices = [
        i for i in range(n_params)
        if meta.get(f"$P{i+1}N", "").strip().upper() == "TIME"
    ]
    if time_indices:
        if "$TIMESTEP" not in meta:
            if version == "FCS3.1":
                raise ValueError("FCS TIME parameter is present but required $TIMESTEP is missing.")
        else:
            try:
                timestep = float(meta["$TIMESTEP"])
            except ValueError as exc:
                raise ValueError(f"Invalid $TIMESTEP value {meta['$TIMESTEP']!r}") from exc
            if not math.isfinite(timestep) or timestep <= 0:
                raise ValueError("$TIMESTEP must be finite and > 0 seconds.")
            for i in time_indices:
                arr[:, i] *= timestep

    df = pd.DataFrame(arr, columns=channels)
    df.attrs["fcs_version"] = version
    df.attrs["fcs_metadata"] = dict(meta)
    df.attrs["fcs_ambiguous_channel_names"] = tuple(ambiguous_channel_names)
    if ambiguous_channel_names:
        compatibility_fixes.append(
            "duplicate FCS channel/stain labels were suffixed; automatic multi-file "
            "matching is disabled for those ambiguous channels"
        )
    # Compensation metadata changed names across supported FCS generations:
    # FCS 2.x used $DFCiTOj terms, FCS 3.0 introduced $COMP, and FCS 3.1
    # standardized $SPILLOVER.  $SPILL is also accepted as a common exporter
    # synonym for warning purposes.  vFlow intentionally does not apply any of
    # these matrices automatically, but it must never omit the safety warning.
    compensation_keys = tuple(
        key for key in meta
        if key.upper() in {"$SPILLOVER", "$SPILL", "$COMP"}
        or re.fullmatch(r"\$DFC\d+TO\d+", key.upper())
    )
    # Neutral provenance marker: the keyword tells us compensation metadata is
    # present, but not whether the numeric DATA segment is raw, already
    # compensated by acquisition electronics/software, or intended for later
    # compensation.  vFlow therefore warns without asserting compensation state.
    df.attrs["fcs_compensation_metadata_present"] = bool(compensation_keys)
    # Backward-compatible alias retained for older internal callers/checkpoints.
    df.attrs["fcs_compensation_unapplied"] = bool(compensation_keys)
    df.attrs["fcs_compensation_metadata_keys"] = compensation_keys
    # Backward-compatible marker retained for existing callers/tests that care
    # specifically about a spillover keyword.
    df.attrs["fcs_spillover_unapplied"] = any(
        key.upper() in {"$SPILLOVER", "$SPILL"} for key in compensation_keys
    )
    df.attrs["fcs_compatibility_fixes"] = tuple(compatibility_fixes)
    return df, meta
