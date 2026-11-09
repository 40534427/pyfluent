#!/usr/bin/env python3
"""Measure the vent (apex hole) diameter from structure VTK states.

The vent ring nodes are identified in state_0000_structure.vtk as the canopy
nodes whose y equals the maximum y (the apex ring written by mesh.py).
For every state_*_structure.vtk the same node indices are used to compute
the mean ring radius -> vent diameter, plus the maximum projected radius of
all canopy nodes, and their ratio.
"""
import glob
import os
import re
import sys

import numpy as np


def read_points(path):
    """Return (points ndarray (n,3), title) from a legacy ASCII VTK file."""
    pts = []
    title = ""
    with open(path) as fh:
        lines = fh.readlines()
    if len(lines) > 1:
        title = lines[1].strip()
    i = 0
    n = len(lines)
    count = None
    while i < n:
        tok = lines[i].strip()
        m = re.match(r"POINTS\s+(\d+)\s+(\w+)", tok, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            i += 1
            while len(pts) < count and i < n:
                row = lines[i].split()
                if len(row) >= 3:
                    try:
                        pts.append([float(row[0]), float(row[1]), float(row[2])])
                    except ValueError:
                        break
                i += 1
            break
        i += 1
    return np.asarray(pts).reshape(-1, 3), title


def main(results):
    st0 = os.path.join(results, "state_0000_structure.vtk")
    p0, _ = read_points(st0)
    # canopy nodes only: drop trailing suspension-line anchor nodes by using
    # the apex ring = nodes at maximum y (identical to mesh.py construction)
    ymax = p0[:, 1].max()
    ring = np.where(np.isclose(p0[:, 1], ymax, rtol=0.0, atol=1e-7))[0]
    print(f"apex ring nodes: {ring.size} (indices {ring.tolist()})")

    rows = []
    for f in sorted(glob.glob(os.path.join(results, "state_*_structure.vtk"))):
        p, title = read_points(f)
        m = re.search(r"t=\s*([0-9.eE+-]+)", title)
        t = float(m.group(1)) if m else float("nan")
        q = p[ring]
        r = np.hypot(q[:, 0] - q[:, 0].mean(), q[:, 2] - q[:, 2].mean())
        vent_d = 2.0 * float(r.mean())
        r_all = np.hypot(p[:, 0] - p[:, 0].mean(), p[:, 2] - p[:, 2].mean())
        r_max = float(r_all.max())
        rows.append((t, vent_d, r_max, vent_d / (2.0 * r_max) if r_max else 0.0))

    print(f"{'t [s]':>10} {'vent_d [mm]':>12} {'R_max [mm]':>12} {'ratio':>8}")
    for t, vd, rm, ratio in rows:
        print(f"{t:10.4f} {vd * 1e3:12.3f} {rm * 1e3:12.3f} {ratio:8.4f}")
    if rows:
        t, vd, rm, ratio = rows[-1]
        print(f"\nFINAL: t={t:.4f} s  vent diameter = {vd * 1e3:.2f} mm, "
              f"max projected diameter = {2 * rm * 1e3:.2f} mm, "
              f"vent/max = {ratio * 100:.2f} %")
        pk = max(rows, key=lambda r: r[2])
        print(f"PEAK R: t={pk[0]:.4f} s  R_max = {pk[2] * 1e3:.1f} mm, "
              f"vent/max = {pk[3] * 100:.2f} %")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/workspace/run_150ms_final/results")
