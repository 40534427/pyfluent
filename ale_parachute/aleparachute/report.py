"""Automatic calculation-report generator for the ALE parachute solver.

After a run (or on an existing ``outdir``), :func:`generate_report` produces a
self-contained HTML report plus the underlying data files (``.dat`` tables,
PNG figures, and an MP4 animation) that the report references.

Coverage (matches the user requirements):

a) Calculation conditions  - domain, mesh, solver settings, material cards
b) Line-force / confluence-force curves (with .dat raw data)
c) Canopy shape evolution, velocity / pressure fields, canopy stress / strain
   contours (with a video animation as backup)
d) CPU model, physical cores, base frequency, wall-clock time

The module is importable and also runnable as ``python -m aleparachute.report
--outdir ...`` for post-hoc generation on an existing result directory.
"""

from __future__ import annotations

import csv
import glob
import html
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation


# ---------------------------------------------------------------------------
# CPU information
# ---------------------------------------------------------------------------
def get_cpu_info() -> Dict[str, str]:
    """Return CPU model, physical cores, base frequency as strings."""
    info = {"model": platform.processor() or "unknown",
            "physical_cores": "?", "base_frequency_ghz": "?",
            "logical_cores": "?"}
    try:
        import psutil
        phy = psutil.cpu_count(logical=False)
        log = psutil.cpu_count(logical=True)
        if phy:
            info["physical_cores"] = str(phy)
        if log:
            info["logical_cores"] = str(log)
        freq = psutil.cpu_freq()
        if freq and getattr(freq, "max", 0):
            info["base_frequency_ghz"] = f"{freq.max / 1000.0:.2f}"
        elif freq:
            info["base_frequency_ghz"] = f"{freq.current / 1000.0:.2f}"
    except Exception:
        pass
    # model name from /proc/cpuinfo (Linux) or system_profiler (macOS)
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    info["model"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    if info["model"] in ("", "unknown", "x86_64"):
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"],
                                          stderr=subprocess.DEVNULL).decode().strip()
            if out:
                info["model"] = out
        except Exception:
            pass
    return info


# ---------------------------------------------------------------------------
# VTK reader (ASCII unstructured grid, no external dependency)
# ---------------------------------------------------------------------------
@dataclass
class VtkDataSet:
    points: np.ndarray
    cells: List[List[int]]
    cell_types: np.ndarray
    cell_data: Dict[str, np.ndarray] = field(default_factory=dict)
    point_data: Dict[str, np.ndarray] = field(default_factory=dict)
    title: str = ""


