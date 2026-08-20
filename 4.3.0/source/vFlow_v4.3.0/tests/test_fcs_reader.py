import numpy as np
import pytest
from vflow.core.fcs_reader import read_fcs


def _escape(value: str, delim: str) -> str:
    return value.replace(delim, delim * 2)


def _write_fcs(tmp_path, *, events, bits, endian="<", stains=None, extra_meta=None, version="FCS3.1"):
    path = tmp_path / "synthetic.fcs"
    n_events = len(events); n_params = len(bits); delim = "/"
    order = "1,2,3,4" if endian == "<" else "4,3,2,1"
    meta = {
        "$MODE":"L", "$DATATYPE":"I", "$PAR":str(n_params),
        "$TOT":str(n_events), "$BYTEORD":order,
        "$BEGINANALYSIS":"0", "$ENDANALYSIS":"0",
        "$BEGINSTEXT":"0", "$ENDSTEXT":"0", "$NEXTDATA":"0",
    }
    for i,width in enumerate(bits,1):
        meta[f"$P{i}B"]=str(width); meta[f"$P{i}R"]=str(1 << min(width,20)); meta[f"$P{i}N"]=f"P{i}"; meta[f"$P{i}E"]="0,0"
        if stains: meta[f"$P{i}S"]=stains[i-1]
    if extra_meta: meta.update(extra_meta)

    def text_bytes(begin,end):
        m=dict(meta); m["$BEGINDATA"]=str(begin); m["$ENDDATA"]=str(end)
        body=delim+delim.join(item for kv in m.items() for item in (_escape(str(kv[0]),delim),_escape(str(kv[1]),delim)))+delim
        return body.encode("utf-8")

    if all(w in (8,16,32,64) for w in bits):
        fields=[(f"f{i}",np.dtype(endian+f"u{w//8}")) for i,w in enumerate(bits)]
        arr=np.zeros(n_events,dtype=np.dtype(fields))
        for r,row in enumerate(events):
            for c,val in enumerate(row): arr[f"f{c}"][r]=val
        payload=arr.tobytes()
    else:
        bitorder="little" if endian=="<" else "big"; seq=[]
        for row in events:
            for val,w in zip(row,bits):
                seq.extend(((val>>j)&1 for j in (range(w) if bitorder=="little" else range(w-1,-1,-1))))
        while len(seq)%8: seq.append(0)
        payload=np.packbits(np.array(seq,dtype=np.uint8),bitorder=bitorder).tobytes()

    begin=end=0
    for _ in range(20):
        text=text_bytes(begin,end); nb=58+len(text); ne=nb+len(payload)-1
        if (nb,ne)==(begin,end): break
        begin,end=nb,ne
    text=text_bytes(begin,end)
    header=(f"{version}    {58:>8}{(58+len(text)-1):>8}{begin:>8}{end:>8}{0:>8}{0:>8}").encode("ascii")
    assert len(header)==58
    path.write_bytes(header+text+payload); return path


def test_big_endian_16_bit_integer_values(tmp_path):
    path=_write_fcs(tmp_path,events=[(1,258),(513,1023)],bits=[16,16],endian=">")
    df,_=read_fcs(path); assert df.to_numpy().tolist()==[[1.0,258.0],[513.0,1023.0]]


def test_text_escaped_delimiter_and_duplicate_stain_names_are_handled(tmp_path):
    path=_write_fcs(tmp_path,events=[(1,2,3)],bits=[16,16,16],stains=["A","A","A_1"],extra_meta={"$COM":"value/with/slashes"})
    df,meta=read_fcs(path); assert meta["$COM"]=="value/with/slashes"; assert list(df.columns)==["A","A_1","A_1_1"]
    assert set(df.attrs["fcs_ambiguous_channel_names"]) == {"A", "A_1", "A_1_1"}
    assert any("duplicate FCS channel/stain labels" in item
               for item in df.attrs["fcs_compatibility_fixes"])


