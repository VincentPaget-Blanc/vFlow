# Real Gallios LMD regression corpus

The 14 original `.LMD` files come from Tyler Smith's Bioconductor
`flowPloidyData` experiment-data package, licensed under GPL-3. The accompanying
full GPL-3 license is included. Files are redistributed without modification.

- Package: https://bioconductor.org/packages/flowPloidyData/
- Source: https://github.com/bioconductor-source/flowPloidyData
- Source commit: `8099dbbcdfea894d0ace23b2b65f94c04132d622`
- Vignette: https://bioconductor.org/packages/release/data/experiment/vignettes/flowPloidyData/inst/doc/flowPloidyData.html

`reference_values.json` was generated independently with FlowIO 1.4.0, reading
the chained high-resolution FCS3.0 member. It freezes event counts, channel
order, source checksums, and exact complete-table/per-column checksums. The
checksums use little-endian float64 with no acquisition transforms; those
modern members have unit gain, linear scale, and no TIME step. The legacy
FCS2.0 display representation has different compressed values and is not
substituted for the high-resolution event measurements.

These files establish tested Gallios LMD coverage, not every Beckman format,
every instrument, or any MQD decoder acceptance.
