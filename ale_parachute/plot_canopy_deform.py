#!/usr/bin/env python3
"""Render canopy deformation frames from the structure VTK states.

Every ``state_*_structure.vtk`` / ``final_structure.vtk`` produced by
``run_parachute.py`` is parsed here (no VTK library needed) and drawn as

* left  : side view  (radial distance r = sqrt(x^2 + z^2) vs height y)
* right : top view   (x vs z)

The triangles are filled with a colour that encodes height, so a canopy that
is still folded / only partly inflated is immediately visible.  The suspension
lines (VTK type 3) are drawn as thin grey segments.

Usage
-----
    python3 plot_canopy_deform.py --outdir out/T4a_eb005_vent04_60ms
"""

from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection


def read_structure_vtk(path):
    with open(path) as fh:
        lines = fh.readlines()
    i = 0
    n = len(lines)
    pts = None
    cells = []
    types = []
    while i < n:
        tok = lines[i].split()
        if not tok:
            i += 1
            continue
        if tok[0] == "POINTS":
            npnt = int(tok[1])
            pts = np.loadtxt(lines[i + 1:i + 1 + npnt])
            i += 1 + npnt
            continue
        if tok[0] == "CELLS":
            nc = int(tok[1])
            for k in range(nc):
                vals = [int(v) for v in lines[i + 1 + k].split()]
                cells.append(vals[1:])
            i += 1 + nc
            continue
        if tok[0] == "CELL_TYPES":
            nc = int(tok[1])
            types = np.array([int(v) for v in lines[i + 1:i + 1 + nc]])
            i += 1 + nc
            continue
        i += 1
    return np.asarray(pts, float), cells, types


def frame_files(outdir):
    files = sorted(glob.glob(os.path.join(outdir, "state_*structure.vtk")))
    final = os.path.join(outdir, "final_structure.vtk")
    if os.path.exists(final):
        files.append(final)
    out = []
    for f in files:
        base = os.path.basename(f)
        m = re.search(r"state_\s*([0-9.]+)_structure", base)
        if m:
            out.append((float(m.group(1)), f"t={float(m.group(1)):.3f}", f))
        elif base.startswith("final"):
            out.append((1e9, "final", f))
    out.sort(key=lambda r: r[0])
    return [(lab, f) for _, lab, f in out]


def metrics(x, cells, types):
    tri = np.array([c for c, t in zip(cells, types) if t == 5], dtype=int)
    nodes = np.unique(tri)
    r = np.linalg.norm(x[nodes][:, [0, 2]], axis=1)
    y = x[nodes, 1]
    y0 = np.percentile(y, 1)
    ymax = np.percentile(y, 99.5)
    h = ymax - y0
    R = np.percentile(r, 99.5)
    rim = np.abs(y - ymax) < 0.02 * max(h, 1e-9)
    vent = float(np.median(r[rim])) if rim.any() else 0.0
    return dict(vent=vent, R=R, h=h, ymax=ymax, y0=y0, ntri=tri.shape[0])


def draw(ax_side, ax_top, x, cells, types, title):
    tri = np.array([c for c, t in zip(cells, types) if t == 5], dtype=int)
    lines = [c for c, t in zip(cells, types) if t == 3]
    r = np.linalg.norm(x[:, [0, 2]], axis=1)
    y = x[:, 1]
    cnode = np.unique(tri)
    ylo, yhi = np.percentile(y[cnode], [0.5, 99.5])
    span = max(yhi - ylo, 1e-6)
    # ---- side view: filled triangles coloured by height
    p = np.stack([r, y], axis=1)
    polys = p[tri]
    fc = plt.cm.viridis((y[tri].mean(axis=1) - ylo) / span)
    pc = PolyCollection(polys, facecolors=fc, edgecolors="none", alpha=0.85)
    ax_side.add_collection(pc)
    if lines:
        seg = np.stack([p[np.array(lines)[:, 0]], p[np.array(lines)[:, 1]]], axis=1)
        ax_side.add_collection(LineCollection(seg, colors="#888888", linewidths=0.4))
    # ---- top view: the same triangles projected on x-z
    q = x[:, [0, 2]]
    polys2 = q[tri]
    fc2 = plt.cm.viridis((y[tri].mean(axis=1) - ylo) / span)
    ax_top.add_collection(PolyCollection(polys2, facecolors=fc2,
                                         edgecolors="none", alpha=0.85))
    R = max(np.percentile(r[cnode], 99.5), 1e-3)
    lim = 1.15 * R
    ax_side.set_xlim(-0.02 * lim, lim)
    ax_side.set_ylim(ylo - 0.15 * span, yhi + 0.15 * span)
    ax_top.set_xlim(-lim, lim)
    ax_top.set_ylim(-lim, lim)
    ax_side.set_aspect("equal", adjustable="box")
    ax_top.set_aspect("equal", adjustable="box")
    ax_side.set_xlabel("r = sqrt(x^2+z^2)  [m]")
    ax_side.set_ylabel("y  [m]")
    ax_top.set_xlabel("x  [m]")
    ax_top.set_ylabel("z  [m]")
    ax_side.set_title(f"{title}  side view", fontsize=9)
    ax_top.set_title(f"{title}  top view", fontsize=9)
    ax_side.grid(alpha=0.25, lw=0.4)
    ax_top.grid(alpha=0.25, lw=0.4)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--max-frames", type=int, default=7)
    args = p.parse_args(argv)

    frames = frame_files(args.outdir)
    if not frames:
        raise SystemExit(f"no structure VTK in {args.outdir}")
    if len(frames) > args.max_frames:
        idx = np.linspace(0, len(frames) - 1, args.max_frames).round().astype(int)
        frames = [frames[k] for k in idx]

    nrow = len(frames)
    fig, axes = plt.subplots(nrow, 2, figsize=(7.2, 3.1 * nrow),
                             constrained_layout=True)
    if nrow == 1:
        axes = np.array([axes])
    for k, (label, path) in enumerate(frames):
        x, cells, types = read_structure_vtk(path)
        mt = metrics(x, cells, types)
        draw(axes[k, 0], axes[k, 1], x, cells, types, label)
        axes[k, 0].text(0.02, 0.98,
                        f"vent r={mt['vent']:.3f} m\nh={mt['h']:.3f} m  "
                        f"R={mt['R']:.3f} m  h/R={mt['h']/max(mt['R'],1e-9):.2f}",
                        transform=axes[k, 0].transAxes, va="top", fontsize=7,
                        bbox=dict(fc="white", alpha=0.7, ec="none"))
        print(f"{label:>16s}  vent_r={mt['vent']:.4f}  R={mt['R']:.4f}  "
              f"h={mt['h']:.4f}  h/R={mt['h']/max(mt['R'],1e-9):.3f}")

    name = args.name or os.path.basename(os.path.normpath(args.outdir))
    out = os.path.join(args.outdir, f"canopy_deform_{name}.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