def read_vtk(path: str) -> VtkDataSet:
    """Read a legacy ASCII VTK unstructured-grid file written by vtkio."""
    with open(path) as fh:
        lines = fh.readlines()
    ds = VtkDataSet(points=np.zeros((0, 3)), cells=[],
                    cell_types=np.zeros(0, int))
    i = 0
    n = len(lines)
    title = ""
    while i < n:
        tok = lines[i].strip()
        if tok.startswith("# vtk"):
            i += 1
            if i < n:
                title = lines[i].strip()
            i += 1
            continue
        if tok.upper() == "ASCII":
            i += 1
            continue
        if tok.upper().startswith("DATASET"):
            i += 1
            continue
        m = re.match(r"POINTS\s+(\d+)\s+(\w+)", tok, re.IGNORECASE)
        if m:
            np_ = int(m.group(1))
            i += 1
            pts = []
            while len(pts) < np_ and i < n:
                row = lines[i].split()
                pts.append([float(row[0]), float(row[1]), float(row[2])])
                i += 1
            ds.points = np.array(pts)
            continue
        m = re.match(r"CELLS\s+(\d+)\s+(\d+)", tok, re.IGNORECASE)
        if m:
            nc = int(m.group(1))
            i += 1
            cells = []
            while len(cells) < nc and i < n:
                row = lines[i].split()
                nv = int(row[0])
                cells.append([int(row[j + 1]) for j in range(nv)])
                i += 1
            ds.cells = cells
            continue
        m = re.match(r"CELL_TYPES\s+(\d+)", tok, re.IGNORECASE)
        if m:
            nc = int(m.group(1))
            i += 1
            types = []
            while len(types) < nc and i < n:
                types.append(int(lines[i].strip()))
                i += 1
            ds.cell_types = np.array(types)
            continue
        if tok.upper().startswith("CELL_DATA"):
            i += 1
            while i < n and not lines[i].strip().upper().startswith("POINT_DATA") \
                    and not lines[i].strip() == "":
                line = lines[i].strip()
                ms = re.match(r"SCALARS\s+(\S+)\s+(\w+)\s+(\d+)", line, re.IGNORECASE)
                mv = re.match(r"VECTORS\s+(\S+)\s+(\w+)", line, re.IGNORECASE)
                if ms:
                    name = ms.group(1)
                    i += 2  # skip LOOKUP_TABLE line
                    vals = []
                    while len(vals) < len(ds.cells) and i < n:
                        vals.append(float(lines[i].strip()))
                        i += 1
                    ds.cell_data[name] = np.array(vals)
                    continue
                if mv:
                    name = mv.group(1)
                    i += 1
                    vals = []
                    while len(vals) < len(ds.cells) and i < n:
                        row = lines[i].split()
                        vals.append([float(row[0]), float(row[1]), float(row[2])])
                        i += 1
                    ds.cell_data[name] = np.array(vals)
                    continue
                i += 1
            continue
        if tok.upper().startswith("POINT_DATA"):
            i += 1
            while i < n and lines[i].strip() != "":
                line = lines[i].strip()
                ms = re.match(r"SCALARS\s+(\S+)\s+(\w+)\s+(\d+)", line, re.IGNORECASE)
                mv = re.match(r"VECTORS\s+(\S+)\s+(\w+)", line, re.IGNORECASE)
                if ms:
                    name = ms.group(1)
                    i += 2
                    vals = []
                    while len(vals) < len(ds.points) and i < n:
                        vals.append(float(lines[i].strip()))
                        i += 1
                    ds.point_data[name] = np.array(vals)
                    continue
                if mv:
                    name = mv.group(1)
                    i += 1
                    vals = []
                    while len(vals) < len(ds.points) and i < n:
                        row = lines[i].split()
                        vals.append([float(row[0]), float(row[1]), float(row[2])])
                        i += 1
                    ds.point_data[name] = np.array(vals)
                    continue
                i += 1
            continue
        i += 1
    ds.title = title
    return ds


# ---------------------------------------------------------------------------
# History / line-force readers
# ---------------------------------------------------------------------------
def read_history(outdir: str) -> Tuple[List[str], np.ndarray]:
    path = os.path.join(outdir, "history.csv")
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


def read_line_force(outdir: str) -> Tuple[List[str], np.ndarray]:
    path = os.path.join(outdir, "line_force.csv")
    if not os.path.exists(path):
        return [], np.zeros((0, 0))
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        head = next(r)
        rows = [[float(v) for v in row] for row in r if row]
    return head, np.array(rows)