def test_tightly_packed_10_bit_integers(tmp_path):
    path=_write_fcs(tmp_path,events=[(1,1023),(513,7)],bits=[10,10])
    df,_=read_fcs(path); assert df.to_numpy().tolist()==[[1.0,1023.0],[513.0,7.0]]


def test_truncated_data_is_rejected(tmp_path):
    path=_write_fcs(tmp_path,events=[(1,2),(3,4)],bits=[16,16]); path.write_bytes(path.read_bytes()[:-2])
    with pytest.raises(ValueError,match="DATA end|truncated"): read_fcs(path)


def test_invalid_byte_order_is_rejected(tmp_path):
    path=_write_fcs(tmp_path,events=[(1,2)],bits=[16,16]); path.write_bytes(path.read_bytes().replace(b"1,2,3,4",b"2,1,4,3"))
    with pytest.raises(ValueError,match="BYTEORD"): read_fcs(path)


def test_linear_gain_is_converted_to_scale_values(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(80,), (160,)], bits=[16],
        extra_meta={"$P1G": "8"},
    )
    df, _ = read_fcs(path)
    assert df.iloc[:, 0].tolist() == [10.0, 20.0]


def test_time_parameter_is_returned_in_seconds(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(0,), (100,)], bits=[16],
        extra_meta={"$P1N": "TIME", "$TIMESTEP": "0.01"},
    )
    df, _ = read_fcs(path)
    assert df.iloc[:, 0].tolist() == [0.0, 1.0]


def test_utf8_stain_name_is_preserved(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(1,)], bits=[16], stains=["CD45 α"],
    )
    df, _ = read_fcs(path)
    assert list(df.columns) == ["CD45 α"]


def test_header_text_data_offset_mismatch_is_rejected(tmp_path):
    path = _write_fcs(tmp_path, events=[(1,)], bits=[16])
    raw = bytearray(path.read_bytes())
    old = int(bytes(raw[26:34]).decode("ascii"))
    raw[26:34] = f"{old + 1:>8}".encode("ascii")
    path.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="disagrees between HEADER"):
        read_fcs(path)


def test_multiple_fcs_datasets_are_not_silently_ignored(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(1,)], bits=[16], extra_meta={"$NEXTDATA": "1234"}
    )
    with pytest.raises(ValueError, match="multiple data sets"):
        read_fcs(path)


def test_log_amplification_cannot_be_combined_with_nonunit_gain(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(100,)], bits=[16],
        extra_meta={"$P1E": "4,1", "$P1G": "2"},
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        read_fcs(path)


def test_spillover_matrix_is_flagged_as_unapplied(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(10, 20)], bits=[16, 16],
        extra_meta={"$SPILLOVER": "2,P1,P2,1,0.1,0.2,1"},
    )
    df, meta = read_fcs(path)
    assert "$SPILLOVER" in meta
    assert df.attrs["fcs_spillover_unapplied"] is True


def test_no_spillover_matrix_is_not_flagged(tmp_path):
    path = _write_fcs(tmp_path, events=[(10,)], bits=[16])
    df, _ = read_fcs(path)
    assert df.attrs["fcs_spillover_unapplied"] is False


def test_fcs30_comp_metadata_is_flagged_as_unapplied_compensation(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(10, 20)], bits=[16, 16], version="FCS3.0",
        extra_meta={"$COMP": "2,P1,P2,1,0.1,0.2,1"},
    )
    df, meta = read_fcs(path)
    assert "$COMP" in meta
    assert df.attrs["fcs_compensation_metadata_present"] is True
    assert df.attrs["fcs_compensation_unapplied"] is True  # compatibility alias
    assert df.attrs["fcs_compensation_metadata_keys"] == ("$COMP",)
    assert df.attrs["fcs_spillover_unapplied"] is False


def test_fcs20_dfc_metadata_is_flagged_as_unapplied_compensation(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(10, 20)], bits=[16, 16], version="FCS2.0",
        extra_meta={"$DFC1TO2": "0.1"},
    )
    df, _ = read_fcs(path)
    assert df.attrs["fcs_compensation_metadata_present"] is True
    assert df.attrs["fcs_compensation_unapplied"] is True  # compatibility alias
    assert df.attrs["fcs_compensation_metadata_keys"] == ("$DFC1TO2",)


