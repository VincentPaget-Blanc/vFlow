#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, csv, sys

root = Path(__file__).resolve().parent
checks = json.loads((root/"truth"/"file_checksums.json").read_text())

bad = []
for rel, expected in checks.items():
    p = root/rel
    if not p.exists():
        bad.append((rel,"MISSING"))
        continue
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    if h.hexdigest()!=expected:
        bad.append((rel,"SHA256_MISMATCH"))

if bad:
    print("FAIL")
    for x in bad: print(" -",x)
    sys.exit(1)
print(f"PASS: {len(checks)} frozen files match SHA-256 manifest.")