# ---------------------------------------------------------------------------
# .dat writers
# ---------------------------------------------------------------------------
def write_dat(path: str, data: np.ndarray, header: str) -> None:
    """Write a plain-text .dat table: comment header line(s) then columns."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for line in header.strip().splitlines():
            fh.write(f"# {line}\n")
        np.savetxt(fh, data, fmt="%.9g")


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------
def _save(fig, path: str, dpi: int = 150) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


# ---------------------------------------------------------------------------
# (b) Force / area curves + .dat
# ---------------------------------------------------------------------------
def plot_force_curves(outdir: str, figdir: str, datdir: str) -> List[str]:
    head, h = read_history(outdir)
    idx = {k: n for n, k in enumerate(head)}
    t_ms = h[:, idx["time"]] * 1.0e3
    drag = h[:, idx["coupling_drag"]]
    anchor = np.maximum(h[:, idx["line_anchor_force"]], 0.0)
    area = h[:, idx["canopy_area"]]
    radi = h[:, idx["canopy_radius"]]
    vmax = h[:, idx["struct_vmax"]]

    figs = []

    # --- line tension (per line) ---
    lhead, lh = read_line_force(outdir)
    if lh.size:
        lt = lh[:, 0] * 1.0e3
        lines = lh[:, 1:]
        nline = lines.shape[1]
        fig, ax = plt.subplots(figsize=(10, 5.5))
        cmap = plt.cm.viridis(np.linspace(0, 0.9, max(nline, 1)))
        for k in range(nline):
            ax.plot(lt, lines[:, k], color=cmap[k], lw=0.8, alpha=0.85)
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("suspension-line tension [N]")
        ax.set_title(f"Per-line suspension-line tension ({nline} lines)")
        ax.set_xlim(0, lt[-1])
        ax.grid(alpha=0.3)
        p = os.path.join(figdir, "line_tension_per_line.png")
        _save(fig, p)
        figs.append(p)
        # .dat
        dat = np.column_stack([lt, lines])
        hdr = "time(ms)  " + "  ".join(lhead[1:])
        write_dat(os.path.join(datdir, "line_tension_per_line.dat"), dat, hdr)

    # --- anchor (convergence-point) force ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(t_ms, anchor, color="tab:red", lw=1.4,
            label="convergence-point resultant line force")
    ka = int(np.argmax(anchor))
    ax.plot(t_ms[ka], anchor[ka], "o", ms=6, color="tab:red")
    ax.annotate(f"peak {anchor[ka]:.0f} N @ {t_ms[ka]:.1f} ms",
                xy=(t_ms[ka], anchor[ka]), xytext=(10, -18),
                textcoords="offset points", fontsize=10, color="tab:red")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("force [N]")
    ax.set_title("Convergence-point (anchor) resultant line force vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    p = os.path.join(figdir, "anchor_force_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "anchor_force_time.dat"),
              np.column_stack([t_ms, anchor]),
              "time(ms)  anchor_force(N)")

    # --- canopy resultant (aerodynamic) drag ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(t_ms, drag, color="tab:blue", lw=1.4,
            label="canopy resultant aerodynamic force")
    kd = int(np.argmax(drag))
    ax.plot(t_ms[kd], drag[kd], "o", ms=6, color="tab:blue")
    ax.annotate(f"peak {drag[kd]:.0f} N @ {t_ms[kd]:.1f} ms",
                xy=(t_ms[kd], drag[kd]), xytext=(10, -18),
                textcoords="offset points", fontsize=10, color="tab:blue")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("force [N]")
    ax.set_title("Canopy resultant aerodynamic force vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    p = os.path.join(figdir, "canopy_drag_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "canopy_drag_time.dat"),
              np.column_stack([t_ms, drag]),
              "time(ms)  canopy_drag(N)")

    # --- area + radius ---
    fig, ax = plt.subplots(figsize=(10, 5.5))
    l1, = ax.plot(t_ms, area, color="tab:green", lw=1.4, label="canopy area")
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("canopy area [m$^2$]")
    ax.set_title("Canopy area and mean radius vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    l2, = ax2.plot(t_ms, radi, color="tab:orange", ls="--", lw=1.2,
                   label="mean radius")
    ax2.set_ylabel("mean canopy radius [m]")
    ax.legend(handles=[l1, l2], loc="lower right")
    p = os.path.join(figdir, "canopy_area_radius_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "canopy_area_radius_time.dat"),
              np.column_stack([t_ms, area, radi]),
              "time(ms)  canopy_area(m2)  mean_radius(m)")

    # --- vmax (smart-damping diagnostic) ---
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(t_ms, vmax, color="tab:purple", lw=1.3)
    ax.set_xlabel("time [ms]")
    ax.set_ylabel("max node velocity [m/s]")
    ax.set_title("Structure max nodal velocity (vmax) vs time")
    ax.set_xlim(0, t_ms[-1])
    ax.grid(alpha=0.3)
    p = os.path.join(figdir, "struct_vmax_time.png")
    _save(fig, p)
    figs.append(p)
    write_dat(os.path.join(datdir, "struct_vmax_time.dat"),
              np.column_stack([t_ms, vmax]),
              "time(ms)  struct_vmax(m/s)")

    return figs


# ---------------------------------------------------------------------------
# VTK state listing
# ---------------------------------------------------------------------------
def list_states(outdir: str) -> List[Tuple[float, str, str]]:
    """Return sorted list of (time_ms, fluid_path, struct_path) for every
    state_*.vtk pair in outdir, plus the final state."""
    pairs = []
    for fp in sorted(glob.glob(os.path.join(outdir, "state_*_fluid.vtk"))):
        sp = fp.replace("_fluid.vtk", "_structure.vtk")
        m = re.search(r"state_([\d.]+)_fluid", os.path.basename(fp))
        t = float(m.group(1)) if m else 0.0
        if os.path.exists(sp):
            pairs.append((t * 1.0e3, fp, sp))
    # final state
    ff = os.path.join(outdir, "final_fluid.vtk")
    fs = os.path.join(outdir, "final_structure.vtk")
    if os.path.exists(ff) and os.path.exists(fs):
        pairs.append((None, ff, fs))
    return pairs


# ---------------------------------------------------------------------------
# (c) Canopy shape evolution
# ---------------------------------------------------------------------------
def plot_canopy_evolution(outdir: str, figdir: str) -> List[str]:
    states = list_states(outdir)
    if not states:
        return []
    # pick up to 6 representative states
    n = len(states)
    picks = [states[0]]
    if n > 2:
        for k in range(1, n - 1):
            picks.append(states[k])
    picks = picks[:6]
    if picks[-1] is not states[-1]:
        picks.append(states[-1])
    picks = picks[:6]

    ncol = min(3, len(picks))
    nrow = (len(picks) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.6 * nrow),
                             squeeze=False)
    figs = []
    for ax, (t, _fp, sp) in zip(axes.ravel(), picks):
        ds = read_vtk(sp)
        x = ds.points
        # only triangle cells (type 5)
        tri_mask = ds.cell_types == 5
        tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
        if tris.size == 0:
            ax.set_title(f"t = {t:.1f} ms" if t else "final")
            continue
        tri = Triangulation(x[:, 0], x[:, 2], tris)
        ax.triplot(tri, lw=0.2, color="tab:blue", alpha=0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("z [m]")
        ax.set_title(f"t = {t:.1f} ms" if t is not None else "final")
        ax.grid(alpha=0.2)
    for ax in axes.ravel()[len(picks):]:
        ax.axis("off")
    fig.suptitle("Canopy shape evolution (x-z projection)", fontsize=12)
    p = os.path.join(figdir, "canopy_shape_evolution.png")
    _save(fig, p)
    figs.append(p)

    # side view (x-y)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.6 * nrow),
                             squeeze=False)
    for ax, (t, _fp, sp) in zip(axes.ravel(), picks):
        ds = read_vtk(sp)
        x = ds.points
        tri_mask = ds.cell_types == 5
        tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
        if tris.size:
            tri = Triangulation(x[:, 0], x[:, 1], tris)
            ax.triplot(tri, lw=0.2, color="tab:blue", alpha=0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(f"t = {t:.1f} ms" if t is not None else "final")
        ax.grid(alpha=0.2)
    for ax in axes.ravel()[len(picks):]:
        ax.axis("off")
    fig.suptitle("Canopy shape evolution (x-y side view)", fontsize=12)
    p = os.path.join(figdir, "canopy_shape_side_evolution.png")
    _save(fig, p)
    figs.append(p)
    return figs


# ---------------------------------------------------------------------------
# (c) Field contours: pressure & velocity on a mid-plane slice
# ---------------------------------------------------------------------------
def _slice_2d(ds: VtkDataSet, axis: int = 2, value: float = 0.0,
              tol: float = 1e-6):
    """Project cells whose centroid is near ``value`` along ``axis`` to 2D."""
    centers = np.array([ds.points[c].mean(axis=0) for c in ds.cells])
    sel = np.abs(centers[:, axis] - value) <= tol
    if sel.sum() < 4:
        # widen tolerance to the nearest layer
        dists = np.abs(centers[:, axis] - value)
        uniq = np.unique(np.round(dists, 8))
        if uniq.size:
            sel = dists <= uniq[min(2, uniq.size - 1)]
    centers = centers[sel]
    if centers.size == 0:
        return None, None, None
    axes2 = [0, 1, 2]
    axes2.remove(axis)
    xs = centers[:, axes2[0]]
    ys = centers[:, axes2[1]]
    return xs, ys, sel


def plot_field_contours(outdir: str, figdir: str) -> List[str]:
    states = list_states(outdir)
    if not states:
        return []
    # use the final state (or the last available) for the field snapshot
    t, fp, sp = states[-1]
    ds = read_vtk(fp)
    p = ds.cell_data.get("pressure")
    vel = ds.cell_data.get("velocity")
    if p is None or vel is None:
        return []
    umag = np.linalg.norm(vel, axis=1)
    figs = []

    # mid-plane along z (axis=2) through domain centre
    zval = float(ds.points[:, 2].mean())
    xp, yp, sel = _slice_2d(ds, axis=2, value=zval, tol=0.05)
    if xp is not None and xp.size > 4:
        # pressure
        fig, ax = plt.subplots(figsize=(8, 5))
        sc = ax.scatter(xp, yp, c=p[sel] / 1.0e3, s=8, cmap="RdBu_r")
        plt.colorbar(sc, ax=ax, label="pressure [kPa]")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        tlabel = f"{t:.1f} ms" if t is not None else "final"
        ax.set_title(f"Pressure field (mid z-plane) at t = {tlabel}")
        ax.set_aspect("equal")
        p1 = os.path.join(figdir, "field_pressure.png")
        _save(fig, p1)
        figs.append(p1)
        # velocity magnitude
        fig, ax = plt.subplots(figsize=(8, 5))
        sc = ax.scatter(xp, yp, c=umag[sel], s=8, cmap="viridis")
        plt.colorbar(sc, ax=ax, label="velocity [m/s]")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(f"Velocity magnitude (mid z-plane) at t = {tlabel}")
        ax.set_aspect("equal")
        p2 = os.path.join(figdir, "field_velocity.png")
        _save(fig, p2)
        figs.append(p2)
    return figs


# ---------------------------------------------------------------------------
# (c) Canopy stress / strain contours
# ---------------------------------------------------------------------------
def plot_canopy_stress(outdir: str, figdir: str) -> List[str]:
    states = list_states(outdir)
    if not states:
        return []
    _t, _fp, sp = states[-1]
    ds = read_vtk(sp)
    tri_mask = ds.cell_types == 5
    tris = np.array([c for c, m in zip(ds.cells, tri_mask) if m])
    if tris.size == 0:
        return []
    x = ds.points
    tri = Triangulation(x[:, 0], x[:, 2], tris)
    figs = []
    for name, label, cmap in [("stress_11", "membrane stress S11 [Pa]", "inferno"),
                               ("strain_11", "membrane strain E11", "plasma")]:
        vals = ds.cell_data.get(name)
        if vals is None:
            continue
        v = vals[tri_mask]
        fig, ax = plt.subplots(figsize=(7.5, 6))
        tc = ax.tripcolor(tri, v, cmap=cmap, shading="flat")
        plt.colorbar(tc, ax=ax, label=label)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("z [m]")
        ax.set_title(f"Canopy {label} (final state, x-z view)")
        p = os.path.join(figdir, f"canopy_{name}.png")
        _save(fig, p)
        figs.append(p)
    return figs


# ---------------------------------------------------------------------------
# (c) Video animation of canopy shape + pressure field
# ---------------------------------------------------------------------------
def make_video(outdir: str, figdir: str) -> Optional[str]:
    states = list_states(outdir)
    if len(states) < 3:
        return None
    tmp = os.path.join(figdir, "_frames")
    os.makedirs(tmp, exist_ok=True)
    frames = []
    for k, (t, fp, sp) in enumerate(states):
        fds = read_vtk(fp)
        sds = read_vtk(sp)
        p = fds.cell_data.get("pressure", np.zeros(len(fds.cells)))
        zval = float(fds.points[:, 2].mean())
        xp, yp, sel = _slice_2d(fds, axis=2, value=zval, tol=0.05)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
        if xp is not None and xp.size > 4:
            sc = ax1.scatter(xp, yp, c=p[sel] / 1.0e3, s=6, cmap="RdBu_r",
                             vmin=p.min() / 1e3, vmax=p.max() / 1e3)
            plt.colorbar(sc, ax=ax1, label="pressure [kPa]")
        ax1.set_aspect("equal")
        ax1.set_xlabel("x [m]"); ax1.set_ylabel("y [m]")
        tlabel = f"{t:.1f} ms" if t is not None else "final"
        ax1.set_title(f"pressure field  t={tlabel}")
        # canopy
        tri_mask = sds.cell_types == 5
        tris = np.array([c for c, m in zip(sds.cells, tri_mask) if m])
        if tris.size:
            tri = Triangulation(sds.points[:, 0], sds.points[:, 2], tris)
            tens = sds.cell_data.get("tension", np.zeros(len(sds.cells)))
            v = tens[tri_mask] if tens.size else None
            if v is not None:
                ax2.tripcolor(tri, v, cmap="viridis", shading="flat")
            else:
                ax2.triplot(tri, lw=0.2, color="tab:blue")
        ax2.set_aspect("equal")
        ax2.set_xlabel("x [m]"); ax2.set_ylabel("z [m]")
        ax2.set_title(f"canopy tension  t={tlabel}")
        fp_ = os.path.join(tmp, f"frame_{k:04d}.png")
        fig.tight_layout()
        fig.savefig(fp_, dpi=100)
        plt.close(fig)
        frames.append(fp_)
    out = os.path.join(figdir, "canopy_inflation.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", "4", "-i",
             os.path.join(tmp, "frame_%04d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        out = None
    # cleanup frames
    for f in frames:
        try:
            os.remove(f)
        except OSError:
            pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------
# (a) Conditions text
# ---------------------------------------------------------------------------
def collect_conditions(model, opt, grid, sim) -> Dict[str, str]:
    cond: Dict[str, str] = {}
    # --- model ---
    cond["kfile_title"] = model.title
    cond["units"] = model.units or "(from K file)"
    parts = [(p["pid"], p["title"]) for p in model.parts.values()]
    cond["parts"] = "\n".join(f"  PID {pid}: {name}" for pid, name in parts)
    # --- fluid domain & mesh ---
    y0, y1 = float(grid.x[:, 1].min()), float(grid.x[:, 1].max())
    r = float(np.max(np.sqrt(grid.x[:, 0] ** 2 + grid.x[:, 2] ** 2)))
    bi = grid.boundary_info()
    cond["domain"] = (f"cylinder: y=[{y0:.3f}, {y1:.3f}] m, R={r:.3f} m\n"
                      f"cells={bi['cells']}, faces={bi['faces']}")
    # --- materials ---
    mats = []
    for mid, m in model.materials.items():
        mats.append(f"  MID {mid} ({m.get('type','?')}): " +
                    ", ".join(f"{k}={m[k]}" for k in m
                              if k not in ("type", "mid") and isinstance(m[k], (int, float))))
    cond["materials"] = "\n".join(mats)
    # --- eos ---
    eos_lines = []
    for eid, e in model.eos.items():
        eos_lines.append(f"  EOS {eid} ({e.get('type','?')}): " +
                         ", ".join(f"{k}={e[k]}" for k in e
                                   if k != "type" and isinstance(e[k], (int, float))))
    cond["eos"] = "\n".join(eos_lines) or "(none)"
    # --- solver ---
    gas = sim.fluid.gas
    cond["solver"] = (
        f"endtime={opt.endtime} s, cfl={opt.cfl}, tssfac={opt.tssfac}\n"
        f"inflow: {'constant '+str(opt.constant_vel)+' m/s' if opt.constant_vel else 'K-file curve'}"
        f"  (vel_scale={opt.vel_scale})\n"
        f"fluid: ALE Eulerian, Rusanov flux, ideal gas "
        f"(rho0={gas.rho0:.4f}, e0={gas.e0:.1f}, p0={gas.c4 * gas.e0:.1f} Pa)\n"
        f"FSI penalty coupling: omega={opt.omega}, cdamp={opt.cdamp}, "
        f"pfac={opt.pfac}, pleak={opt.pleak}, leak_cap={opt.leak_cap}, "
        f"mach_cap={opt.fsi_mach_cap}, p_cap={opt.p_cap}\n"
        f"structure: mass_scale={opt.mass_scale}, "
        f"membrane_tension_only={opt.membrane_tension_only}, "
        f"eb_frac={opt.eb_frac}, eb_stab_frac={opt.eb_stab_frac}\n"
        f"bending: bend_scale={opt.bend_scale}, bend_damp={opt.bend_damp}\n"
        f"damping: struct_damping={opt.struct_damping} 1/s, "
        f"struct_damping_vmax={opt.struct_damping_vmax} m/s (smart gate)\n"
        f"shell: THEORY={sim.theory}, BWC={sim.bwc}, IHQ={sim.ihq}, "
        f"hg_qh={opt.hg_qh}\n"
        f"contact: enabled={opt.contact}, scale={opt.contact_scale}, "
        f"vdc={opt.contact_vdc}"
    )
    return cond


def _conditions_html(cond: Dict[str, str]) -> str:
    rows = []
    labels = {"kfile_title": "K-file title", "units": "Units",
              "parts": "Parts", "domain": "Fluid domain & mesh",
              "materials": "Materials", "eos": "Equation of state",
              "solver": "Solver & coupling settings"}
    for key, label in labels.items():
        val = cond.get(key, "")
        rows.append(f"<tr><th class='k'>{html.escape(label)}</th>"
                    f"<td><pre>{html.escape(val)}</pre></td></tr>")
    return "<table class='cond'>" + "".join(rows) + "</table>"


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;
     color:#222;max-width:1100px}
h1{border-bottom:2px solid #444;padding-bottom:6px}
h2{margin-top:28px;border-left:4px solid #3a7;color:#2a5;padding-left:10px}
table.cond{border-collapse:collapse;width:100%;margin:8px 0}
table.cond th.k{background:#eef;text-align:left;vertical-align:top;
     padding:8px;width:220px;border:1px solid #ccd}
table.cond td{padding:8px;border:1px solid #ccd;background:#fafafa}
table.cond pre{margin:0;white-space:pre-wrap;font-size:12px}
.fig{margin:14px 0}
.fig img{max-width:100%;border:1px solid #ccc}
.meta{background:#f4f4f4;padding:10px 14px;border-radius:6px;margin:10px 0}
.tag{display:inline-block;background:#3a7;color:#fff;padding:2px 8px;
     border-radius:10px;font-size:12px;margin-right:6px}
"""