def test_case_insensitive_duplicate_stains_are_disambiguated(tmp_path):
    path = _write_fcs(
        tmp_path, events=[(1, 2)], bits=[16, 16], stains=["CD3", "cd3"]
    )
    df, _ = read_fcs(path)
    assert list(df.columns) == ["CD3", "cd3_1"]
    assert set(df.attrs["fcs_ambiguous_channel_names"]) == {"CD3", "cd3_1"}



def _write_flowjo_texttofcs_float(tmp_path, *, events, include_linear_pnd=True):
    """Write the non-standard-but-common layout emitted by FlowJo TextToFCS v1.3."""
    path = tmp_path / "flowjo_texttofcs.fcs"
    arr = np.asarray(events, dtype=">f4")
    if arr.ndim != 2:
        raise ValueError("events must be a 2-D array")
    n_events, n_params = arr.shape
    payload = arr.tobytes()
    delim = "|"
    text_len = 1024
    text_start = 58
    text_end = text_start + text_len - 1
    data_start = text_end + 1
    # TextToFCS v1.3 uses an exclusive one-past-EOF DATA end offset.
    data_end = data_start + len(payload)
    meta = {
        "$TOT": str(n_events), "$PAR": str(n_params),
        "$BYTEORD": "4,3,2,1", "$DATATYPE": "F", "$MODE": "L",
        "$BEGINDATA": str(data_start), "$ENDDATA": str(data_end),
        "$BEGINANALYSIS": "0", "$ENDANALYSIS": "0",
        "$BEGINSTEXT": str(text_start), "$ENDSTEXT": str(data_start),
        "$NEXTDATA": "0", "$CYT": "FlowJo TextToFCS v 1.3",
    }
    for i in range(1, n_params + 1):
        meta[f"$P{i}S"] = f"Marker{i}"
        meta[f"$P{i}N"] = f"Parameter_{i}"
        meta[f"$P{i}G"] = "1"
        meta[f"$P{i}R"] = "1000000"
        meta[f"$P{i}B"] = "32"
        if include_linear_pnd:
            meta[f"$P{i}D"] = "Linear,0,1000000"
        # Intentionally omit $PnE, matching TextToFCS v1.3 output.
    body = delim + delim.join(str(x) for kv in meta.items() for x in kv) + delim
    encoded = body.encode("ascii")
    if len(encoded) > text_len:
        raise AssertionError("test TEXT payload exceeds fixed segment")
    text = encoded + b" " * (text_len - len(encoded))
    header = (
        f"FCS3.0    {text_start:>8}{text_end:>8}"
        f"{data_start:>8}{data_end:>8}{0:>8}{0:>8}"
    ).encode("ascii")
    assert len(header) == 58
    path.write_bytes(header + text + payload)
    assert len(path.read_bytes()) == data_end
    return path


def test_flowjo_texttofcs_float_compatibility_layout_is_read_exactly(tmp_path):
    expected = np.array([[1.0, 12.5], [2.0, -3.25], [3.0, 99.0]], dtype=float)
    path = _write_flowjo_texttofcs_float(tmp_path, events=expected)
    df, meta = read_fcs(path)
    assert list(df.columns) == ["Marker1", "Marker2"]
    np.testing.assert_array_equal(df.to_numpy(), expected)
    fixes = df.attrs["fcs_compatibility_fixes"]
    assert "TEXT trailing whitespace padding ignored" in fixes
    assert "exclusive one-past-EOF DATA end normalized" in fixes
    assert any("$P1E missing; inferred 0,0" in item for item in fixes)
    assert any("$P2E missing; inferred 0,0" in item for item in fixes)


def test_missing_pne_is_still_rejected_without_explicit_linear_pnd(tmp_path):
    path = _write_flowjo_texttofcs_float(
        tmp_path, events=[[1.0, 2.0]], include_linear_pnd=False
    )
    with pytest.raises(ValueError, match=r"missing required \$P1E"):
        read_fcs(path)


