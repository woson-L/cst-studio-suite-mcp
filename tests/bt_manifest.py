# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Build the run manifest for the BT-20260919-OPT1 antenna optimisation."""
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")


def stats(path):
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
        pts.append((f, vals[0] if len(vals) == 1 else
                    20 * math.log10(max(1e-15, math.hypot(vals[0], vals[1])))))
    band = [(f, v) for f, v in pts if 2.40 <= f <= 2.48]
    if not band:
        return None
    w = max(band, key=lambda t: t[1])
    b = min(pts, key=lambda t: t[1])
    span = [f for f, v in pts if v <= -10]
    return {"worst_db": round(w[1], 4), "worst_ghz": round(w[0], 4),
            "best_db": round(b[1], 3), "best_ghz": round(b[0], 4),
            "minus10_span": [round(min(span), 4), round(max(span), 4)] if span else None,
            "pass": w[1] <= -10}


order = [
    ("s11_baseline_delivered.txt", "baseline: project exactly as delivered"),
    ("s11_FX22.5.txt", "full plate, feed moved to x=22.5 (first resonance found)"),
    ("s11_LT5.5_FX22.5.txt", "plate trimmed to x[5.5,25]"),
    ("s11_LT9.0_FX22.5.txt", "plate trimmed to x[9,25]"),
    ("s11_LT7.85_FX22.5.txt", "plate trimmed to x[7.85,25]"),
    ("s11_LT7.55_FX22.5.txt", "plate trimmed to x[7.55,25] - first PASS"),
    ("s11_LT7.55_FX23.0.txt", "feed x=23.0 (too close to the short, degrades)"),
    ("s11_LT7.55_FX22.0.txt", "feed x=22.0"),
    ("s11_LT7.55_FX21.5.txt", "feed x=21.5"),
    ("s11_LT7.75_FX22.0.txt", "feed x=22.0, trim 7.75"),
    ("s11_LT7.3_FX21.5.txt", "feed x=21.5, trim 7.3"),
    ("s11_LT7.1_FX21.5.txt", "feed x=21.5, trim 7.1"),
    ("S11_FINAL_LT7.0_FX21.5.txt", "FINAL  feed x=21.5, trim 7.0"),
]

history = []
for name, note in order:
    p = RUN / name
    if not p.is_file():
        continue
    st = stats(p)
    if st:
        history.append({"case": name.replace("s11_", "").replace(".txt", ""),
                        "note": note, **st})

final = history[-1] if history else {}
manifest = {
    "task": "optimise the onboard antenna of BT-20260919 to S11 <= -10 dB over 2.40-2.48 GHz",
    "source_project": r"C:\CST_MCP_workspace\source\BT-20260919.cst",
    "working_project": str(RUN / "BT-20260919-OPT1.cst"),
    "working_companion_dir": str(RUN / "BT-20260919-OPT1"),
    "units": {"geometry": "mm", "frequency": "GHz", "impedance": "ohm"},
    "fixed_by_user_and_respected": {
        "substrate": "antenna:substrate  FR-4 (lossy)  x[0,25] y[90,100] z[0.035,0.965]  UNCHANGED",
        "ground": "component1:mainpcb  Copper (annealed)  100x100x1  UNCHANGED",
        "boundary_conditions": "UNCHANGED",
        "solver": "HF Time Domain, band 0-3 GHz  UNCHANGED",
        "mesh_settings": "UNCHANGED",
        "field_monitors": "none added  UNCHANGED",
        "port": "discrete port 1, 50 ohm, translated along global x only",
    },
    "geometry_before": {
        "antenna:antenna": {"material": "Copper (annealed)",
                            "bbox": {"x": [0, 25], "y": [90.5, 100], "z": [0, 0.035]},
                            "volume_mm3": 8.3125},
        "port_1": "midpoint of antenna:antenna edge 29 -> midpoint of mainpcb edge 42, "
                  "i.e. (12.5, 90.5, 0) -> (12.5, 90, 0) across the 0.5 mm feed gap",
    },
    "geometry_after": {
        "antenna:antenna": {"material": "Copper (annealed)",
                            "bbox": {"x": [7.0, 25], "y": [90.5, 100], "z": [0, 0.035]},
                            "volume_mm3": 5.985},
        "shape": "rectangular plate x[7,25] y[90.5,100] z[0,0.035]; it shares its x=25 face "
                 "with component1:mainpcb (the shorting edge); fed 3.5 mm from that short",
        "port_1": "(21.5, 90.5, 0) -> (21.5, 90, 0)",
    },
    "final_parameters": {"LT": 7.0, "FX": 21.5},
    "parameter_meaning": {
        "LT": "x of the plate's open end (plate length = 25 - LT = 18 mm)",
        "FX": "x of the feed (distance from the shorting edge = 25 - FX = 3.5 mm)",
    },
    "final_result": final,
    "criterion": {"band_ghz": [2.40, 2.48], "s11_max_db": -10.0,
                  "inclusive": True, "verdict": "PASS" if final.get("pass") else "FAIL"},
    "status": "validated_pass" if final.get("pass") else "validated_fail",
    "iteration_history": history,
    "evidence": {
        "s11_raw": "S11_FINAL_LT7.0_FX21.5.txt",
        "touchstone": "BT-20260919-OPT1_final.s1p.s1p",
        "all_iterations": [h["case"] for h in history],
    },
}
out = RUN / "OPT1_manifest.json"
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"written {out}\n")
for h in history:
    print(f"  {h['case']:<28} worst {h['worst_db']:>8.2f} dB @ {h['worst_ghz']:.4f}"
          f"  best {h['best_db']:>7.2f} @ {h['best_ghz']:.4f}"
          f"  {'PASS' if h['pass'] else 'fail'}")
