# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Final acceptance check for the BT-20260919-OPT1 antenna.

usage: python bt_final_check.py FILE.txt
"""
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

F_LO, F_HI, LIMIT = 2.40, 2.48, -10.0


def load(path):
    pts = []
    for line in Path(path).read_text(errors="replace").splitlines():
        s = line.strip()
        if not s or s[0] not in "-+.0123456789":
            continue
        try:
            parts = s.split()
            f = float(parts[0])
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            continue
        if not vals:
            continue
        db = (vals[0] if len(vals) == 1
              else 20 * math.log10(max(1e-15, math.hypot(vals[0], vals[1]))))
        pts.append((f, db))
    return pts


def main(path):
    pts = load(path)
    band = [(f, v) for f, v in pts if F_LO - 1e-9 <= f <= F_HI + 1e-9]
    print(f"file                : {Path(path).name}")
    print(f"curve               : {len(pts)} pts, {pts[0][0]:.4f}-{pts[-1][0]:.4f} GHz")
    print(f"points in band      : {len(band)}")
    if not band:
        print("NO DATA IN BAND -> needs_validation")
        return 2
    w = max(band, key=lambda t: t[1])
    print(f"worst in 2.40-2.48  : {w[1]:.4f} dB @ {w[0]:.6f} GHz")
    for f in (2.400, 2.420, 2.440, 2.460, 2.480):
        near = min(pts, key=lambda t: abs(t[0] - f))
        print(f"   S11({f:.3f} GHz)   = {near[1]:8.4f} dB")
    span = [f for f, v in pts if v <= LIMIT]
    if span:
        print(f"S11 <= -10 dB span  : {min(span):.4f} .. {max(span):.4f} GHz"
              f"  ({(max(span) - min(span)) * 1000:.1f} MHz)")
    best = min(pts, key=lambda t: t[1])
    print(f"best                : {best[1]:.4f} dB @ {best[0]:.6f} GHz")
    ok = w[1] <= LIMIT
    print(f"CRITERION S11<=-10dB in [{F_LO},{F_HI}] : {'PASS' if ok else 'FAIL'}"
          f"   margin {abs(LIMIT - w[1]):.2f} dB")
    print(f"status              : {'validated_pass' if ok else 'validated_fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