def generate_report(outdir: str, model=None, opt=None, grid=None, sim=None,
                    wall_time: Optional[float] = None,
                    cpu_info: Optional[Dict[str, str]] = None) -> str:
    """Generate the full HTML report + figures + .dat + video.

    ``model/opt/grid/sim`` are optional; if omitted the conditions section is
    filled from what is available (e.g. only wall time + CPU info) so the
    function also works post-hoc on an existing outdir.
    """
    figdir = os.path.join(outdir, "figures")
    datdir = os.path.join(outdir, "data")
    os.makedirs(figdir, exist_ok=True)
    os.makedirs(datdir, exist_ok=True)

    figures: List[str] = []
    # (b) curves
    figures += plot_force_curves(outdir, figdir, datdir)
    # (c) evolution, fields, stress
    figures += plot_canopy_evolution(outdir, figdir)
    figures += plot_field_contours(outdir, figdir)
    figures += plot_canopy_stress(outdir, figdir)
    # (c) video
    video = make_video(outdir, figdir)

    # conditions
    cond = {}
    if model is not None and opt is not None and grid is not None and sim is not None:
        cond = collect_conditions(model, opt, grid, sim)

    cpu = cpu_info or get_cpu_info()

    # summary numbers
    summary = ""
    try:
        head, h = read_history(outdir)
        idx = {k: n for n, k in enumerate(head)}
        t_ms = h[:, idx["time"]] * 1e3
        drag = h[:, idx["coupling_drag"]]
        anchor = h[:, idx["line_anchor_force"]]
        area = h[:, idx["canopy_area"]]
        radi = h[:, idx["canopy_radius"]]
        kd = int(np.argmax(drag))
        ka = int(np.argmax(anchor))
        summary = (
            f"<div class='meta'>"
            f"<span class='tag'>peak canopy force</span> "
            f"{drag[kd]:.0f} N @ {t_ms[kd]:.1f} ms &nbsp;&nbsp; "
            f"<span class='tag'>peak line force</span> "
            f"{anchor[ka]:.0f} N @ {t_ms[ka]:.1f} ms &nbsp;&nbsp; "
            f"<span class='tag'>final area</span> {area[-1]:.3f} m&sup2; &nbsp;&nbsp; "
            f"<span class='tag'>final radius</span> {radi[-1]:.3f} m"
            f"</div>")
    except Exception:
        pass

    # compute-time block
    ct = ""
    if wall_time is not None:
        h_ = int(wall_time // 3600)
        m_ = int((wall_time % 3600) // 60)
        s_ = wall_time - h_ * 3600 - m_ * 60
        ct += f"wall-clock time: <b>{wall_time:.1f} s</b> "
        ct += f"({h_}h {m_}m {s_:.1f}s)<br>"
    ct += (f"CPU model: <b>{cpu['model']}</b><br>"
           f"physical cores: <b>{cpu['physical_cores']}</b> &nbsp; "
           f"logical cores: {cpu['logical_cores']}<br>"
           f"base frequency: <b>{cpu['base_frequency_ghz']} GHz</b>")

    # figure list
    fig_html = []
    captions = {
        "line_tension_per_line": "Per-line suspension-line tension vs time",
        "anchor_force_time": "Convergence-point resultant line force vs time",
        "canopy_drag_time": "Canopy resultant aerodynamic force vs time",
        "canopy_area_radius_time": "Canopy area and mean radius vs time",
        "struct_vmax_time": "Structure max nodal velocity (vmax) vs time",
        "canopy_shape_evolution": "Canopy shape evolution (x-z projection)",
        "canopy_shape_side_evolution": "Canopy shape evolution (x-y side view)",
        "field_pressure": "Pressure field (mid z-plane, final state)",
        "field_velocity": "Velocity-magnitude field (mid z-plane, final state)",
        "canopy_stress_11": "Canopy membrane stress S11 (final state)",
        "canopy_strain_11": "Canopy membrane strain E11 (final state)",
    }
    for f in figures:
        bn = os.path.basename(f)
        key = os.path.splitext(bn)[0]
        cap = captions.get(key, key)
        fig_html.append(
            f"<div class='fig'><img src='figures/{bn}' alt='{bn}'>"
            f"<div style='font-size:13px;color:#555;margin-top:4px'>{cap}</div>"
            f"</div>")

    video_html = ""
    if video and os.path.exists(video):
        video_html = (f"<h2>Video animation</h2>"
                      f"<video controls width='100%' src='figures/{os.path.basename(video)}'>"
                      f"Your browser does not support video.</video>"
                      f"<p style='color:#666;font-size:13px'>Animation of the pressure "
                      f"field (left) and canopy tension (right) over the full inflation.</p>")

    cond_html = _conditions_html(cond) if cond else \
        "<p style='color:#888'>(Conditions not available — run the report " \
        "from inside the solver to populate this section.)</p>"

    html_doc = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>Parachute inflation calculation report</title>
<style>{CSS}</style></head><body>
<h1>减速伞展开过程数值计算报告</h1>
<div class='meta'>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
结果目录: <code>{html.escape(os.path.abspath(outdir))}</code></div>

{summary}

<h2>1 计算条件</h2>
{cond_html}

<h2>2 计算资源与用时</h2>
<div class='meta'>{ct}</div>

<h2>3 伞绳力与汇聚点受力时程曲线</h2>
{fig_html[0] if fig_html else ''}
{fig_html[1] if len(fig_html) > 1 else ''}
<p style='color:#666;font-size:13px'>原始数据见 <code>data/</code> 目录下的
<code>.dat</code> 文件（列：时间 ms，力 N）。</p>

<h2>4 伞衣气动力、面积与速度时程</h2>
{fig_html[2] if len(fig_html) > 2 else ''}
{fig_html[3] if len(fig_html) > 3 else ''}
{fig_html[4] if len(fig_html) > 4 else ''}

<h2>5 伞衣形态变化</h2>
{fig_html[5] if len(fig_html) > 5 else ''}
{fig_html[6] if len(fig_html) > 6 else ''}

<h2>6 流场云图（速度 / 压力）</h2>
{fig_html[7] if len(fig_html) > 7 else ''}
{fig_html[8] if len(fig_html) > 8 else ''}

<h2>7 伞衣应力 / 应变云图</h2>
{fig_html[9] if len(fig_html) > 9 else ''}
{fig_html[10] if len(fig_html) > 10 else ''}

{video_html}

<h2>8 数据文件说明</h2>
<ul>
<li><code>data/*.dat</code> — 所有曲线的原始数据（空格分隔，首行为列名注释）</li>
<li><code>figures/*.png</code> — 报告中所有图片</li>
<li><code>figures/canopy_inflation.mp4</code> — 展开过程动画</li>
<li><code>history.csv</code> — 完整时程历史</li>
<li><code>line_force.csv</code> — 逐伞绳张力时程</li>
<li><code>state_*_fluid.vtk / *_structure.vtk</code> — 各时刻流场/结构 VTK</li>
</ul>
</body></html>"""

    report_path = os.path.join(outdir, "calculation_report.html")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    print(f"[report] wrote {report_path}")
    print(f"[report] {len(figures)} figures, video={'yes' if video else 'no'}")
    return report_path


# ---------------------------------------------------------------------------
# CLI for post-hoc report generation
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Generate calculation report "
                                            "from an existing result directory.")
    p.add_argument("--outdir", required=True, help="result directory")
    p.add_argument("--wall-time", type=float, default=None,
                   help="wall-clock time of the run [s] (optional)")
    a = p.parse_args(argv)
    cpu = get_cpu_info()
    generate_report(a.outdir, wall_time=a.wall_time, cpu_info=cpu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
