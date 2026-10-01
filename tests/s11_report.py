# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Summarise CST 1D S11 ASCII exports (frequency GHz + |S11| dB).

usage: python s11_report.py FILE [FILE ...]
"""
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(path):
    pts = []
    for line in Path(path).read_text(errors="replace").splitlines():
        s = line.strip()
        if not s or s[0] not in "-+.0123456789":
            continue
        parts = s.split()
        try:
            f = float(parts[0])
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            continue
        if not vals:
            continue
        if len(vals) >= 2:                      # re, im
            m = math.hypot(vals[0], vals[1])
            db = 20 * math.log10(m) if m > 1e-15 else -300.0
        else:                                   # already dB
            db = vals[0]
        pts.append((f, db))
    return pts


def report(path):
    pts = load(path)
    if not pts:
        print(f"{Path(path).name}: no data")
        return None
    band = [(f, v) for f, v in pts if 2.40 <= f <= 2.48]
    print(f"== {Path(path).name}  ({len(pts)} pts, {pts[0][0]:.3f}-{pts[-1][0]:.3f} GHz)")
    if band:
        w = max(band, key=lambda t: t[1])
        verdict = "PASS" if w[1] <= -10 else "FAIL"
        print(f"   worst 2.40-2.48 : {w[1]:8.2f} dB @ {w[0]:.4f} GHz   {verdict}")
    b = min(pts, key=lambda t: t[1])
    print(f"   best overall    : {b[1]:8.2f} dB @ {b[0]:.4f} GHz")
    span = [f for f, v in pts if v <= -10]
    if span:
        print(f"   <= -10 dB from  : {min(span):.4f} .. {max(span):.4f} GHz")
    for f in (2.30, 2.40, 2.44, 2.48, 2.60, 2.71, 2.80, 3.00):
        if pts[0][0] <= f <= pts[-1][0]:
            print(f"     {f:.2f} GHz -> {min(pts, key=lambda t: abs(t[0]-f))[1]:7.2f} dB")
    return band


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
        print()