def test_integer_unused_high_bits_are_masked_according_to_pnr(tmp_path):
    path = _write_fcs(
        tmp_path,
        events=[(0xFC05,)],
        bits=[16],
        extra_meta={"$P1R": "1024"},
    )
    df, _ = read_fcs(path)
    assert df.iloc[:, 0].tolist() == [5.0]
    assert any("unused integer high bits masked" in item
               for item in df.attrs["fcs_compatibility_fixes"])


def test_integer_value_still_outside_non_power_of_two_pnr_is_rejected_after_mask(tmp_path):
    path = _write_fcs(
        tmp_path,
        events=[(1023,)],
        bits=[16],
        extra_meta={"$P1R": "1000"},
    )
    with pytest.raises(ValueError, match=r"outside \$P1R=1000 after unused-bit masking"):
        read_fcs(path)


def test_integer_range_beyond_exact_float64_precision_fails_closed(tmp_path):
    path = _write_fcs(
        tmp_path,
        events=[(1,)],
        bits=[64],
        extra_meta={"$P1R": str((1 << 53) + 1)},
    )
    with pytest.raises(ValueError, match="exact float64 integer precision"):
        read_fcs(path)


def test_integer_value_at_pnr_minus_one_is_valid(tmp_path):
    path = _write_fcs(
        tmp_path,
        events=[(999,)],
        bits=[16],
        extra_meta={"$P1R": "1000"},
    )
    df, _ = read_fcs(path)
    assert df.iloc[:, 0].tolist() == [999.0]


def _write_fcs_with_stext(
    tmp_path,
    *,
    events,
    bits,
    supplemental_meta,
    primary_extra_meta=None,
    endian="<",
):
    """Write an FCS3.1 file with a distinct supplemental TEXT segment."""
    path = tmp_path / "synthetic_stext.fcs"
    n_events = len(events)
    n_params = len(bits)
    delim = "/"
    order = "1,2,3,4" if endian == "<" else "4,3,2,1"
    primary = {
        "$MODE": "L",
        "$DATATYPE": "I",
        "$PAR": str(n_params),
        "$TOT": str(n_events),
        "$BYTEORD": order,
        "$BEGINANALYSIS": "0",
        "$ENDANALYSIS": "0",
        "$NEXTDATA": "0",
    }
    for i, width in enumerate(bits, 1):
        primary[f"$P{i}B"] = str(width)
        primary[f"$P{i}R"] = str(1 << min(width, 20))
        primary[f"$P{i}N"] = f"P{i}"
        primary[f"$P{i}E"] = "0,0"
    if primary_extra_meta:
        primary.update(primary_extra_meta)

    def text_bytes(mapping):
        body = (
            delim
            + delim.join(
                item
                for kv in mapping.items()
                for item in (_escape(str(kv[0]), delim), _escape(str(kv[1]), delim))
            )
            + delim
        )
        return body.encode("utf-8")

    fields = [(f"f{i}", np.dtype(endian + f"u{w // 8}")) for i, w in enumerate(bits)]
    if not all(w in (8, 16, 32, 64) for w in bits):
        raise ValueError("test helper currently requires byte-aligned integer widths")
    arr = np.zeros(n_events, dtype=np.dtype(fields))
    for r, row in enumerate(events):
        for c, value in enumerate(row):
            arr[f"f{c}"][r] = value
    payload = arr.tobytes()
    supplemental = text_bytes(supplemental_meta)

    begin_stext = end_stext = begin_data = end_data = 0
    for _ in range(50):
        candidate = dict(primary)
        candidate["$BEGINSTEXT"] = str(begin_stext)
        candidate["$ENDSTEXT"] = str(end_stext)
        candidate["$BEGINDATA"] = str(begin_data)
        candidate["$ENDDATA"] = str(end_data)
        text = text_bytes(candidate)
        new_begin_stext = 58 + len(text)
        new_end_stext = new_begin_stext + len(supplemental) - 1
        new_begin_data = new_end_stext + 1
        new_end_data = new_begin_data + len(payload) - 1
        new_offsets = (new_begin_stext, new_end_stext, new_begin_data, new_end_data)
        if new_offsets == (begin_stext, end_stext, begin_data, end_data):
            break
        begin_stext, end_stext, begin_data, end_data = new_offsets
    else:
        raise AssertionError("FCS offset iteration did not converge")

    candidate = dict(primary)
    candidate["$BEGINSTEXT"] = str(begin_stext)
    candidate["$ENDSTEXT"] = str(end_stext)
    candidate["$BEGINDATA"] = str(begin_data)
    candidate["$ENDDATA"] = str(end_data)
    text = text_bytes(candidate)
    assert 58 + len(text) == begin_stext
    assert begin_stext + len(supplemental) - 1 == end_stext
    assert end_stext + 1 == begin_data
    header = (
        f"FCS3.1    {58:>8}{(58 + len(text) - 1):>8}"
        f"{begin_data:>8}{end_data:>8}{0:>8}{0:>8}"
    ).encode("ascii")
    assert len(header) == 58
    path.write_bytes(header + text + supplemental + payload)
    return path


