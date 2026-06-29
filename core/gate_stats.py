"""Gate statistics aggregation helpers."""

from __future__ import annotations


def stats_from_regions(regions: dict, total: int) -> dict:
    """Build the legacy stats dict for a single file from region masks."""
    return {
        "stats": {
            rname: {
                "count": (count := int(mask.sum())),
                "pct": count / total * 100 if total else 0.0,
            }
            for rname, mask in regions.items()
        },
        "total": total,
    }


def merge_gate_stats(gate_data: dict) -> dict:
    """Merge per-file stats from a {path: {stats, total}} mapping."""
    if not gate_data:
        return {}
    first_stats = next(iter(gate_data.values()))["stats"]
    region_names = list(first_stats.keys())
    counts = {region: 0 for region in region_names}
    total = 0
    for info in gate_data.values():
        total += info["total"]
        for region in region_names:
            counts[region] += info["stats"].get(region, {}).get("count", 0)
    return {
        "stats": {
            region: {
                "count": counts[region],
                "pct": counts[region] / total * 100 if total else 0.0,
            }
            for region in region_names
        },
        "total": total,
    }