def test_supplemental_text_gain_is_applied_before_numeric_conversion(tmp_path):
    path = _write_fcs_with_stext(
        tmp_path,
        events=[(80,), (160,)],
        bits=[16],
        supplemental_meta={"$P1G": "8"},
    )
    df, meta = read_fcs(path)
    assert meta["$P1G"] == "8"
    assert df.iloc[:, 0].tolist() == [10.0, 20.0]


def test_supplemental_text_spillover_is_not_silently_ignored(tmp_path):
    path = _write_fcs_with_stext(
        tmp_path,
        events=[(10, 20)],
        bits=[16, 16],
        supplemental_meta={"$SPILLOVER": "2,P1,P2,1,0.1,0.2,1"},
    )
    df, meta = read_fcs(path)
    assert "$SPILLOVER" in meta
    assert df.attrs["fcs_spillover_unapplied"] is True


def test_duplicate_fcs_keyword_between_primary_and_supplemental_text_is_rejected(tmp_path):
    path = _write_fcs_with_stext(
        tmp_path,
        events=[(1,)],
        bits=[16],
        supplemental_meta={"$P1N": "DifferentName"},
    )
    with pytest.raises(ValueError, match="repeated between primary and supplemental"):
        read_fcs(path)


def test_duplicate_fcs_keyword_within_primary_text_is_rejected(tmp_path):
    path = _write_fcs(tmp_path, events=[(1,)], bits=[16], extra_meta={"$COM": "one"})
    raw = path.read_bytes()
    text_start = int(raw[10:18].decode("ascii"))
    text_end = int(raw[18:26].decode("ascii"))
    text = raw[text_start:text_end + 1]
    marker = b"/$COM/one/"
    assert marker in text
    # Replace an equal-length region so all offsets remain valid; duplicate the
    # same keyword with a different value to make last-wins behavior detectable.
    replacement = b"/$COM/one/$COM/two/"
    # Grow TEXT and rebuild offsets through the dedicated helper is simpler than
    # mutating a fixed-offset file; use the parser-level representation below.
    from vflow.core.fcs_reader import _parse_text_segment
    with pytest.raises(ValueError, match="duplicate keyword"):
        _parse_text_segment(replacement.decode("ascii"))


def test_texttofcs_overlapping_stext_quirk_remains_compatible(tmp_path):
    expected = np.array([[1.0, 12.5], [2.0, -3.25], [3.0, 99.0]], dtype=float)
    path = _write_flowjo_texttofcs_float(tmp_path, events=expected)
    df, _ = read_fcs(path)
    np.testing.assert_array_equal(df.to_numpy(), expected)
    # Supplemental-TEXT support must not alter the historical compatibility
    # notice surface for this already-certified exporter quirk.
    assert len(df.attrs["fcs_compatibility_fixes"]) == 4
